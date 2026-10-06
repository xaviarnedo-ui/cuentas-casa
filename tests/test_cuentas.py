"""Lógica de cuentas.py con una Api falsa (sin red ni .env)."""
import contextlib
import io
import tempfile
import unittest
from pathlib import Path

import cuentas
from importador.modelo import Extracto, FormatoError

CSV = str(Path(__file__).parent / "fixtures" / "caixabank.csv")
XAVI = "uuid-xavi"
CUENTAS = [
    {"id": "comun", "nombre": "Común", "banco": "Revolut", "owner": None, "iban_final": "1111"},
    {"id": "revolut-x", "nombre": "Revolut Xavi", "banco": "Revolut", "owner": XAVI, "iban_final": "3805"},
    {"id": "caixabank", "nombre": "CaixaBank", "banco": "CaixaBank", "owner": XAVI, "iban_final": None},
]


class ApiFalsa:
    def __init__(self, cuentas_=None, reglas=None, movimientos=None, agua=None):
        self.tablas = {"cuentas": cuentas_ if cuentas_ is not None else CUENTAS,
                       "reglas": reglas or [],
                       "movimientos": movimientos or [],
                       "agua": agua or [],
                       "categorias": [{"id": "ocio"}, {"id": "piso-agua"}, {"id": "super"}]}
        self.lecturas = []
        self.inserciones = []

    def leer(self, tabla, **filtros):
        self.lecturas.append((tabla, filtros))
        if tabla == "movimientos" and "categoria_id" in filtros:
            return self.tablas["agua"]
        return self.tablas[tabla]

    def insertar(self, tabla, filas, **opciones):
        self.inserciones.append((tabla, filas, opciones))


def extracto(banco="caixabank", iban=""):
    return Extracto(banco, iban, 0, 0, [])


def silencio(f, *args, **kwargs):
    salida = io.StringIO()
    with contextlib.redirect_stdout(salida):
        resultado = f(*args, **kwargs)
    return resultado, salida.getvalue()


class LeerImporte(unittest.TestCase):
    def test_formatos(self):
        self.assertEqual(cuentas.leer_importe("12.340"), 1234000)
        self.assertEqual(cuentas.leer_importe("12.340,5"), 1234050)
        self.assertEqual(cuentas.leer_importe("12340,50"), 1234050)
        self.assertEqual(cuentas.leer_importe("12340.5"), 1234050)
        self.assertEqual(cuentas.leer_importe(" 1.234,56 € "), 123456)
        self.assertEqual(cuentas.leer_importe("0"), 0)
        self.assertEqual(cuentas.leer_importe("23.480"), 2348000)
        self.assertEqual(cuentas.leer_importe("7310"), 731000)
        self.assertEqual(cuentas.leer_importe("12.5"), 1250)
        self.assertEqual(cuentas.leer_importe("1.234.567"), 123456700)

    def test_no_validos(self):
        for malo in ("", "abc", "-5", "1,2,3", "12.34.5", "1.2345"):
            with self.assertRaises(FormatoError):
                cuentas.leer_importe(malo)


class Saldo(unittest.TestCase):
    def test_registra_con_fecha(self):
        api = ApiFalsa(cuentas_=[{"id": "myinvestor", "nombre": "MyInvestor"}])
        self.assertEqual(silencio(cuentas.saldo, api, "myinvestor", "12.340,50", "2026-09-30")[0], 0)
        tabla, filas, opciones = api.inserciones[-1]
        self.assertEqual(tabla, "saldos")
        self.assertEqual(filas, [{"cuenta_id": "myinvestor", "fecha": "2026-09-30", "saldo_cent": 1234050}])
        self.assertEqual(opciones, {"conflicto": "cuenta_id,fecha", "al_chocar": "merge"})

    def test_cuenta_inexistente(self):
        api = ApiFalsa(cuentas_=[{"id": "myinvestor", "nombre": "MyInvestor"}])
        with self.assertRaises(FormatoError):
            cuentas.saldo(api, "nada", "100", "2026-09-30")

    def test_fecha_no_valida(self):
        api = ApiFalsa(cuentas_=[{"id": "myinvestor", "nombre": "MyInvestor"}])
        with self.assertRaises(FormatoError):
            cuentas.saldo(api, "myinvestor", "100", "30/09/2026")

    def test_efectivo_no_se_registra_a_mano(self):
        api = ApiFalsa(cuentas_=[{"id": "cartera", "nombre": "Cartera", "tipo": "efectivo"}])
        with self.assertRaises(FormatoError):
            cuentas.saldo(api, "cartera", "100", "2026-09-30")
        self.assertEqual(api.inserciones, [])

    def test_deuda_no_se_registra_a_mano(self):
        api = ApiFalsa(cuentas_=[{"id": "deuda", "nombre": "Deuda", "tipo": "deuda"}])
        with self.assertRaises(FormatoError):
            cuentas.saldo(api, "deuda", "100", "2026-09-30")
        self.assertEqual(api.inserciones, [])


