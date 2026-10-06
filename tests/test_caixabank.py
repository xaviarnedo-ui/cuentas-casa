"""Lector del CSV de CaixaBankNow, con una fixture anonimizada."""
import unittest
from pathlib import Path

from importador import caixabank
from importador.modelo import FormatoError

FIXTURE = Path(__file__).parent / "fixtures" / "caixabank.csv"
BOM = "﻿"


def texto():
    return FIXTURE.read_text(encoding="utf-8")


class Parsear(unittest.TestCase):
    def setUp(self):
        self.ext = caixabank.parsear(texto())
        self.movs = self.ext.movimientos

    def test_detecta(self):
        self.assertTrue(caixabank.es_csv_caixabank(texto()))
        self.assertTrue(caixabank.es_csv_caixabank(BOM + texto()))
        self.assertFalse(caixabank.es_csv_caixabank("Fecha,Importe\n"))

    def test_orden_cronologico_e_importes(self):
        self.assertEqual([m.fecha for m in self.movs],
                         ["2026-09-01", "2026-09-05", "2026-09-28", "2026-09-28", "2026-09-30"])
        self.assertEqual([m.importe_cent for m in self.movs], [-50000, -1400, -1, 7000, -135])

    def test_saldos_y_banco(self):
        self.assertEqual(self.ext.banco, "caixabank")
        self.assertEqual(self.ext.iban, "")
        self.assertEqual(self.ext.saldo_inicial_cent, 193360)
        self.assertEqual(self.ext.saldo_final_cent, 148824)
        self.assertEqual(self.movs[-1].saldo_cent, 148824)

    def test_concepto_con_espacios_normalizados(self):
        self.assertEqual(self.movs[1].comercio, "SumUp *TIENDA")
        self.assertEqual(self.movs[1].descripcion, "SumUp *TIENDA")
        self.assertFalse(any(m.es_transferencia for m in self.movs))

    def test_bom(self):
        self.assertEqual(len(caixabank.parsear(BOM + texto()).movimientos), 5)

    def test_saldo_que_no_cuadra_aborta(self):
        with self.assertRaises(FormatoError):
            caixabank.parsear(texto().replace("1.419,59EUR", "1.419,58EUR"))

    def test_cabecera_distinta_aborta(self):
        with self.assertRaises(FormatoError):
            caixabank.parsear("Fecha;Concepto\n")

    def test_columnas_de_mas_aborta(self):
        with self.assertRaises(FormatoError):
            caixabank.parsear(texto().replace("Activacion;", "Activa;cion;"))

    def test_importe_con_formato_raro_aborta(self):
        for malo in (".,00EUR", "1.2.3,00EUR", "1234.567,00EUR"):
            with self.assertRaises(FormatoError, msg=malo):
                caixabank.parsear(texto().replace("1,35EUR", malo, 1))


if __name__ == "__main__":
    unittest.main()
