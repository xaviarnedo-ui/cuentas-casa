"""Lector del PDF de Revolut, probado con el texto anonimizado de un extracto real."""
import unittest
from pathlib import Path

from importador import revolut
from importador.modelo import FormatoError, Movimiento, euros, huella

FIXTURE = Path(__file__).parent / "fixtures" / "revolut_paginas.txt"


def paginas():
    return FIXTURE.read_text(encoding="utf-8").split("\n=== PAGINA ===\n")


class Parsear(unittest.TestCase):
    def setUp(self):
        self.ext = revolut.parsear(paginas())
        self.movs = self.ext.movimientos

    def test_detecta_revolut(self):
        self.assertTrue(revolut.es_extracto_revolut(paginas()))
        self.assertFalse(revolut.es_extracto_revolut(["CaixaBank extracto"]))

    def test_resumen_e_iban(self):
        self.assertEqual(self.ext.banco, "revolut")
        self.assertEqual(self.ext.iban, "ES0000000000000000000001")
        self.assertEqual(self.ext.saldo_inicial_cent, 3386)
        self.assertEqual(self.ext.saldo_final_cent, 148650)

    def test_movimientos_consolidados_sin_pendientes(self):
        self.assertEqual([m.comercio for m in self.movs],
                         ["Pago de TITULAR UNO", "Una recarga de Apple Pay con *0000", "Mercadona",
                          "H&M", "H&M", "To Titular Dos", "Netflix"])

    def test_signo_por_cambio_de_saldo(self):
        self.assertEqual([m.importe_cent for m in self.movs],
                         [150000, 10000, -6237, -2297, 2297, -7000, -1499])

    def test_fechas(self):
        self.assertEqual([m.fecha for m in self.movs],
                         ["2026-09-01", "2026-09-01", "2026-09-03", "2026-09-06",
                          "2026-09-17", "2026-09-24", "2026-10-04"])
        self.assertEqual(self.movs[2].fecha_valor, "2026-09-04")

    def test_transferencias(self):
        # Solo las recargas son transferencias automáticas; "Pago de"/"To" se deciden con reglas
        # (una transferencia a un tercero, p. ej. un profesor, es un gasto).
        self.assertEqual([m.es_transferencia for m in self.movs],
                         [False, True, False, False, False, False, False])

    def test_descripcion_con_detalle(self):
        self.assertEqual(self.movs[2].descripcion,
                         "Mercadona · A Mercadona Estadi Balea, Palma Mallorc, ESP · Tarjeta: 000000******0001")
        self.assertEqual(self.movs[2].saldo_cent, 157149)

    def test_saldo_que_no_cuadra_aborta(self):
        pags = paginas()
        pags[1] = pags[1].replace("1.571,49€", "1.571,48€", 1)
        with self.assertRaises(FormatoError):
            revolut.parsear(pags)

    def test_no_revolut_aborta(self):
        with self.assertRaises(FormatoError):
            revolut.parsear(["Otro banco"])

    def test_bloque_del_titular_no_entra_en_la_descripcion(self):
        lineas = ["Transacciones de la cuenta desde el 1", "1 sept 2026", "1 sept 2026", "Galp",
                  "20,00€", "13,86€", "A Galp, Palma", "Nombre de", "la cuenta", "TITULAR UNO",
                  "Calle Falsa 1"]
        self.assertEqual(revolut._cuerpo(lineas),
                         ["1 sept 2026", "1 sept 2026", "Galp", "20,00€", "13,86€", "A Galp, Palma"])


class Modelo(unittest.TestCase):
    def test_huella_estable_y_sensible_al_saldo(self):
        a = Movimiento("2026-09-03", "2026-09-04", -6237, "Mercadona", "x", 157149)
        b = Movimiento("2026-09-03", "2026-09-04", -6237, "Mercadona", "otra desc", 157149)
        c = Movimiento("2026-09-03", "2026-09-04", -6237, "Mercadona", "x", 100000)
        self.assertEqual(huella("comun", a), huella("comun", b))
        self.assertNotEqual(huella("comun", a), huella("comun", c))
        self.assertNotEqual(huella("comun", a), huella("otra", a))

    def test_euros(self):
        self.assertEqual(euros(-123456), "-1.234,56 €")
        self.assertEqual(euros(5), "0,05 €")
        self.assertEqual(euros(100000000), "1.000.000,00 €")


if __name__ == "__main__":
    unittest.main()
