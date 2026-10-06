"""Lector del CSV de movimientos de CaixaBankNow (Concepto;Fecha;Importe;Saldo).

Viene del más reciente al más antiguo y no trae IBAN: la cuenta se decide por el banco.
Cada fila debe cuadrar con el saldo de la anterior (en orden cronológico)."""
import re

from .modelo import Extracto, FormatoError, Movimiento

CABECERA = "Concepto;Fecha;Importe;Saldo"
RE_FECHA = re.compile(r"^(\d{2})/(\d{2})/(\d{4})$")
RE_IMPORTE = re.compile(r"^([+-]?)(\d{1,3}(?:\.\d{3})*|\d+),(\d{2})EUR$")


def _sin_bom(texto):
    return texto[1:] if texto.startswith("﻿") else texto


def es_csv_caixabank(texto):
    return _sin_bom(texto).startswith(CABECERA)


def _cent(texto):
    m = RE_IMPORTE.match(texto.strip())
    if not m:
        raise FormatoError("Importe con formato desconocido: " + texto)
    valor = int(m.group(2).replace(".", "")) * 100 + int(m.group(3))
    return -valor if m.group(1) == "-" else valor


def _fecha(texto):
    m = RE_FECHA.match(texto.strip())
    if not m:
        raise FormatoError("Fecha con formato desconocido: " + texto)
    dia, mes, anio = m.groups()
    return "%s-%s-%s" % (anio, mes, dia)


def parsear(texto):
    lineas = [l for l in _sin_bom(texto).splitlines() if l.strip()]
    if not lineas or lineas[0].strip() != CABECERA:
        raise FormatoError("No es un CSV de CaixaBank (cabecera esperada: %s)." % CABECERA)
    filas = []
    for numero, linea in enumerate(lineas[1:], 2):
        partes = linea.split(";")
        if len(partes) != 4:
            raise FormatoError("La línea %d no tiene 4 columnas: %s" % (numero, linea))
        concepto, fecha, importe, saldo = partes
        filas.append((" ".join(concepto.split()), _fecha(fecha), _cent(importe), _cent(saldo)))
    filas.reverse()  # del más antiguo al más reciente
    if not filas:
        return Extracto("caixabank", "", 0, 0, [])
    inicial = filas[0][3] - filas[0][2]
    movimientos, saldo = [], inicial
    for concepto, fecha, importe, nuevo_saldo in filas:
        if saldo + importe != nuevo_saldo:
            raise FormatoError("El saldo no cuadra en '%s' del %s." % (concepto, fecha))
        saldo = nuevo_saldo
        movimientos.append(Movimiento(fecha=fecha, fecha_valor=fecha, importe_cent=importe,
                                      comercio=concepto, descripcion=concepto, saldo_cent=nuevo_saldo))
    return Extracto("caixabank", "", inicial, saldo, movimientos)
