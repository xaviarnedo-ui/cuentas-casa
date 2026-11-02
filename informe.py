#!/usr/bin/env python3
"""Informe mensual de gastos y patrimonio (HTML + PDF) a partir de la base de datos.

  python3 informe.py 2026-10 [--html <ruta>] [--sin-pdf]

El PDF se guarda en ~/Desktop/Finanzas/<Mes> <año>.pdf (Chrome sin cabeceras)."""
import argparse
import calendar
import collections
import base64
import json
import re
import urllib.request
from html import escape
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import cuentas
from importador.api import Api
from importador.categorizar import es_generico

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]
CORTOS = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
PLANTILLA = Path(__file__).parent / "informe" / "plantilla.html"
PLANTILLA_DETALLE = Path(__file__).parent / "informe" / "detalle.html"
CARPETA_PDF = Path.home() / "Desktop" / "Finanzas"
ETIQUETAS = Path(__file__).parent / "informe" / "etiquetas.json"  # local: patrón → texto (lleva nombres)
CACHE_FUENTES = Path(__file__).parent / "informe" / ".fuentes.css"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
TIPOS = {"corriente": "Cuenta corriente", "efectivo": "En mano", "ahorro": "Ahorro", "inversion": "Inversión"}
DESDE_MOVIMIENTOS = ("efectivo", "deuda")
# Conceptos del banco poco legibles → nombre para el informe.
NOMBRES = {"RECIBOS VARIOS": "Máster PNI", "GO FORTH RUNNERS": "Go Forth Runners", "REPSOL WAYLET": "Repsol",
           "GRUPO PUERTAS PIZ": "Mando del parking", "SMAP ORA PALMA": "ORA Palma", "LM PALMA CIUDAD": "Leroy Merlin",
           "SumUp *KEVINCOIF": "Peluquería", "FUND.PASQUAL MAR.": "Fund. Pasqual Maragall",
           "ASOC.ESPANOLA CON": "Asoc. Española contra el Cáncer", "APPLE.COM/BILL": "Apple",
           "EasyPark Espana S": "EasyPark", "Activacion": "Activación tarjeta", "PAGO TRANSFERENCIAS": "MyInvestor",
           "AXA AURORA VIDA": "MyAXA", "Ahorro": "Hucha \"Ahorro\"", "DEPORTICKET.COM": "Deporticket",
           "TRAINING SCHEMES": "Tribe (ropa de running)", "CAT COPLEFC": "Colegio profesional",
           "Vueling*VILADECANS": "Vueling", "Decatlon": "Decathlon", "Ingles": "Clases de inglés",
           "Inglés": "Clases de inglés", "Xavi": "Clases de inglés",
           "AGENCIA TRIBUTARI": "Hacienda", "RECIBO UNICO MYBOX": "Seguro MyBox", "COM.DE PROP.FRANC": "Comunidad",
           "PAGO TRASPASOS": "Ascensor (trimestral)", "IBERDROLA CLIENT.": "Iberdrola", "IBERDROLA CLIENTE": "Iberdrola",
           "AJUNT.DE CORNELLA": "IBI Ajuntament de Cornellà", "AIGUES DE BARCEL.": "Aigües de Barcelona"}


