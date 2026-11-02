"""Lectores del PDF de CaixaBankNow y del CSV de Revolut, con datos inventados."""
import unittest

from importador import caixabank, revolut
from importador.modelo import FormatoError

PDF_P1 = """Titular Persona De Prueba
IBAN ES00 0000 0000 0000 0000 1234
Periodo 01/10/2026 - 31/10/2026
Saldo disponible 999.99
Concepto
Fecha
Importe Saldo
BIZUM ENVIADO
30/10/2026
-20,00€
1.130,00€
NOMINA
02/10/2026
+1500,00€ 1150,00€
1/2
"""
PDF_P2 = """SUPER DE BARRIO
01/10/2026
-50,00€
-350,00€
PRES.0000
01/10/2026
-300,00€ -300,00€
2/2
"""

CSV_REVOLUT = """Tipo,Producto,Fecha de inicio,Fecha de finalización,Descripción,Importe,Comisión,Divisa,State,Saldo
Pago con tarjeta,Actual,2026-09-30 19:59:15,2026-10-01 14:35:03,Super,-7.68,0.00,EUR,COMPLETADO,92.32
Recargas,Actual,2026-10-02 20:13:01,2026-10-02 20:13:02,Una recarga de Apple Pay con *0000,50.00,0.00,EUR,COMPLETADO,142.32
Pago con tarjeta,Actual,2026-10-20 10:09:00,,Tienda,-11.60,0.00,EUR,DEVUELTO,
Transferir,Actual,2026-10-28 15:25:36,2026-10-28 15:25:37,"Pago, con coma",-42.32,0.00,EUR,COMPLETADO,100.00
"""


class PdfCaixaBank(unittest.TestCase):
    def setUp(self):
        self.ext = caixabank.parsear_pdf([PDF_P1, PDF_P2])
        self.movs = self.ext.movimientos

    def test_detecta(self):
        self.assertTrue(caixabank.es_pdf_caixabank([PDF_P1]))
        self.assertFalse(caixabank.es_pdf_caixabank(["Revolut Bank UAB"]))

    def test_orden_importes_y_saldos(self):
        self.assertEqual([m.fecha for m in self.movs], ["2026-10-01", "2026-10-01", "2026-10-02", "2026-10-30"])
        self.assertEqual([m.comercio for m in self.movs], ["PRES.0000", "SUPER DE BARRIO", "NOMINA", "BIZUM ENVIADO"])
        self.assertEqual([m.importe_cent for m in self.movs], [-30000, -5000, 150000, -2000])
        self.assertEqual(self.ext.saldo_inicial_cent, 0)
        self.assertEqual(self.ext.saldo_final_cent, 113000)
        self.assertEqual(self.ext.iban, "ES0000000000000000001234")
        self.assertEqual(self.ext.banco, "caixabank")

    def test_saldo_que_no_cuadra_aborta(self):
        with self.assertRaises(FormatoError):
            caixabank.parsear_pdf([PDF_P1.replace("1.130,00€", "1.130,01€"), PDF_P2])

    def test_fila_sin_saldo_aborta(self):
        with self.assertRaises(FormatoError):
            caixabank.parsear_pdf([PDF_P1, PDF_P2.replace("-300,00€ -300,00€", "-300,00€")])


class CsvRevolut(unittest.TestCase):
    def setUp(self):
        self.ext = revolut.parsear_csv(CSV_REVOLUT)
        self.movs = self.ext.movimientos

    def test_detecta(self):
        self.assertTrue(revolut.es_csv_revolut(CSV_REVOLUT))
        self.assertFalse(revolut.es_csv_revolut("Concepto;Fecha;Importe;Saldo\n"))

    def test_solo_completados_con_fechas_y_saldos(self):
        self.assertEqual([m.comercio for m in self.movs], ["Super", "Una recarga de Apple Pay con *0000", "Pago, con coma"])
        self.assertEqual([m.fecha for m in self.movs], ["2026-09-30", "2026-10-02", "2026-10-28"])
        self.assertEqual(self.movs[0].fecha_valor, "2026-10-01")
        self.assertEqual([m.importe_cent for m in self.movs], [-768, 5000, -4232])
        self.assertEqual([m.saldo_cent for m in self.movs], [9232, 14232, 10000])
        self.assertEqual([m.es_transferencia for m in self.movs], [False, True, False])
        self.assertEqual((self.ext.saldo_inicial_cent, self.ext.saldo_final_cent), (10000, 10000))
        self.assertEqual((self.ext.banco, self.ext.iban), ("revolut", ""))

    def test_saldo_que_no_cuadra_aborta(self):
        with self.assertRaises(FormatoError):
            revolut.parsear_csv(CSV_REVOLUT.replace("142.32", "142.33"))

    def test_divisa_distinta_aborta(self):
        with self.assertRaises(FormatoError):
            revolut.parsear_csv(CSV_REVOLUT.replace(",EUR,COMPLETADO,92.32", ",USD,COMPLETADO,92.32"))


if __name__ == "__main__":
    unittest.main()
