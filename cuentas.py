#!/usr/bin/env python3
"""Importa extractos bancarios a Cuentas de casa (Supabase). Lo ejecuta Claude; ver CLAUDE.md.

  python3 cuentas.py importar <extracto.pdf|.csv> [--cuenta <id>] [--asignar N=<categoria> ...] [--sin-categoria]
  python3 cuentas.py regla <patrón> <categoria_id> [--cuenta <cuenta_id>]
  python3 cuentas.py categorias
  python3 cuentas.py saldo <cuenta_id> <importe> [--fecha AAAA-MM-DD]
"""
import argparse
import re
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

from importador import caixabank, revolut
from importador.api import Api, ApiError
from importador.categorizar import (DIAS_BIZUM_AGUA, gasto_por_mes, posibles_duplicados,
                                    preparar_importacion, sumar_dias)
from importador.modelo import FormatoError, euros

LECTORES = [(revolut.es_extracto_revolut, revolut.parsear)]

RE_IMPORTE_ES = re.compile(r"^(\d{1,3}(?:\.\d{3})+|\d+)(?:,(\d{1,2}))?$")   # 12.340 / 12.340,5 / 12340,50
RE_IMPORTE_PUNTO = re.compile(r"^(\d+)\.(\d{1,2})$")                      # 12340.5


def leer_importe(texto):
    """Importe dictado por Xavi → céntimos. El punto con 3 cifras detrás es de miles."""
    t = texto.replace("€", "").replace(" ", "").strip()
    m = RE_IMPORTE_ES.match(t)
    if m:
        enteros, dec = m.group(1).replace(".", ""), (m.group(2) or "0")
    else:
        m = RE_IMPORTE_PUNTO.match(t)
        if not m:
            raise FormatoError("Importe no válido: '%s' (ej. 12.340,50)" % texto)
        enteros, dec = m.group(1), m.group(2)
    return int(Decimal(enteros + "." + dec) * 100)


def saldo(api, cuenta_id, importe_texto, fecha=None):
    cuenta = next((c for c in api.leer("cuentas", select="id,nombre,tipo") if c["id"] == cuenta_id), None)
    if cuenta is None:
        raise FormatoError("No existe la cuenta '%s'." % cuenta_id)
    if cuenta.get("tipo") in ("efectivo", "deuda"):
        raise FormatoError("El saldo de '%s' se calcula con sus movimientos: no se registra a mano." % cuenta["nombre"])
    fecha = fecha or date.today().isoformat()
    try:
        date.fromisoformat(fecha)
    except ValueError:
        raise FormatoError("Fecha no válida: '%s' (formato AAAA-MM-DD)." % fecha)
    cent = leer_importe(importe_texto)
    api.insertar("saldos", [{"cuenta_id": cuenta_id, "fecha": fecha, "saldo_cent": cent}],
                 conflicto="cuenta_id,fecha", al_chocar="merge")
    print("Saldo de %s a %s: %s" % (cuenta["nombre"], fecha, euros(cent)))
    return 0


def leer_env():
    ruta = Path(__file__).parent / ".env"
    if not ruta.exists():
        sys.exit("No encuentro %s. Cópialo de .env.example y rellénalo." % ruta)
    valores = {}
    for linea in ruta.read_text().splitlines():
        linea = linea.strip()
        if linea and not linea.startswith("#") and "=" in linea:
            clave, _, valor = linea.partition("=")
            valores[clave.strip()] = valor.strip()
    for clave in ("SUPABASE_URL", "SUPABASE_SERVICE_KEY"):
        if not valores.get(clave):
            sys.exit("Falta %s en .env (mira .env.example)." % clave)
    return valores


def paginas_pdf(ruta):
    import fitz
    with fitz.open(ruta) as doc:
        return [p.get_text() for p in doc]


def leer_extracto(ruta):
    if ruta.lower().endswith(".csv"):
        datos = Path(ruta).read_bytes()
        try:
            texto = datos.decode("utf-8-sig")
        except UnicodeDecodeError:
            texto = datos.decode("latin-1")
        if caixabank.es_csv_caixabank(texto):
            return caixabank.parsear(texto)
        raise FormatoError("No reconozco el formato del CSV " + ruta)
    paginas = paginas_pdf(ruta)
    parsear = next((p for detecta, p in LECTORES if detecta(paginas)), None)
    if parsear is None:
        raise FormatoError("No reconozco el banco de " + ruta)
    return parsear(paginas)


