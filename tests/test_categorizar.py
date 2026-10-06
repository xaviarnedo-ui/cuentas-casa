import unittest

from importador.categorizar import (TRANSFERENCIAS, buscar_regla, es_generico, gasto_por_mes,
                                    posibles_duplicados, preparar_importacion, sumar_dias)
from importador.modelo import Extracto, Movimiento, huella

XAVI = "uuid-xavi"
REGLAS = [
    {"patron": "mercadona", "categoria_id": "super", "owner": None},
    {"patron": "don pedro", "categoria_id": "restaurantes", "owner": None},
    {"patron": "don pedro cafe", "categoria_id": "ocio", "owner": None},
    {"patron": "mercadona", "categoria_id": "casa", "owner": XAVI},
    {"patron": "galp", "categoria_id": "transporte", "owner": "uuid-andrea"},
]


class BuscarRegla(unittest.TestCase):
    def test_sin_distinguir_mayusculas(self):
        self.assertEqual(buscar_regla("MERCADONA Estadi", REGLAS, None), "super")

    def test_gana_el_patron_mas_largo(self):
        self.assertEqual(buscar_regla("Don Pedro Cafe Bistro", REGLAS, None), "ocio")

    def test_la_regla_del_dueno_gana_a_la_compartida(self):
        self.assertEqual(buscar_regla("Mercadona", REGLAS, XAVI), "casa")

    def test_las_reglas_de_otro_no_se_aplican(self):
        self.assertIsNone(buscar_regla("Galp", REGLAS, XAVI))
        self.assertIsNone(buscar_regla("Galp", REGLAS, None))

    def test_las_reglas_personales_no_se_aplican_a_la_comun(self):
        self.assertEqual(buscar_regla("Mercadona", REGLAS, None), "super")


def mov(fecha, valor, importe, comercio, saldo, transf=False):
    return Movimiento(fecha, valor, importe, comercio, comercio + " · detalle", saldo, transf)


class PrepararImportacion(unittest.TestCase):
    def setUp(self):
        self.cuenta = {"id": "comun", "owner": None}
        self.movs = [
            mov("2026-09-01", "2026-09-01", 50000, "Pago de X", 53386, True),
            mov("2026-09-01", "2026-09-02", -2000, "Galp", 51386),
            mov("2026-09-03", "2026-09-04", -6237, "Mercadona", 45149),
            mov("2026-09-04", "2026-09-04", -500, "Bar Xorri", 44649),
            mov("2026-09-05", "2026-09-06", -800, "Bar Xorri", 43849),
        ]
        self.ext = Extracto("revolut", "ES00", 3386, 43849, self.movs)

    def test_categoriza_y_marca_transferencias(self):
        plan = preparar_importacion(self.ext, self.cuenta, REGLAS, set())
        self.assertEqual([f["categoria_id"] for f in plan.nuevos],
                         [TRANSFERENCIAS, None, "super", None, None])
        self.assertEqual(plan.nuevos[2], {
            "cuenta_id": "comun", "fecha": "2026-09-03", "importe_cent": -6237,
            "descripcion": "Mercadona · detalle", "comercio": "Mercadona", "categoria_id": "super",
            "origen": "import", "huella": huella("comun", self.movs[2])})

    def test_sin_regla_unicos_en_orden(self):
        plan = preparar_importacion(self.ext, self.cuenta, REGLAS, set())
        self.assertEqual(plan.sin_regla, ["Galp", "Bar Xorri"])

    def test_salta_duplicados(self):
        ya = {huella("comun", self.movs[0]), huella("comun", self.movs[1])}
        plan = preparar_importacion(self.ext, self.cuenta, REGLAS, ya)
        self.assertEqual(plan.duplicados, 2)
        self.assertEqual(len(plan.nuevos), 3)
        self.assertEqual(plan.sin_regla, ["Bar Xorri"])

    def test_saldos_ultimo_de_cada_dia_por_fecha_valor(self):
        plan = preparar_importacion(self.ext, self.cuenta, REGLAS, set())
        self.assertEqual(plan.saldos, [
            {"cuenta_id": "comun", "fecha": "2026-09-01", "saldo_cent": 53386},
            {"cuenta_id": "comun", "fecha": "2026-09-02", "saldo_cent": 51386},
            {"cuenta_id": "comun", "fecha": "2026-09-04", "saldo_cent": 44649},
            {"cuenta_id": "comun", "fecha": "2026-09-06", "saldo_cent": 43849},
        ])

    def test_filas_identicas_en_un_extracto_no_se_colapsan(self):
        m = mov("2026-09-07", "2026-09-07", -300, "Cafe Sol", 10000)
        ext = Extracto("revolut", "ES00", 10300, 10000, [m, m])
        plan = preparar_importacion(ext, self.cuenta, REGLAS, set())
        self.assertEqual(len(plan.nuevos), 2)
        h0, h1 = (f["huella"] for f in plan.nuevos)
        self.assertNotEqual(h0, h1)
        self.assertEqual(h0, huella("comun", m))  # la primera conserva la huella de siempre

    def test_repetidas_ya_importadas_se_cuentan_como_duplicadas(self):
        m = mov("2026-09-07", "2026-09-07", -300, "Cafe Sol", 10000)
        ext = Extracto("revolut", "ES00", 10300, 10000, [m, m])
        ya = {f["huella"] for f in preparar_importacion(ext, self.cuenta, REGLAS, set()).nuevos}
        plan = preparar_importacion(ext, self.cuenta, REGLAS, ya)
        self.assertEqual((len(plan.nuevos), plan.duplicados), (0, 2))