def mes_siguiente(mes):
    a, m = int(mes[:4]), int(mes[5:7])
    return "%d-%02d" % (a + m // 12, m % 12 + 1)


def mes_anterior(mes):
    a, m = int(mes[:4]), int(mes[5:7])
    return "%d-%02d" % (a - (m == 1), 12 if m == 1 else m - 1)


def nombre_mes(mes):
    return MESES[int(mes[5:7]) - 1]


def ultimo_dia(mes):
    return "%s-%02d" % (mes, calendar.monthrange(int(mes[:4]), int(mes[5:7]))[1])


def nombre(m):
    if m.get("nota") and (es_generico(m["comercio"]) or m["comercio"].startswith(("To ", "Pago de "))):
        return m["nota"]  # Bizum y traspasos: la nota dice qué fue
    if es_generico(m["comercio"]):
        if m["categoria_id"] == "formacion":
            return "Clases de inglés"
        if (m["categoria_id"] or "").startswith("piso-") and m["importe_cent"] > 0:
            return "Bizum de la inquilina"
        if m["categoria_id"] == "ahorro-inversion" and m["comercio"] in NOMBRES:
            return NOMBRES[m["comercio"]]
        return m["comercio"].capitalize()
    if m["comercio"].startswith("PRES."):
        return "Hipoteca"
    return NOMBRES.get(m["comercio"], m["comercio"])


def es_gasto(m, cats):
    if m["no_es_gasto"]:
        return False
    c = cats.get(m["categoria_id"])
    return c is None or c["cuenta_como_gasto"]


def saldo_a(cuenta, fecha, saldos, movs):
    """Saldo de una cuenta al cierre de `fecha`: suma de movimientos (efectivo, deudas) o último saldo."""
    if cuenta["tipo"] in DESDE_MOVIMIENTOS:
        return sum(m["importe_cent"] for m in movs if m["cuenta_id"] == cuenta["id"] and m["fecha"] <= fecha)
    previos = [s for s in saldos if s["cuenta_id"] == cuenta["id"] and s["fecha"] <= fecha]
    return max(previos, key=lambda s: s["fecha"])["saldo_cent"] if previos else None


def patrimonio(cuentas_propias, fecha, saldos, movs):
    filas = [(c, saldo_a(c, fecha, saldos, movs)) for c in cuentas_propias]
    filas = [(c, v) for c, v in filas if v is not None]
    total = sum(v for _, v in filas)
    bienes = sum(v for c, v in filas if c["tipo"] in ("inmueble", "vehiculo"))
    hipoteca = sum(v for c, v in filas if c["id"].startswith("hipoteca"))
    return {"filas": filas, "total": total, "liquido": total - bienes - hipoteca,
            "tienes": sum(v for _, v in filas if v > 0), "debes": sum(v for _, v in filas if v < 0)}


def euros(c):
    return cuentas.euros(c)


def etiquetas():
    return json.loads(ETIQUETAS.read_text(encoding="utf-8")) if ETIQUETAS.exists() else {}


def etiqueta(m, tabla):
    texto = " ".join((m.get("nota") or m["comercio"]).lower().split()) + " | " + m["comercio"].lower()
    for patron in sorted(tabla, key=len, reverse=True):
        if patron in texto:
            return tabla[patron]
    return None


def concepto_flujo(m, cats, tabla):
    """Línea del cuadre de una cuenta a la que va cada movimiento."""
    c = cats.get(m["categoria_id"])
    if m["no_es_gasto"]:
        return nombre(m)
    if m["categoria_id"] == "ingresos":
        return "Nómina e ingresos"
    if c and c["grupo"] == "piso":
        return "Alquiler del piso" if m["categoria_id"] == "piso-alquiler" else "Piso de Cornellà (gastos y lo que devuelve la inquilina)"
    if m["categoria_id"] == "ahorro-inversion":
        return "Ahorro e inversión"
    if m["categoria_id"] == "transferencias":
        return etiqueta(m, tabla) or ("Traspasos y Bizum entre vosotros" if es_generico(m["comercio"]) else nombre(m))
    if m["importe_cent"] > 0:
        persona = etiqueta(m, tabla)
        return "Devoluciones y repartos" + (" (%s)" % persona.replace("Aportación de ", "") if persona and persona.startswith("Aportación de ") else "")
    return "Gastos"


def flujo(movs, cats, tabla, inicial, final):
    """Cuadre de una cuenta en el mes: saldo inicial + líneas = saldo final (el desfase es lo cobrado en otro mes)."""
    lineas = collections.OrderedDict()
    for m in movs:
        k = concepto_flujo(m, cats, tabla)
        lineas[k] = lineas.get(k, 0) + m["importe_cent"]
    filas = [[k, v] for k, v in lineas.items() if v]
    filas.sort(key=lambda f: (f[1] < 0, -abs(f[1])))
    desfase = final - inicial - sum(v for _, v in filas)
    if desfase:
        filas.append(["Desfase por fecha de cargo (compras que el banco cobra otro mes)", desfase])
    return {"inicial": inicial, "final": final, "filas": filas}


def gasto_por_categoria(movs, cats):
    tot = collections.Counter()
    for m in movs:
        if es_gasto(m, cats):
            tot[m["categoria_id"]] -= m["importe_cent"]
    return sorted(([k, v] for k, v in tot.items() if v), key=lambda f: -f[1])


def datos(api, mes):
    cats = {c["id"]: c for c in api.leer("categorias", select="*")}
    todas = api.leer("cuentas", select="*", order="orden")
    perfil = next(c["owner"] for c in todas if c["id"] == "caixabank")
    propias = [c for c in todas if c["owner"] == perfil]
    vistas = ["comun"] + [c["id"] for c in propias if c["tipo"] in ("corriente", "efectivo")]
    fin = ultimo_dia(mes)
    ant = mes_anterior(mes)
    movs_mes = api.leer("movimientos", select="*", cuenta_id="in.(%s)" % ",".join(vistas),
                        fecha="gte.%s-01" % ant, **{"and": "(fecha.lte.%s)" % fin}, order="fecha")
    del_mes = [m for m in movs_mes if m["fecha"].startswith(mes)]

    gastos = [{"d": int(m["fecha"][8:]), "c": m["categoria_id"], "q": "comun" if m["cuenta_id"] == "comun" else "mia",
               "n": nombre(m), "e": -m["importe_cent"]} for m in del_mes if es_gasto(m, cats)]
    total_ant = -sum(m["importe_cent"] for m in movs_mes if m["fecha"].startswith(ant) and es_gasto(m, cats))
    total = sum(g["e"] for g in gastos)
    mayor = max(gastos, key=lambda g: g["e"], default=None)
    destacado = mayor if mayor and total and mayor["e"] >= total * 0.12 else None

    piso = collections.Counter()
    for m in del_mes:
        c = cats.get(m["categoria_id"])
        if c and c["grupo"] == "piso":
            piso[c["nombre"].replace("Piso · ", "")] += m["importe_cent"]
    filas_piso = sorted(((k, v) for k, v in piso.items() if v), key=lambda kv: -kv[1])
    amortizado = 0
    if any(c["id"] == "hipoteca-piso" for c in propias):
        amortizado = sum(m["importe_cent"] for m in api.leer(
            "movimientos", select="importe_cent", cuenta_id="eq.hipoteca-piso", comercio="eq.Amortización",
            fecha="gte.%s-01" % mes, **{"and": "(fecha.lte.%s)" % fin}))
    nota_piso = "Ingresos y gastos del piso del mes; la luz, el gas y el agua van netos de lo que devuelve la inquilina."
    if amortizado:
        nota_piso += " De la cuota de la hipoteca, %s fueron capital amortizado: también es patrimonio tuyo." % euros(amortizado)

    ahorro = collections.Counter()
    for m in del_mes:
        if m["categoria_id"] == "ahorro-inversion":
            ahorro[nombre(m)] -= m["importe_cent"]

    saldos = api.leer("saldos", select="*", fecha="lte.%s" % fin)
    movs_saldo = api.leer("movimientos", select="cuenta_id,fecha,importe_cent",
                          cuenta_id="in.(%s)" % ",".join(c["id"] for c in propias if c["tipo"] in DESDE_MOVIMIENTOS),
                          fecha="lte.%s" % fin)
    p = patrimonio(propias, fin, saldos, movs_saldo)
    p_ant = patrimonio(propias, ultimo_dia(ant), saldos, movs_saldo)
    if not any(c["tipo"] in ("ahorro", "inversion") for c, _ in p_ant["filas"]):
        p_ant = {"filas": [], "total": None}  # primer mes con datos: no hay con qué comparar
    comun = saldo_a({"id": "comun", "tipo": "corriente"}, fin, saldos, [])
    resumen = []
    for c, v in p["filas"]:
        if c["tipo"] in ("inmueble", "vehiculo"):
            resumen.append([c["nombre"] + " (valor estimado)", v])
    resumen.insert(1, ["Cuentas, ahorro e inversión", sum(v for c, v in p["filas"] if c["tipo"] in TIPOS)])
    for c, v in p["filas"]:
        if c["tipo"] == "deuda":
            resumen.append([c["nombre"] + (" (capital pendiente)" if c["id"].startswith("hipoteca") else ""), v])
    detalle = sorted(([c["nombre"], TIPOS[c["tipo"]], v] for c, v in p["filas"] if c["tipo"] in TIPOS), key=lambda f: -f[2])

    fin_txt = "%d de %s de %s" % (int(fin[8:]), nombre_mes(mes), mes[:4])
    tabla = etiquetas()
    fin_ant = ultimo_dia(ant)
    cuentas_flujo = []
    for cid, titulo in (("comun", "Cuenta común"), ("caixabank", "Tu cuenta corriente (CaixaBank)"), ("efectivo", "Tu efectivo")):
        c = next((x for x in todas if x["id"] == cid), None)
        if not c:
            continue
        movs_c = [m for m in del_mes if m["cuenta_id"] == cid]
        if cid == "efectivo":
            ini, fin_c = saldo_a(c, fin_ant, saldos, movs_saldo), saldo_a(c, fin, saldos, movs_saldo)
        else:
            ini, fin_c = saldo_a(c, fin_ant, saldos, []), saldo_a(c, fin, saldos, [])
        if ini is None:
            ini = (fin_c or 0) - sum(m["importe_cent"] for m in movs_c)
        f = flujo(movs_c, cats, tabla, ini, fin_c if fin_c is not None else ini + sum(m["importe_cent"] for m in movs_c))
        f.update(id=cid, titulo=titulo, cats=gasto_por_categoria(movs_c, cats))
        cuentas_flujo.append(f)

    variacion = []
    if p_ant["filas"]:
        antes = {c["id"]: v for c, v in p_ant["filas"]}
        ahora = {c["id"]: v for c, v in p["filas"]}
        delta = lambda ids: sum(ahora.get(i, 0) - antes.get(i, 0) for i in ids)
        por_tipo = lambda tipos: [c["id"] for c in propias if c["tipo"] in tipos]
        aportado = -sum(m["importe_cent"] for m in del_mes if m["categoria_id"] == "ahorro-inversion")
        inv = delta(por_tipo(("ahorro", "inversion")))
        variacion = [["Cuenta corriente y efectivo", delta(por_tipo(("corriente", "efectivo")))],
                     ["Aportado a ahorro e inversión", aportado],
                     ["Lo que han ganado (o perdido) tus inversiones", inv - aportado],
                     ["Hipoteca amortizada", delta([c["id"] for c in propias if c["id"].startswith("hipoteca")])],
                     ["Deudas", delta([c["id"] for c in propias if c["tipo"] == "deuda" and not c["id"].startswith("hipoteca")])],
                     ["Revalorización estimada de piso y coche", delta(por_tipo(("inmueble", "vehiculo")))]]
        variacion = [v for v in variacion if v[1]]
    pie = ["Datos del 1 al %s: movimientos de la cuenta común y de CaixaBank, apuntes de efectivo, saldos de fin de mes "
           "y valores estimados del piso y el coche (se revisan cada 6 meses)." % fin_txt]
    for m in del_mes:
        if m["no_es_gasto"] and m["importe_cent"]:
            pie.append("No cuenta como gasto: %s, %s%s." % (nombre(m), euros(abs(m["importe_cent"])),
                                                             (" (" + m["nota"] + ")") if m.get("nota") else ""))
    return {
        "mes": {"nombre": nombre_mes(mes), "anio": mes[:4], "dias": int(fin[8:]), "corto": CORTOS[int(mes[5:7]) - 1]},
        "movs": gastos, "cats": {k: {"nombre": c["nombre"], "icono": c["icono"]} for k, c in cats.items()},
        "anterior": {"nombre": nombre_mes(ant), "total": total_ant} if total_ant > 0 else None,
        "destacado": destacado,
        "piso": {"filas": filas_piso, "total": sum(piso.values()), "nota": nota_piso},
        "ahorro": {"filas": sorted(ahorro.items(), key=lambda kv: -kv[1]), "total": sum(ahorro.values())},
        "patri": {"fecha": fin_txt, "total": p["total"], "tienes": p["tienes"], "debes": p["debes"],
                  "liquido": p["liquido"], "anterior": p_ant["total"] if p_ant["filas"] else None,
                  "filas": resumen, "cuentas": detalle, "comun": comun,
                  "nota": "Piso y coche a valor de mercado estimado; hipoteca según su calendario de amortización. "
                          "Saldos de MyInvestor, MyAXA y Trade Republic a fin de mes; el efectivo es el que consta en la app."},
        "pie": pie, "cuentas": cuentas_flujo, "variacion": variacion,
        "fecha_ini": "%d de %s" % (int(fin_ant[8:]), nombre_mes(ant)), "fecha_fin": "%d de %s" % (int(fin[8:]), nombre_mes(mes)),
    }


def html(d, mes):
    texto = PLANTILLA.read_text(encoding="utf-8")
    titulo = "Gastos de %s %s" % (nombre_mes(mes), mes[:4])
    datos_js = json.dumps(d, ensure_ascii=False).replace("</", "<\\/")
    return texto.replace("__TITULO__", titulo).replace("__DATOS__", datos_js)


def fuentes_incrustadas(pagina):
    """Chrome sin cabeceras se cuelga descargando Google Fonts: se incrustan como data: (con caché local)."""
    enlace = re.search(r'<link rel="stylesheet" href="(https://fonts.googleapis.com/[^"]+)">', pagina)
    if not enlace:
        return pagina
    if not CACHE_FUENTES.exists():
        ua = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120 Safari/537.36"}
        css = urllib.request.urlopen(urllib.request.Request(enlace.group(1).replace("&amp;", "&"), headers=ua)).read().decode()
        def incrustar(m):
            datos = urllib.request.urlopen(m.group(1)).read()
            return "url(data:font/woff2;base64,%s)" % base64.b64encode(datos).decode()
        CACHE_FUENTES.write_text(re.sub(r"url\((https://[^)]+)\)", incrustar, css), encoding="utf-8")
    pagina = re.sub(r'<link rel="preconnect"[^>]*>\n?', "", pagina)
    return pagina.replace(enlace.group(0), "<style>" + CACHE_FUENTES.read_text(encoding="utf-8") + "</style>")


def pdf(pagina, destino):
    pagina = fuentes_incrustadas(pagina)
    with tempfile.TemporaryDirectory() as tmp:
        fuente = Path(tmp) / "informe.html"
        fuente.write_text('<!doctype html><html lang="es"><head><meta charset="utf-8">'
                          '<meta name="viewport" content="width=device-width,initial-scale=1"></head><body>'
                          + pagina + "</body></html>", encoding="utf-8")
        salida = Path(tmp) / "informe.pdf"
        proc = subprocess.Popen([CHROME, "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
                                 "--user-data-dir=" + str(Path(tmp) / "perfil"), "--no-pdf-header-footer",
                                 "--run-all-compositor-stages-before-draw", "--virtual-time-budget=6000",
                                 "--print-to-pdf=" + str(salida), fuente.as_uri()],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(90):  # Chrome a veces no termina solo: basta con que el PDF esté escrito
            if salida.exists() and salida.stat().st_size > 0:
                time.sleep(1)
                break
            time.sleep(1)
        proc.kill()
        if not salida.exists():
            raise SystemExit("ERROR: Chrome no generó el PDF.")
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(salida, destino)


CUENTAS_TXT = {"comun": ("Común", "comun"), "caixabank": ("CaixaBank", "mia"), "efectivo": ("Efectivo", "mia")}


def html_detalle(api, mes):
    """Todos los movimientos del mes: gastos por categoría con subtotal y, aparte, lo que no es gasto."""
    cats = {c["id"]: c for c in api.leer("categorias", select="*")}
    fin = ultimo_dia(mes)
    movs = api.leer("movimientos", select="*", cuenta_id="in.(comun,caixabank,efectivo)",
                    fecha="gte.%s-01" % mes, **{"and": "(fecha.lte.%s)" % fin}, order="fecha")

    def tabla(lista):
        filas = []
        for m in lista:
            cuenta, q = CUENTAS_TXT.get(m["cuenta_id"], (m["cuenta_id"], "mia"))
            n = nombre(m)
            extra = []
            if m["comercio"] != n and not es_generico(m["comercio"]):
                extra.append(m["comercio"])
            if m.get("nota") and m["nota"] != n:
                extra.append(m["nota"])
            filas.append('<tr><td class="f num">%s</td><td>%s%s</td><td class="c"><i style="background:var(--%s)"></i>%s</td>'
                         '<td class="i num%s">%s</td></tr>' % (
                             "%d %s" % (int(m["fecha"][8:]), CORTOS[int(m["fecha"][5:7]) - 1]), escape(n),
                             "".join("<small>%s</small>" % escape(e) for e in extra), q, cuenta,
                             " mas" if m["importe_cent"] > 0 else "",
                             ("+" if m["importe_cent"] > 0 else "") + euros(m["importe_cent"]).replace("-", "−")))
        return ('<div class="tabla-wrap"><table><thead><tr><th>Fecha</th><th>Concepto</th><th>Cuenta</th><th class="i">Importe</th>'
                '</tr></thead><tbody>%s</tbody></table></div>' % "".join(filas))

    def bloque(titulo, lista, total_txt):
        return '<div class="bloque"><h3>%s<span class="num">%s</span></h3>%s</div>' % (escape(titulo), total_txt, tabla(lista))

    gasto = collections.defaultdict(list)
    resto = collections.OrderedDict([("Piso de Cornellà", []), ("Ahorro e inversión", []), ("Ingresos", []),
                                     ("Entre cuentas y no cuenta como gasto", [])])
    for m in movs:
        c = cats.get(m["categoria_id"])
        if es_gasto(m, cats):
            gasto[m["categoria_id"]].append(m)
        elif c and c["grupo"] == "piso":
            resto["Piso de Cornellà"].append(m)
        elif m["categoria_id"] == "ahorro-inversion":
            resto["Ahorro e inversión"].append(m)
        elif m["categoria_id"] == "ingresos" and not m["no_es_gasto"]:
            resto["Ingresos"].append(m)
        else:
            resto["Entre cuentas y no cuenta como gasto"].append(m)
    orden = sorted(gasto, key=lambda k: sum(m["importe_cent"] for m in gasto[k]))
    total = -sum(m["importe_cent"] for k in gasto for m in gasto[k])
    por_q = collections.Counter()
    for k in gasto:
        for m in gasto[k]:
            por_q["comun" if m["cuenta_id"] == "comun" else "mia"] -= m["importe_cent"]

    partes = ['<header style="display:grid;gap:14px"><div class="eyebrow">Cuentas de casa · detalle</div>'
              '<h1>Movimientos de %s %s</h1><div class="resumen num">' % (nombre_mes(mes), mes[:4])]
    for etiqueta, valor in (("Gasto del mes", total), ("Común", por_q["comun"]), ("Tuyo", por_q["mia"]),
                            ("Movimientos", len(movs))):
        partes.append("<div><span>%s</span><b>%s</b></div>" % (etiqueta, valor if etiqueta == "Movimientos" else euros(valor)))
    partes.append('</div><p class="sub">Todos los movimientos de la cuenta común, CaixaBank y el efectivo. En verde, '
                  'dinero que entra: en los gastos son devoluciones y ya están restadas del total de su categoría.</p></header>')
    partes.append('<section><h2>Gastos por categoría</h2>')
    for k in orden:
        c = cats.get(k) or {"nombre": "Sin categoría", "icono": ""}
        partes.append(bloque("%s %s" % (c["icono"], c["nombre"]), gasto[k], euros(-sum(m["importe_cent"] for m in gasto[k]))))
    partes.append('</section><section><h2>Fuera del gasto</h2>')
    for titulo, lista in resto.items():
        if lista:
            neto = sum(m["importe_cent"] for m in lista)
            partes.append(bloque(titulo, lista, ("+" if neto > 0 else "") + euros(neto).replace("-", "−") + " neto"))
    partes.append('</section><footer>Generado desde la app de Cuentas de casa. Fechas = día de la operación.</footer>')
    pagina = PLANTILLA_DETALLE.read_text(encoding="utf-8")
    return pagina.replace("__TITULO__", "Movimientos de %s %s" % (nombre_mes(mes), mes[:4])).replace("__CUERPO__", "\n".join(partes))


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("mes", help="AAAA-MM")
    p.add_argument("--html", help="guarda también la página en esta ruta")
    p.add_argument("--sin-pdf", action="store_true")
    p.add_argument("--detalle", action="store_true", help="todos los movimientos del mes (<Mes> <año> - detalle.pdf)")
    args = p.parse_args()
    env = cuentas.leer_env()
    api = Api(env["SUPABASE_URL"], env["SUPABASE_SERVICE_KEY"])
    pagina = html_detalle(api, args.mes) if args.detalle else html(datos(api, args.mes), args.mes)
    if args.html:
        Path(args.html).write_text(pagina, encoding="utf-8")
        print("Página:", args.html)
    if not args.sin_pdf:
        destino = CARPETA_PDF / ("%s %s%s.pdf" % (nombre_mes(args.mes).capitalize(), args.mes[:4],
                                                   " - detalle" if args.detalle else ""))
        pdf(pagina, destino)
        print("PDF:", destino)


if __name__ == "__main__":
    sys.exit(main())