def cuenta_del_extracto(api, extracto, cuenta_id):
    cuentas = api.leer("cuentas", select="id,nombre,banco,owner,iban_final")
    if cuenta_id:
        for c in cuentas:
            if c["id"] == cuenta_id:
                if extracto.iban and c["iban_final"] and not extracto.iban.endswith(c["iban_final"]):
                    raise FormatoError("El extracto es de una cuenta acabada en %s, no de '%s'."
                                       % (extracto.iban[-4:], cuenta_id))
                return c
        raise FormatoError("No existe la cuenta '%s'." % cuenta_id)
    if extracto.iban:
        for c in cuentas:
            if c["iban_final"] and extracto.iban.endswith(c["iban_final"]):
                return c
        raise FormatoError("Ninguna cuenta tiene un IBAN acabado en %s." % extracto.iban[-4:])
    del_banco = [c for c in cuentas if c["banco"].lower() == extracto.banco]
    if len(del_banco) == 1:
        return del_banco[0]
    raise FormatoError("No sé a qué cuenta de %s va este extracto: usa --cuenta <id>." % extracto.banco)


def leer_asignaciones(items):
    asignar = {}
    for item in items:
        n, igual, categoria = item.partition("=")
        n = n.strip()
        if not igual or not categoria.strip() or not (n.isascii() and n.isdigit()):
            raise FormatoError("Asignación no válida: %s (formato N=categoria)" % item)
        if int(n) in asignar:
            raise FormatoError("--asignar %s repetido." % n)
        asignar[int(n)] = categoria.strip()
    return asignar


def importar(api, ruta, sin_categoria, asignar=None, cuenta_id=None):
    asignar = asignar or {}
    extracto = leer_extracto(ruta)
    if not extracto.movimientos:
        print("El extracto no tiene movimientos consolidados.")
        return 0
    cuenta = cuenta_del_extracto(api, extracto, cuenta_id)
    if asignar:
        validas = {c["id"] for c in api.leer("categorias", select="id")}
        for cat in asignar.values():
            if cat not in validas:
                raise FormatoError("No existe la categoría '%s'." % cat)
    desde = min(m.fecha for m in extracto.movimientos)
    existentes = api.leer("movimientos", select="huella,fecha,importe_cent,comercio",
                          cuenta_id="eq." + cuenta["id"], fecha="gte." + desde)
    agua_previa = api.leer("movimientos", select="fecha,importe_cent",
                           cuenta_id="eq." + cuenta["id"], categoria_id="eq.piso-agua",
                           fecha="gte." + sumar_dias(desde, -DIAS_BIZUM_AGUA))
    reglas = api.leer("reglas", select="patron,categoria_id,owner")
    plan = preparar_importacion(extracto, cuenta, reglas, {f["huella"] for f in existentes},
                                asignar, agua_previa)
    desconocidos = sorted(set(asignar) - set(plan.numeros_genericos))
    if desconocidos:
        raise FormatoError("--asignar %s: no hay ningún movimiento genérico con ese número." % desconocidos)

    print("%s · %d movimientos en el extracto · %d nuevos · %d ya estaban"
          % (cuenta["nombre"], len(extracto.movimientos), len(plan.nuevos), plan.duplicados))
    for n in posibles_duplicados(plan.nuevos, existentes):
        print("AVISO posible duplicado: %s %s %s" % (n["fecha"], n["comercio"], euros(n["importe_cent"])))
    for g in plan.auto_agua:
        print("  [%d] %s  %s  %s → piso-agua (devolución de agua; corrígelo con --asignar %d=<categoria> si no lo es)"
              % (g["n"], g["fecha"], g["comercio"], euros(g["importe_cent"]), g["n"]))
    if (plan.sin_regla or plan.genericos) and not sin_categoria:
        if plan.sin_regla:
            print("\nComercios sin regla (NO se ha subido nada):")
            for comercio in plan.sin_regla:
                print("  - " + comercio)
            cuenta_arg = " --cuenta " + cuenta["id"] if cuenta["owner"] else ""
            print('Crea las reglas con:  python3 cuentas.py regla "<patrón>" <categoria_id>' + cuenta_arg)
        if plan.genericos:
            print("\nMovimientos genéricos por asignar (NO se ha subido nada):")
            for g in plan.genericos:
                print("  [%d] %s  %s  %s" % (g["n"], g["fecha"], g["comercio"], euros(g["importe_cent"])))
            print("Repite la importación con:  --asignar N=<categoria_id>  (uno por movimiento)")
        return 2

    if plan.nuevos:
        api.insertar("movimientos", plan.nuevos, conflicto="huella", al_chocar="ignore")
    if plan.saldos:
        api.insertar("saldos", plan.saldos, conflicto="cuenta_id,fecha", al_chocar="merge")

    gasto = {c["id"] for c in api.leer("categorias", select="id", cuenta_como_gasto="eq.true")}
    print("Subido. Saldo a %s: %s" % (extracto.movimientos[-1].fecha_valor,
                                      euros(extracto.saldo_final_cent)))
    for mes, cent in gasto_por_mes(plan.nuevos, gasto).items():
        print("  Gasto nuevo en %s: %s" % (mes, euros(cent)))
    return 0