class PosiblesDuplicados(unittest.TestCase):
    def test_marca_los_que_coinciden_en_fecha_importe_y_comercio(self):
        nuevos = [{"fecha": "2026-09-03", "importe_cent": -6237, "comercio": "Mercadona"},
                  {"fecha": "2026-09-03", "importe_cent": -6237, "comercio": "Galp"},
                  {"fecha": "2026-09-04", "importe_cent": -6237, "comercio": "Mercadona"}]
        existentes = [{"fecha": "2026-09-03", "importe_cent": -6237, "comercio": "Mercadona",
                       "huella": "x"}]
        self.assertEqual(posibles_duplicados(nuevos, existentes), [nuevos[0]])

    def test_sin_existentes_no_hay_avisos(self):
        self.assertEqual(posibles_duplicados([{"fecha": "2026-09-03", "importe_cent": 1,
                                               "comercio": "A"}], []), [])


class GastoPorMes(unittest.TestCase):
    def test_suma_gasto_y_resta_devoluciones(self):
        filas = [
            {"fecha": "2026-09-01", "importe_cent": 50000, "categoria_id": TRANSFERENCIAS},
            {"fecha": "2026-09-03", "importe_cent": -6237, "categoria_id": "super"},
            {"fecha": "2026-09-06", "importe_cent": -2297, "categoria_id": "compras"},
            {"fecha": "2026-09-17", "importe_cent": 2297, "categoria_id": "compras"},
            {"fecha": "2026-09-20", "importe_cent": -500, "categoria_id": None},
            {"fecha": "2026-10-04", "importe_cent": -1499, "categoria_id": "suscripciones"},
        ]
        self.assertEqual(gasto_por_mes(filas, {"super", "compras", "suscripciones"}),
                         {"2026-09": 6737, "2026-10": 1499})