class LeerExtracto(unittest.TestCase):
    def test_csv_de_caixabank(self):
        self.assertEqual(len(cuentas.leer_extracto(CSV).movimientos), 5)

    def test_csv_desconocido_aborta(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / "otro.csv"
            ruta.write_text("Fecha,Importe\n1,2\n", encoding="utf-8")
            with self.assertRaises(FormatoError):
                cuentas.leer_extracto(str(ruta))


class CuentaDelExtracto(unittest.TestCase):
    def test_por_cuenta_explicita(self):
        self.assertEqual(cuentas.cuenta_del_extracto(ApiFalsa(), extracto("revolut"), "comun")["id"], "comun")

    def test_cuenta_inexistente(self):
        with self.assertRaises(FormatoError):
            cuentas.cuenta_del_extracto(ApiFalsa(), extracto(), "nada")

    def test_por_iban(self):
        c = cuentas.cuenta_del_extracto(ApiFalsa(), extracto("revolut", "ES0000000000003805"), None)
        self.assertEqual(c["id"], "revolut-x")

    def test_iban_sin_cuenta(self):
        with self.assertRaises(FormatoError):
            cuentas.cuenta_del_extracto(ApiFalsa(), extracto("revolut", "ES0000000000009999"), None)

    def test_por_banco_unico(self):
        self.assertEqual(cuentas.cuenta_del_extracto(ApiFalsa(), extracto("caixabank"), None)["id"], "caixabank")

    def test_banco_ambiguo(self):
        with self.assertRaises(FormatoError):
            cuentas.cuenta_del_extracto(ApiFalsa(), extracto("revolut"), None)

    def test_cuenta_que_contradice_el_iban(self):
        with self.assertRaises(FormatoError) as cm:
            cuentas.cuenta_del_extracto(ApiFalsa(), extracto("revolut", "ES0000000000003805"), "comun")
        self.assertIn("3805", str(cm.exception))

    def test_cuenta_que_concuerda_con_el_iban(self):
        c = cuentas.cuenta_del_extracto(ApiFalsa(), extracto("revolut", "ES0000000000003805"), "revolut-x")
        self.assertEqual(c["id"], "revolut-x")

    def test_cuenta_sin_iban_final_no_se_contrasta(self):
        c = cuentas.cuenta_del_extracto(ApiFalsa(), extracto("revolut", "ES0000000000003805"), "caixabank")
        self.assertEqual(c["id"], "caixabank")


class LeerAsignaciones(unittest.TestCase):
    def test_valida(self):
        self.assertEqual(cuentas.leer_asignaciones(["1=ocio", "12= super "]), {1: "ocio", 12: "super"})

    def test_no_validas(self):
        for malo in ("x", "²=ocio", "=ocio", "1=", "a=ocio", "-1=ocio"):
            with self.assertRaises(FormatoError, msg=malo):
                cuentas.leer_asignaciones([malo])

    def test_repetida(self):
        with self.assertRaises(FormatoError) as cm:
            cuentas.leer_asignaciones(["1=a", "1=b"])
        self.assertIn("repetido", str(cm.exception))


REGLAS_COMPLETAS = [{"patron": p, "categoria_id": "super", "owner": None}
                    for p in ("smap ora", "activacion", "sumup", "comun")]


class Importar(unittest.TestCase):
    def test_sin_reglas_no_sube_nada(self):
        api = ApiFalsa()
        codigo, salida = silencio(cuentas.importar, api, CSV, False)
        self.assertEqual(codigo, 2)
        self.assertEqual(api.inserciones, [])
        self.assertIn("Comercios sin regla", salida)
        self.assertIn("--cuenta caixabank", salida)
        self.assertNotIn("[--cuenta", salida)
        self.assertIn("[1] 2026-09-28  BIZUM RECIBIDO", salida)

    def test_con_reglas_y_asignaciones_sube(self):
        api = ApiFalsa(reglas=REGLAS_COMPLETAS)
        codigo, _ = silencio(cuentas.importar, api, CSV, False, {1: "ocio"})
        self.assertEqual(codigo, 0)
        self.assertEqual([t for t, _, _ in api.inserciones], ["movimientos", "saldos"])
        filas = api.inserciones[0][1]
        self.assertEqual(len(filas), 5)
        self.assertEqual({f["categoria_id"] for f in filas}, {"super", "ocio"})

    def test_asignar_un_numero_inexistente_aborta(self):
        api = ApiFalsa(reglas=REGLAS_COMPLETAS)
        with self.assertRaises(FormatoError) as cm:
            silencio(cuentas.importar, api, CSV, False, {1: "ocio", 99: "ocio"})
        self.assertIn("99", str(cm.exception))
        self.assertEqual(api.inserciones, [])

    def test_asignar_a_un_movimiento_que_no_es_generico_aborta(self):
        api = ApiFalsa(reglas=REGLAS_COMPLETAS)
        with self.assertRaises(FormatoError):
            silencio(cuentas.importar, api, CSV, False, {1: "ocio", 2: "ocio"})

    def test_categoria_inexistente_aborta(self):
        with self.assertRaises(FormatoError):
            silencio(cuentas.importar, ApiFalsa(reglas=REGLAS_COMPLETAS), CSV, False, {1: "nada"})

    def test_agua_automatica_se_muestra_y_se_sube(self):
        agua = [{"fecha": "2026-09-01", "importe_cent": -7000}]
        api = ApiFalsa(reglas=REGLAS_COMPLETAS, agua=agua)
        codigo, salida = silencio(cuentas.importar, api, CSV, False)
        self.assertEqual(codigo, 0)
        self.assertIn("[1] 2026-09-28  BIZUM RECIBIDO  70,00 € → piso-agua", salida)
        self.assertIn("--asignar 1=<categoria>", salida)
        self.assertIn("piso-agua", {f["categoria_id"] for f in api.inserciones[0][1]})

    def test_agua_automatica_se_muestra_tambien_si_faltan_reglas(self):
        agua = [{"fecha": "2026-09-01", "importe_cent": -7000}]
        codigo, salida = silencio(cuentas.importar, ApiFalsa(agua=agua), CSV, False)
        self.assertEqual(codigo, 2)
        self.assertIn("→ piso-agua", salida)

    def test_asignar_un_numero_de_agua_automatica_lo_sobrescribe(self):
        agua = [{"fecha": "2026-09-01", "importe_cent": -7000}]
        api = ApiFalsa(reglas=REGLAS_COMPLETAS, agua=agua)
        codigo, salida = silencio(cuentas.importar, api, CSV, False, {1: "ocio"})
        self.assertEqual(codigo, 0)
        self.assertNotIn("→ piso-agua", salida)
        self.assertNotIn("piso-agua", {f["categoria_id"] for f in api.inserciones[0][1]})

    def test_pista_sin_corchetes_si_la_cuenta_es_compartida(self):
        compartida = [{"id": "comun", "nombre": "Común", "banco": "CaixaBank", "owner": None, "iban_final": None}]
        _, salida = silencio(cuentas.importar, ApiFalsa(cuentas_=compartida), CSV, False)
        self.assertNotIn("--cuenta", salida)


if __name__ == "__main__":
    unittest.main()