def regla(api, patron, categoria_id, cuenta_id):
    categorias = api.leer("categorias", select="id,owner", id="eq." + categoria_id)
    if not categorias:
        raise FormatoError("No existe la categoría '%s' (mira: python3 cuentas.py categorias)." % categoria_id)
    cuentas = api.leer("cuentas", select="owner", id="eq." + cuenta_id)
    if not cuentas:
        raise FormatoError("No existe la cuenta '%s'." % cuenta_id)
    dueno = categorias[0].get("owner")
    if dueno and dueno != cuentas[0]["owner"]:
        raise FormatoError("La categoría '%s' es privada: usa --cuenta con una cuenta de su dueño." % categoria_id)
    api.insertar("reglas", [{"patron": patron.lower(), "categoria_id": categoria_id,
                             "owner": cuentas[0]["owner"]}],
                 conflicto="patron,owner", al_chocar="merge")
    print("Regla: '%s' → %s" % (patron.lower(), categoria_id))
    return 0


def categorias(api):
    for c in api.leer("categorias", select="id,nombre,cuenta_como_gasto", order="orden"):
        print("%-15s %s%s" % (c["id"], c["nombre"], "" if c["cuenta_como_gasto"] else "  (no es gasto)"))
    return 0


def main():
    p = argparse.ArgumentParser(description="Cuentas de casa")
    sub = p.add_subparsers(dest="orden", required=True)
    pi = sub.add_parser("importar")
    pi.add_argument("archivo")
    pi.add_argument("--cuenta", help="id de la cuenta (si el extracto no trae IBAN ni basta el banco)")
    pi.add_argument("--asignar", action="append", default=[], metavar="N=CATEGORIA",
                    help="categoría de un movimiento genérico numerado (se repite)")
    pi.add_argument("--sin-categoria", action="store_true",
                    help="sube aunque haya comercios sin regla (quedan 'Sin categoría')")
    pr = sub.add_parser("regla")
    pr.add_argument("patron")
    pr.add_argument("categoria_id")
    pr.add_argument("--cuenta", default="comun")
    sub.add_parser("categorias")
    ps = sub.add_parser("saldo")
    ps.add_argument("cuenta_id")
    ps.add_argument("importe")
    ps.add_argument("--fecha", help="fecha del saldo (AAAA-MM-DD); hoy si no se especifica")
    args = p.parse_args()

    env = leer_env()
    api = Api(env["SUPABASE_URL"], env["SUPABASE_SERVICE_KEY"])
    try:
        if args.orden == "importar":
            return importar(api, args.archivo, args.sin_categoria,
                            leer_asignaciones(args.asignar), args.cuenta)
        if args.orden == "regla":
            return regla(api, args.patron, args.categoria_id, args.cuenta)
        if args.orden == "saldo":
            return saldo(api, args.cuenta_id, args.importe, args.fecha)
        return categorias(api)
    except (FormatoError, ApiError) as e:
        print("ERROR: %s" % e, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