class Genericos(unittest.TestCase):
    def setUp(self):
        self.cuenta = {"id": "caixabank", "owner": XAVI}

    def ext(self, *movs):
        return Extracto("caixabank", "", 0, 0, list(movs))

    def test_es_generico(self):
        self.assertTrue(es_generico("BIZUM  RECIBIDO"))
        self.assertTrue(es_generico("Transfer Inmediata"))
        self.assertFalse(es_generico("Comun"))

    def test_genericos_numerados_y_pendientes(self):
        plan = preparar_importacion(self.ext(
            mov("2026-09-08", "2026-09-08", 5308, "BIZUM RECIBIDO", 100),
            mov("2026-09-09", "2026-09-09", -50000, "Comun", 200),
            mov("2026-09-10", "2026-09-10", -2000, "BIZUM ENVIADO", 300)), self.cuenta, [], set())
        self.assertEqual(plan.sin_regla, ["Comun"])
        self.assertEqual(plan.genericos, [
            {"n": 1, "fecha": "2026-09-08", "comercio": "BIZUM RECIBIDO", "importe_cent": 5308},
            {"n": 2, "fecha": "2026-09-10", "comercio": "BIZUM ENVIADO", "importe_cent": -2000}])
        self.assertEqual([f["categoria_id"] for f in plan.nuevos], [None, None, None])

    def test_asignaciones(self):
        plan = preparar_importacion(self.ext(
            mov("2026-09-08", "2026-09-08", 5308, "BIZUM RECIBIDO", 100),
            mov("2026-09-10", "2026-09-10", -2000, "BIZUM ENVIADO", 300)),
            self.cuenta, [], set(), asignaciones={1: "piso-luz-gas"})
        self.assertEqual(plan.nuevos[0]["categoria_id"], "piso-luz-gas")
        self.assertEqual([g["n"] for g in plan.genericos], [2])

    def test_los_genericos_no_usan_reglas(self):
        reglas = [{"patron": "bizum", "categoria_id": "ocio", "owner": None}]
        plan = preparar_importacion(self.ext(mov("2026-09-08", "2026-09-08", 5308, "BIZUM RECIBIDO", 100)),
                                    self.cuenta, reglas, set())
        self.assertIsNone(plan.nuevos[0]["categoria_id"])
        self.assertEqual(len(plan.genericos), 1)

    def test_bizum_que_devuelve_agua(self):
        previa = [{"fecha": "2026-08-20", "importe_cent": -3540}]
        plan = preparar_importacion(self.ext(
            mov("2026-09-10", "2026-09-10", 3540, "BIZUM RECIBIDO", 100),
            mov("2026-09-11", "2026-09-11", 3540, "BIZUM RECIBIDO", 200)),
            self.cuenta, [], set(), agua_previa=previa)
        self.assertEqual([f["categoria_id"] for f in plan.nuevos], ["piso-agua", None])
        self.assertEqual([g["n"] for g in plan.genericos], [2])

    def test_agua_ya_devuelta_o_fuera_de_plazo_no_cuenta(self):
        previa = [{"fecha": "2026-06-01", "importe_cent": -3540},
                  {"fecha": "2026-08-20", "importe_cent": -2000},
                  {"fecha": "2026-08-25", "importe_cent": 2000}]
        plan = preparar_importacion(self.ext(
            mov("2026-09-10", "2026-09-10", 3540, "BIZUM RECIBIDO", 100),
            mov("2026-09-11", "2026-09-11", 2000, "BIZUM RECIBIDO", 200)),
            self.cuenta, [], set(), agua_previa=previa)
        self.assertEqual([f["categoria_id"] for f in plan.nuevos], [None, None])

    def test_cargo_de_agua_en_el_mismo_extracto(self):
        reglas = [{"patron": "aigues", "categoria_id": "piso-agua", "owner": XAVI}]
        plan = preparar_importacion(self.ext(
            mov("2026-09-02", "2026-09-02", -3540, "AIGUES DE BARCELONA", 100),
            mov("2026-09-06", "2026-09-06", 3540, "BIZUM RECIBIDO", 200)), self.cuenta, reglas, set())
        self.assertEqual([f["categoria_id"] for f in plan.nuevos], ["piso-agua", "piso-agua"])
        self.assertEqual(plan.genericos, [])

    def test_bizum_en_el_dia_45_devuelve_agua_y_en_el_46_no(self):
        previa = [{"fecha": "2026-08-01", "importe_cent": -3540}]
        for fecha, esperado in (("2026-09-15", "piso-agua"), ("2026-09-16", None)):
            plan = preparar_importacion(self.ext(mov(fecha, fecha, 3540, "BIZUM RECIBIDO", 100)),
                                        self.cuenta, [], set(), agua_previa=previa)
            self.assertEqual(plan.nuevos[0]["categoria_id"], esperado, fecha)

    def test_mismo_dia_el_cargo_va_antes_que_la_devolucion(self):
        previa = [{"fecha": "2026-08-20", "importe_cent": 3540},
                  {"fecha": "2026-08-20", "importe_cent": -3540}]
        plan = preparar_importacion(self.ext(mov("2026-09-10", "2026-09-10", 3540, "BIZUM RECIBIDO", 100)),
                                    self.cuenta, [], set(), agua_previa=previa)
        self.assertIsNone(plan.nuevos[0]["categoria_id"])  # el cargo ya estaba devuelto

    def test_numeros_genericos_y_agua_automatica(self):
        previa = [{"fecha": "2026-08-20", "importe_cent": -3540}]
        plan = preparar_importacion(self.ext(
            mov("2026-09-10", "2026-09-10", 3540, "BIZUM RECIBIDO", 100),
            mov("2026-09-11", "2026-09-11", -2000, "BIZUM ENVIADO", 200),
            mov("2026-09-12", "2026-09-12", -900, "TRANSFER INMEDIATA", 300)),
            self.cuenta, [], set(), asignaciones={2: "ocio"}, agua_previa=previa)
        self.assertEqual(plan.numeros_genericos, [1, 2, 3])
        self.assertEqual([g["n"] for g in plan.genericos], [3])
        self.assertEqual(plan.auto_agua, [
            {"n": 1, "fecha": "2026-09-10", "comercio": "BIZUM RECIBIDO", "importe_cent": 3540}])

    def test_sumar_dias(self):
        self.assertEqual(sumar_dias("2026-01-30", 45), "2026-03-16")


if __name__ == "__main__":
    unittest.main()
