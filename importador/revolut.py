"""Lector del extracto PDF de Revolut (cuenta conjunta en EUR).

El texto del PDF no dice si un importe es entrada o salida: el signo se deduce
del cambio de saldo respecto a la fila anterior. Las transacciones pendientes se
ignoran (llegan consolidadas en el extracto siguiente)."""
import re

from .modelo import Extracto, FormatoError, Movimiento

MESES = {"ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6, "jul": 7,
         "ago": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dic": 12}
RE_FECHA = re.compile(r"^(\d{1,2}) ([a-z]+)\.? (\d{4})$")
RE_IMPORTE = re.compile(r"^(-?[\d.]+,\d{2})€$")
RE_IBAN = re.compile(r"^ES\d{22}$")
CABECERA_TABLA = {"Fecha de la", "transacción", "Fecha valor", "Descripción",
                  "Dinero saliente", "Dinero entrante", "Saldo"}
PREFIJOS_TRANSFERENCIA = ("Una recarga de ",)


def es_extracto_revolut(paginas):
    return bool(paginas) and "Revolut Bank UAB" in paginas[0]


def _cent(texto):
    return int(RE_IMPORTE.match(texto).group(1).replace(".", "").replace(",", ""))


def _fecha(texto):
    dia, mes, anio = RE_FECHA.match(texto).groups()
    if mes not in MESES:
        raise FormatoError("Mes desconocido en la fecha: " + texto)
    return "%s-%02d-%02d" % (anio, MESES[mes], int(dia))


def _resumen(lineas):
    try:
        i = lineas.index("Resumen del saldo")
    except ValueError:
        raise FormatoError("No encuentro el 'Resumen del saldo'.")
    importes = [_cent(l) for l in lineas[i:i + 25] if RE_IMPORTE.match(l)]
    if len(importes) < 4:
        raise FormatoError("El resumen del saldo no tiene los 4 importes esperados.")
    return importes[:4]  # inicial, saliente, entrante, final


def _cuerpo(lineas):
    """Líneas de la tabla de transacciones consolidadas, sin cabeceras, pies ni datos del titular."""
    try:
        inicio = next(i for i, l in enumerate(lineas) if l.startswith("Transacciones de la cuenta"))
    except StopIteration:
        raise FormatoError("No encuentro la tabla 'Transacciones de la cuenta'.")
    limpias, saltando, pendientes_de_saltar = [], False, 0
    for l in lineas[inicio + 1:]:
        if l.startswith("Extracto de cuenta") or l.startswith("Nombre de"):
            saltando = True
            continue
        if saltando:
            if l.startswith("Página"):
                saltando, pendientes_de_saltar = False, 2  # nº de página y total
            continue
        if pendientes_de_saltar:
            pendientes_de_saltar -= 1
            continue
        if l and l not in CABECERA_TABLA:
            limpias.append(l)
    return limpias


def _filas(cuerpo):
    filas, i = [], 0
    while i < len(cuerpo):
        if RE_FECHA.match(cuerpo[i]) and i + 1 < len(cuerpo) and RE_FECHA.match(cuerpo[i + 1]):
            fila = {"fecha": _fecha(cuerpo[i]), "valor": _fecha(cuerpo[i + 1]), "titulo": [], "detalle": []}
            i += 2
            while i < len(cuerpo) and not RE_IMPORTE.match(cuerpo[i]):
                fila["titulo"].append(cuerpo[i])
                i += 1
            if i + 1 >= len(cuerpo) or not RE_IMPORTE.match(cuerpo[i + 1]):
                raise FormatoError("Transacción sin importe y saldo: " + " ".join(fila["titulo"]))
            fila["importe"], fila["saldo"] = _cent(cuerpo[i]), _cent(cuerpo[i + 1])
            i += 2
            filas.append(fila)
        elif filas:
            filas[-1]["detalle"].append(cuerpo[i])
            i += 1
        else:
            raise FormatoError("Línea inesperada antes de la primera transacción: " + cuerpo[i])
    return filas


def parsear(paginas):
    if not es_extracto_revolut(paginas):
        raise FormatoError("No es un extracto de Revolut.")
    lineas = [l.strip() for p in paginas for l in p.split("\n")]
    inicial, saliente, entrante, final = _resumen(lineas)
    iban = next((l for l in lineas if RE_IBAN.match(l)), None)
    if iban is None:
        raise FormatoError("No encuentro el IBAN de la cuenta.")

    movimientos, saldo = [], inicial
    for f in _filas(_cuerpo(lineas)):
        delta = f["saldo"] - saldo
        titulo = " ".join(f["titulo"])
        if abs(delta) != f["importe"]:
            raise FormatoError("El saldo no cuadra en '%s' del %s." % (titulo, f["fecha"]))
        saldo = f["saldo"]
        movimientos.append(Movimiento(
            fecha=f["fecha"], fecha_valor=f["valor"], importe_cent=delta, comercio=titulo,
            descripcion=" · ".join([titulo] + f["detalle"]), saldo_cent=f["saldo"],
            es_transferencia=titulo.startswith(PREFIJOS_TRANSFERENCIA)))

    if saldo != final:
        raise FormatoError("El saldo final (%d) no coincide con el resumen (%d)." % (saldo, final))
    salidas = -sum(m.importe_cent for m in movimientos if m.importe_cent < 0)
    entradas = sum(m.importe_cent for m in movimientos if m.importe_cent > 0)
    if (salidas, entradas) != (saliente, entrante):
        raise FormatoError("Los totales de entradas/salidas no coinciden con el resumen.")
    return Extracto("revolut", iban, inicial, final, movimientos)
