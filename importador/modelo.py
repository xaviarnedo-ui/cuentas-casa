"""Tipos comunes a todos los lectores de extractos."""
import hashlib
from dataclasses import dataclass, field
from typing import List, Optional


class FormatoError(Exception):
    """El archivo no tiene el formato esperado: no se importa nada."""


@dataclass
class Movimiento:
    fecha: str              # 'YYYY-MM-DD', fecha de la transacción (decide el mes)
    fecha_valor: str        # 'YYYY-MM-DD', orden en que se aplica al saldo
    importe_cent: int       # negativo = sale dinero
    comercio: str
    descripcion: str
    saldo_cent: Optional[int] = None
    es_transferencia: bool = False


@dataclass
class Extracto:
    banco: str
    iban: str
    saldo_inicial_cent: int
    saldo_final_cent: int
    movimientos: List[Movimiento] = field(default_factory=list)


def huella(cuenta_id, m):
    """Identifica un movimiento entre extractos solapados. El saldo hace única cada fila."""
    base = "|".join([cuenta_id, m.fecha, str(m.importe_cent), m.comercio, str(m.saldo_cent)])
    return hashlib.sha1(base.encode("utf-8")).hexdigest()


def euros(cent):
    texto = "{:,.2f}".format(abs(cent) / 100).replace(",", "X").replace(".", ",").replace("X", ".")
    return ("-" if cent < 0 else "") + texto + " €"
