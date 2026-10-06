"""Asigna categoría a cada movimiento y decide qué falta por preguntar a Xavi."""
import hashlib
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Dict, List

from .modelo import huella

TRANSFERENCIAS = "transferencias"
# Conceptos de banco sin nombre: cada uno puede ser cualquier cosa, así que nunca usan reglas.
GENERICOS = ("bizum recibido", "bizum enviado", "transfer inmediata", "pago transferencias")
DIAS_BIZUM_AGUA = 45


def es_generico(comercio):
    return " ".join(comercio.lower().split()) in GENERICOS


def sumar_dias(fecha, n):
    return (date.fromisoformat(fecha) + timedelta(days=n)).isoformat()


class _FacturasAgua:
    """Cargos de agua aún sin devolver. Un Bizum por el mismo importe en los 45 días
    siguientes es su devolución (uno a uno, por orden de fecha)."""

    def __init__(self, previos):
        self.pendientes = []
        for p in sorted(previos, key=lambda x: (x["fecha"], x["importe_cent"])):
            self.registrar(p["fecha"], p["importe_cent"])

    def _buscar(self, fecha, importe_cent):
        for cargo in self.pendientes:
            if (-cargo["importe_cent"] == importe_cent
                    and cargo["fecha"] <= fecha <= sumar_dias(cargo["fecha"], DIAS_BIZUM_AGUA)):
                return cargo
        return None

    def es_devolucion(self, fecha, importe_cent):
        return importe_cent > 0 and self._buscar(fecha, importe_cent) is not None

    def registrar(self, fecha, importe_cent):
        if importe_cent < 0:
            self.pendientes.append({"fecha": fecha, "importe_cent": importe_cent})
        else:
            cargo = self._buscar(fecha, importe_cent)
            if cargo is not None:
                self.pendientes.remove(cargo)


def buscar_regla(comercio, reglas, owner):
    """Gana la regla del dueño de la cuenta sobre la compartida y, a igualdad, el patrón
    más largo (más específico). Las reglas de otra persona nunca se aplican."""
    texto = comercio.lower()
    candidatas = [r for r in reglas
                  if r["patron"].lower() in texto and r["owner"] in (None, owner)]
    if not candidatas:
        return None
    mejor = max(candidatas, key=lambda r: (r["owner"] is not None, len(r["patron"])))
    return mejor["categoria_id"]


@dataclass
class PlanImportacion:
    nuevos: List[dict]
    duplicados: int
    sin_regla: List[str]
    saldos: List[dict]
    genericos: List[dict] = field(default_factory=list)       # pendientes de asignar
    numeros_genericos: List[int] = field(default_factory=list)  # todos los vistos en esta pasada
    auto_agua: List[dict] = field(default_factory=list)       # genéricos asignados solos a piso-agua


def posibles_duplicados(nuevos, existentes):
    """Filas nuevas que coinciden en (fecha, importe, comercio) con algo ya subido: aviso por si
    la huella no reconoce un movimiento que el banco ha repetido con otro saldo."""
    vistos = {(f["fecha"], f["importe_cent"], f["comercio"]) for f in existentes}
    return [n for n in nuevos if (n["fecha"], n["importe_cent"], n["comercio"]) in vistos]


def preparar_importacion(extracto, cuenta, reglas, huellas_existentes, asignaciones=None, agua_previa=None):
    asignaciones = asignaciones or {}
    agua = _FacturasAgua(agua_previa or [])
    nuevos, duplicados, sin_regla = [], 0, []
    genericos, numeros_genericos, auto_agua, num_generico = [], [], [], 0
    repeticiones: Dict[str, int] = {}
    for m in extracto.movimientos:
        h = huella(cuenta["id"], m)
        k = repeticiones.get(h, 0)  # filas idénticas del mismo extracto no deben colapsar
        repeticiones[h] = k + 1
        if k:
            h = hashlib.sha1((h + "|" + str(k)).encode("utf-8")).hexdigest()
        if h in huellas_existentes:
            duplicados += 1
            continue
        if m.es_transferencia:
            categoria = TRANSFERENCIAS
        elif es_generico(m.comercio):
            num_generico += 1
            numeros_genericos.append(num_generico)
            if num_generico in asignaciones:
                categoria = asignaciones[num_generico]
            elif m.comercio.lower().startswith("bizum recibido") and agua.es_devolucion(m.fecha, m.importe_cent):
                categoria = "piso-agua"
                auto_agua.append({"n": num_generico, "fecha": m.fecha, "comercio": m.comercio,
                                  "importe_cent": m.importe_cent})
            else:
                categoria = None
                genericos.append({"n": num_generico, "fecha": m.fecha, "comercio": m.comercio,
                                  "importe_cent": m.importe_cent})
        else:
            categoria = buscar_regla(m.comercio, reglas, cuenta["owner"])
            if categoria is None and m.comercio not in sin_regla:
                sin_regla.append(m.comercio)
        if categoria == "piso-agua":
            agua.registrar(m.fecha, m.importe_cent)
        nuevos.append({"cuenta_id": cuenta["id"], "fecha": m.fecha, "importe_cent": m.importe_cent,
                       "descripcion": m.descripcion, "comercio": m.comercio,
                       "categoria_id": categoria, "origen": "import", "huella": h})

    ultimo_saldo = {}
    for m in extracto.movimientos:  # van en orden de fecha valor: el último del día gana
        if m.saldo_cent is not None:
            ultimo_saldo[m.fecha_valor] = m.saldo_cent
    saldos = [{"cuenta_id": cuenta["id"], "fecha": f, "saldo_cent": s}
              for f, s in sorted(ultimo_saldo.items())]
    return PlanImportacion(nuevos, duplicados, sin_regla, saldos, genericos, numeros_genericos, auto_agua)


def gasto_por_mes(filas, categorias_gasto):
    """Gasto = −(suma de importes) de lo que cuenta como gasto o no tiene categoría."""
    total: Dict[str, int] = {}
    for f in filas:
        if f["categoria_id"] is None or f["categoria_id"] in categorias_gasto:
            mes = f["fecha"][:7]
            total[mes] = total.get(mes, 0) - f["importe_cent"]
    return {mes: v for mes, v in sorted(total.items()) if v}
