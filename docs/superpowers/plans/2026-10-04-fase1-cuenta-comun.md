# Cuentas de casa — Fase 1 (cuenta común) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que Xavi y Andrea vean en el móvil el gasto por categoría y mes de la cuenta común (Revolut), alimentada con los extractos PDF que Xavi pasa a Claude, y puedan recategorizar y apuntar gastos a mano.

**Architecture:** Un script Python (`cuentas.py`, solo stdlib + PyMuPDF) lee el PDF de Revolut, categoriza con reglas y sube a Supabase con la clave de servicio. Una PWA vanilla (GitHub Pages) lee de Supabase con login por usuario; la privacidad la impone RLS en la base de datos. Los cálculos de la app son funciones puras en `calculos.js`, probadas con `node --test`.

**Tech Stack:** Python 3.9 + `unittest` + PyMuPDF (`fitz`, ya instalado) · Supabase (Postgres 15+, Auth, RLS, PostgREST) · HTML/CSS/JS vanilla + `supabase-js` vendorizado · Node 24 (`node --test`) solo para tests · GitHub Pages.

**Spec:** `docs/superpowers/specs/2026-10-04-cuentas-casa-design.md`

## Global Constraints

- Repo: `~/Desktop/NEXO/Otros-proyectos/cuentas/`. Nunca se commitean extractos (`*.pdf`, `*.xlsx`, `*.xls`, `*.csv`) ni `.env` (ya en `.gitignore`).
- Importes siempre en **céntimos enteros**; negativo = sale dinero.
- Gasto de una categoría = −(suma de `importe_cent`) de sus movimientos con `no_es_gasto = false` y categoría con `cuenta_como_gasto = true` o sin categoría. Las devoluciones restan.
- Mes de un movimiento = **fecha de transacción**.
- Datos desde el **1 sept 2026**. Cuenta común: id `comun`, Revolut, IBAN acabado en `3805`.
- Lo que es compartido tiene `owner = null`; lo personal, `owner = <uuid del usuario>`.
- Python: solo stdlib + `fitz`. Tests Python con `unittest` (no hay pytest). Ejecutar desde la raíz del repo: `python3 -m unittest discover -s tests -t .`
- JS sin build ni frameworks, estilo IIFE con `"use strict"` como en `~/Desktop/nexo-ideas`. Assets con `?v=N` sincronizados con `sw.js`.
- Textos de la interfaz en español.
- Fuera de esta fase: CaixaBank, Sabadell, saldos de ahorro/inversión, pestaña Patrimonio.
- Commits terminan con `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Estructura de archivos

```
cuentas/
  CLAUDE.md                     procedimiento para Claude (importar, reglas, tests, publicar)
  .env.example                  plantilla de credenciales del script
  cuentas.py                    CLI: importar / regla / categorias
  importador/
    __init__.py
    modelo.py                   Movimiento, Extracto, FormatoError, huella(), euros()
    revolut.py                  es_extracto_revolut(), parsear()
    categorizar.py              buscar_regla(), preparar_importacion(), gasto_por_mes()
    api.py                      Api (PostgREST con urllib), ApiError
  supabase/
    schema.sql                  tablas, RLS, permisos
    seed.sql                    categorías, cuenta común, reglas iniciales
    perfiles.sql                perfiles de Xavi y Andrea (tras crear los usuarios)
    test_rls.sql                prueba de privacidad (se ejecuta en el SQL Editor)
  tests/
    __init__.py
    fixtures/revolut_paginas.txt   extracto Revolut anonimizado (texto)
    test_revolut.py
    test_categorizar.py
    test_api.py
    calculos.test.js
  index.html  styles.css  manifest.json  sw.js  gen_icons.py  icons/
  supabase-js.min.js            copia de ~/Desktop/nexo-ideas/supabase-js.min.js
  supabase-client.js            crea window.CUENTAS_DB
  calculos.js                   funciones puras (navegador + node)
  datos.js                      window.Datos (Supabase)
  datos-demo.js                 window.DatosDemo (en memoria, index.html?demo=1)
  ui-mes.js  ui-movs.js  ui-nuevo.js   pantallas
  app.js                        arranque, estado, login, pestañas, meses
```

---

### Task 1: Lector del extracto PDF de Revolut

**Files:**
- Create: `importador/__init__.py` (vacío), `importador/modelo.py`, `importador/revolut.py`
- Create: `tests/__init__.py` (vacío), `tests/fixtures/revolut_paginas.txt`, `tests/test_revolut.py`

**Interfaces:**
- Produces:
  - `modelo.FormatoError(Exception)`
  - `modelo.Movimiento(fecha: str, fecha_valor: str, importe_cent: int, comercio: str, descripcion: str, saldo_cent: Optional[int] = None, es_transferencia: bool = False)`
  - `modelo.Extracto(banco: str, iban: str, saldo_inicial_cent: int, saldo_final_cent: int, movimientos: List[Movimiento])`
  - `modelo.huella(cuenta_id: str, m: Movimiento) -> str` (sha1 hex)
  - `modelo.euros(cent: int) -> str` → `"-1.234,56 €"`
  - `revolut.es_extracto_revolut(paginas: List[str]) -> bool`
  - `revolut.parsear(paginas: List[str]) -> Extracto` (lanza `FormatoError`)

- [ ] **Step 1: Crear la fixture anonimizada**

`tests/fixtures/revolut_paginas.txt` (las páginas van separadas por la línea `=== PAGINA ===`; reproduce la estructura real: resumen, pendientes, bloque del titular, cabeceras y pies de página repetidos, devolución y transferencias):

```
Extracto de cuenta conjunta en EUR
 
Generado el 4 oct 2026
Revolut Bank UAB Sucursal En España
© 2026 Revolut Bank UAB Sucursal En España
Revolut.
Página  de 
1
3
Resumen del saldo
Producto
Saldo inicial
Dinero saliente
Dinero entrante
Saldo final
Cuenta (Cuenta Corriente)
33,86€
170,33€
1.622,97€
1.486,50€
Total
33,86€
170,33€
1.622,97€
1.486,50€
El saldo de tu estado de cuenta puede ser diferente al mostrado en tu aplicación.
Pendientes desde el 1 de septiembre de 2026 al 4 de octubre de 2026
Fecha de la 
transacción
Descripción
Dinero saliente
Dinero entrante
3 oct 2026
Ara
86,00€
A Ara, Algaida
Tarjeta: 000000******0001
Nombre de 
la cuenta
TITULAR UNO & 
TITULAR DOS
IBAN
BIC
ES0000000000000000000001
REVOESM2
 
TITULAR UNO
Calle Falsa 1
=== PAGINA ===
Extracto de cuenta conjunta en EUR
 
Generado el 4 oct 2026
Revolut Bank UAB Sucursal En España
Revolut.
Página  de 
2
3
Transacciones de la cuenta desde el 1 de septiembre de 2026 al 4 de octubre de 2026
Fecha de la 
transacción
Fecha valor
Descripción
Dinero saliente
Dinero entrante
Saldo
1 sept 2026
1 sept 2026
Pago de TITULAR UNO
1.500,00€
1.533,86€
Referencia: Comun
De TITULAR UNO, ES0000000000000000000002
1 sept 2026
1 sept 2026
Una recarga de Apple Pay con *0000
100,00€
1.633,86€
De *0000
3 sept 2026
4 sept 2026
Mercadona
62,37€
1.571,49€
A Mercadona Estadi Balea, Palma Mallorc, ESP
Tarjeta: 000000******0001
6 sept 2026
10 sept 2026
H&M
22,97€
1.548,52€
A H M, Barcelona, ESP
Tarjeta: 000000******0002
=== PAGINA ===
Extracto de cuenta conjunta en EUR
 
Generado el 4 oct 2026
Revolut Bank UAB Sucursal En España
Revolut.
Página  de 
3
3
Fecha de la 
transacción
Fecha valor
Descripción
Dinero saliente
Dinero entrante
Saldo
17 sept 2026
18 sept 2026
H&M
22,97€
1.571,49€
De H M, Barcelona, ESP
Tarjeta: 000000******0002
24 sept 2026
24 sept 2026
To Titular Dos
70,00€
1.501,49€
Referencia: Enviada desde Revolut
A Titular Dos, ES0000000000000000000003
4 oct 2026
4 oct 2026
Netflix
14,99€
1.486,50€
A Netflix.com, Madrid, ESP
Tarjeta: 000000******0001
```

- [ ] **Step 2: Escribir los tests que fallan**

`tests/test_revolut.py`:

```python
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
        self.assertEqual([m.es_transferencia for m in self.movs],
                         [True, True, False, False, False, True, False])

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
```

- [ ] **Step 3: Ejecutar y ver que falla**

Run: `cd ~/Desktop/NEXO/Otros-proyectos/cuentas && python3 -m unittest discover -s tests -t . -v`
Expected: ERROR `ModuleNotFoundError: No module named 'importador'` (o `cannot import name`).

- [ ] **Step 4: Implementar `importador/modelo.py`**

```python
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
```

- [ ] **Step 5: Implementar `importador/revolut.py`**

```python
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
PREFIJOS_TRANSFERENCIA = ("Pago de ", "Una recarga de ", "To ", "Transferencia")


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
```

- [ ] **Step 6: Ejecutar y ver que pasa**

Run: `python3 -m unittest discover -s tests -t . -v`
Expected: 12 tests OK.

- [ ] **Step 7: Comprobación con el PDF real (sin commitearlo)**

Run:
```bash
python3 -c "
import fitz; from importador import revolut
p=[x.get_text() for x in fitz.open('/Users/xaviarnedo/Desktop/Extracto Revolut.pdf')]
e=revolut.parsear(p); print(len(e.movimientos), e.iban[-4:], e.saldo_final_cent)"
```
Expected: `56 3805 <saldo final del extracto>`

- [ ] **Step 8: Commit**

```bash
git add importador tests
git commit -m "Lector del extracto PDF de Revolut

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Categorización y plan de importación

**Files:**
- Create: `importador/categorizar.py`, `tests/test_categorizar.py`

**Interfaces:**
- Consumes: `Movimiento`, `Extracto`, `huella` (Task 1).
- Produces:
  - `TRANSFERENCIAS = "transferencias"`
  - `buscar_regla(comercio: str, reglas: List[dict], owner: Optional[str]) -> Optional[str]` — `reglas` son dicts `{"patron", "categoria_id", "owner"}`.
  - `PlanImportacion(nuevos: List[dict], duplicados: int, sin_regla: List[str], saldos: List[dict])`
  - `preparar_importacion(extracto: Extracto, cuenta: dict, reglas: List[dict], huellas_existentes: Set[str]) -> PlanImportacion` — `cuenta` es `{"id", "owner", ...}`. Cada fila de `nuevos` tiene exactamente las claves `cuenta_id, fecha, importe_cent, descripcion, comercio, categoria_id, origen, huella`. Cada fila de `saldos`: `cuenta_id, fecha, saldo_cent`.
  - `gasto_por_mes(filas: List[dict], categorias_gasto: Set[str]) -> Dict[str, int]` — `{"2026-09": 141431}`.

- [ ] **Step 1: Escribir los tests que fallan**

`tests/test_categorizar.py`:

```python
import unittest

from importador.categorizar import TRANSFERENCIAS, buscar_regla, gasto_por_mes, preparar_importacion
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


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Ejecutar y ver que falla**

Run: `python3 -m unittest tests.test_categorizar -v`
Expected: ERROR `No module named 'importador.categorizar'`

- [ ] **Step 3: Implementar `importador/categorizar.py`**

```python
"""Asigna categoría a cada movimiento y decide qué falta por preguntar a Xavi."""
from dataclasses import dataclass
from typing import Dict, List

from .modelo import huella

TRANSFERENCIAS = "transferencias"


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


def preparar_importacion(extracto, cuenta, reglas, huellas_existentes):
    nuevos, duplicados, sin_regla = [], 0, []
    for m in extracto.movimientos:
        h = huella(cuenta["id"], m)
        if h in huellas_existentes:
            duplicados += 1
            continue
        if m.es_transferencia:
            categoria = TRANSFERENCIAS
        else:
            categoria = buscar_regla(m.comercio, reglas, cuenta["owner"])
        if categoria is None and m.comercio not in sin_regla:
            sin_regla.append(m.comercio)
        nuevos.append({"cuenta_id": cuenta["id"], "fecha": m.fecha, "importe_cent": m.importe_cent,
                       "descripcion": m.descripcion, "comercio": m.comercio,
                       "categoria_id": categoria, "origen": "import", "huella": h})

    ultimo_saldo = {}
    for m in extracto.movimientos:  # van en orden de fecha valor: el último del día gana
        if m.saldo_cent is not None:
            ultimo_saldo[m.fecha_valor] = m.saldo_cent
    saldos = [{"cuenta_id": cuenta["id"], "fecha": f, "saldo_cent": s}
              for f, s in sorted(ultimo_saldo.items())]
    return PlanImportacion(nuevos, duplicados, sin_regla, saldos)


def gasto_por_mes(filas, categorias_gasto):
    """Gasto = −(suma de importes) de lo que cuenta como gasto o no tiene categoría."""
    total: Dict[str, int] = {}
    for f in filas:
        if f["categoria_id"] is None or f["categoria_id"] in categorias_gasto:
            mes = f["fecha"][:7]
            total[mes] = total.get(mes, 0) - f["importe_cent"]
    return {mes: v for mes, v in sorted(total.items()) if v}
```

- [ ] **Step 4: Ejecutar y ver que pasa**

Run: `python3 -m unittest discover -s tests -t . -v`
Expected: todos OK (12 de Task 1 + 10 nuevos).

- [ ] **Step 5: Commit**

```bash
git add importador/categorizar.py tests/test_categorizar.py
git commit -m "Categorización por reglas y plan de importación sin duplicados

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Supabase — esquema, semilla, usuarios y prueba de privacidad

Esta tarea mezcla archivos que escribe Claude y pasos que hace **Xavi** en el panel de Supabase (Claude no crea cuentas ni maneja contraseñas ni la clave de servicio).

**Files:**
- Create: `supabase/schema.sql`, `supabase/seed.sql`, `supabase/perfiles.sql`, `supabase/test_rls.sql`

**Interfaces:**
- Produces (lo usan Tasks 4–9):
  - Tablas: `profiles(id, nombre)`, `cuentas(id text, nombre, banco, tipo, owner, iban_final, orden)`, `categorias(id text, nombre, icono, cuenta_como_gasto, orden)`, `movimientos(id uuid, cuenta_id, fecha, importe_cent, descripcion, comercio, categoria_id, nota, no_es_gasto, origen, creado_por, huella, created_at)`, `reglas(id, patron, categoria_id, owner, created_at)` con `unique nulls not distinct (patron, owner)`, `saldos(cuenta_id, fecha, saldo_cent)` con PK `(cuenta_id, fecha)`.
  - Ids de categoría: `super, casa, restaurantes, ocio, transporte, salud, compras, suscripciones, viajes, otros, ingresos, transferencias`.
  - Desde la app, en `movimientos` solo se pueden actualizar `categoria_id, nota, no_es_gasto`.
  - `SUPABASE_URL` y la clave pública (anon / publishable), que Xavi pega en el chat (son públicas por diseño).

- [ ] **Step 1: Escribir `supabase/schema.sql`**

```sql
-- Cuentas de casa — esquema. Ejecutar entero en Supabase → SQL Editor.

create table profiles (
  id uuid primary key references auth.users on delete cascade,
  nombre text not null
);

create table cuentas (
  id text primary key,
  nombre text not null,
  banco text not null,
  tipo text not null check (tipo in ('corriente', 'ahorro', 'inversion')),
  owner uuid references auth.users,          -- null = compartida
  iban_final text,                           -- últimos 4 dígitos, para reconocer el extracto
  orden int not null default 0
);

create table categorias (
  id text primary key,
  nombre text not null,
  icono text not null,
  cuenta_como_gasto boolean not null default true,
  orden int not null default 0
);

create table movimientos (
  id uuid primary key default gen_random_uuid(),
  cuenta_id text not null references cuentas,
  fecha date not null,
  importe_cent integer not null,             -- negativo = sale dinero
  descripcion text not null default '',
  comercio text not null,
  categoria_id text references categorias,
  nota text not null default '',
  no_es_gasto boolean not null default false,
  origen text not null check (origen in ('import', 'manual')),
  creado_por uuid references auth.users default auth.uid(),
  huella text not null unique default ('manual-' || gen_random_uuid()::text),
  created_at timestamptz not null default now()
);
create index movimientos_cuenta_fecha on movimientos (cuenta_id, fecha);

create table reglas (
  id uuid primary key default gen_random_uuid(),
  patron text not null,                      -- se busca contenido en el comercio, sin mayúsculas
  categoria_id text not null references categorias,
  owner uuid references auth.users,          -- null = compartida
  created_at timestamptz not null default now(),
  unique nulls not distinct (patron, owner)
);

create table saldos (
  cuenta_id text not null references cuentas,
  fecha date not null,
  saldo_cent bigint not null,
  primary key (cuenta_id, fecha)
);

-- Privacidad -----------------------------------------------------------------

create function puede_ver_cuenta(c text) returns boolean
language sql stable security definer set search_path = public as $$
  select exists (select 1 from cuentas where id = c and (owner is null or owner = auth.uid()))
$$;

alter table profiles enable row level security;
alter table cuentas enable row level security;
alter table categorias enable row level security;
alter table movimientos enable row level security;
alter table reglas enable row level security;
alter table saldos enable row level security;

create policy "perfiles visibles" on profiles for select to authenticated using (true);
create policy "cuentas propias o compartidas" on cuentas for select to authenticated
  using (owner is null or owner = auth.uid());
create policy "categorias visibles" on categorias for select to authenticated using (true);

create policy "ver movimientos" on movimientos for select to authenticated
  using (puede_ver_cuenta(cuenta_id));
create policy "apuntar a mano" on movimientos for insert to authenticated
  with check (puede_ver_cuenta(cuenta_id) and origen = 'manual' and creado_por = auth.uid());
create policy "editar movimientos" on movimientos for update to authenticated
  using (puede_ver_cuenta(cuenta_id)) with check (puede_ver_cuenta(cuenta_id));
create policy "borrar lo apuntado a mano" on movimientos for delete to authenticated
  using (origen = 'manual' and creado_por = auth.uid());

create policy "ver reglas" on reglas for select to authenticated
  using (owner is null or owner = auth.uid());
create policy "crear reglas" on reglas for insert to authenticated
  with check (owner is null or owner = auth.uid());
create policy "editar reglas" on reglas for update to authenticated
  using (owner is null or owner = auth.uid()) with check (owner is null or owner = auth.uid());

create policy "ver saldos" on saldos for select to authenticated
  using (puede_ver_cuenta(cuenta_id));

-- Permisos: nada para anónimos; desde la app solo se editan 3 columnas de movimientos.
revoke all on all tables in schema public from anon;
revoke execute on function puede_ver_cuenta(text) from public, anon;
grant execute on function puede_ver_cuenta(text) to authenticated;
revoke update on movimientos from authenticated;
grant update (categoria_id, nota, no_es_gasto) on movimientos to authenticated;
```

- [ ] **Step 2: Escribir `supabase/seed.sql`**

```sql
-- Cuentas de casa — datos iniciales. Ejecutar después de schema.sql.

insert into categorias (id, nombre, icono, cuenta_como_gasto, orden) values
  ('super', 'Súper', '🛒', true, 1),
  ('casa', 'Casa', '🏠', true, 2),
  ('restaurantes', 'Restaurantes', '🍽️', true, 3),
  ('ocio', 'Ocio', '🎉', true, 4),
  ('transporte', 'Transporte', '🚗', true, 5),
  ('salud', 'Salud', '💊', true, 6),
  ('compras', 'Compras', '🛍️', true, 7),
  ('suscripciones', 'Suscripciones', '📺', true, 8),
  ('viajes', 'Viajes', '✈️', true, 9),
  ('otros', 'Otros', '📦', true, 10),
  ('ingresos', 'Ingresos', '💶', false, 11),
  ('transferencias', 'Transferencias / Aportaciones', '🔁', false, 12);

insert into cuentas (id, nombre, banco, tipo, owner, iban_final, orden) values
  ('comun', 'Común', 'Revolut', 'corriente', null, '3805', 1);

insert into reglas (patron, categoria_id) values
  ('mercadona', 'super'), ('lidl', 'super'), ('carrefour', 'super'), ('eroski', 'super'),
  ('aldi', 'super'), ('netflix', 'suscripciones'), ('spotify', 'suscripciones'),
  ('hbo', 'suscripciones'), ('disney', 'suscripciones'), ('galp', 'transporte'),
  ('repsol', 'transporte'), ('cepsa', 'transporte'), ('farmacia', 'salud'),
  ('ikea', 'casa'), ('decathlon', 'compras'), ('h&m', 'compras'), ('zara', 'compras'),
  ('primor', 'compras'), ('müller', 'compras'), ('burger king', 'restaurantes'),
  ('mcdonald', 'restaurantes');
```

- [ ] **Step 3: Escribir `supabase/perfiles.sql`**

```sql
-- Ejecutar DESPUÉS de crear los dos usuarios en Authentication → Users.
-- Antes de ejecutar, sustituye EMAIL_DE_XAVI por el email con el que se creó el usuario de Xavi.
insert into profiles (id, nombre)
select id, case when email = 'EMAIL_DE_XAVI' then 'Xavi' else 'Andrea' end
from auth.users
on conflict (id) do nothing;

select nombre, count(*) over () as total from profiles;  -- debe salir Xavi y Andrea, total 2
```

- [ ] **Step 4: Escribir `supabase/test_rls.sql`**

```sql
-- Prueba de privacidad entre Xavi y Andrea. Ejecutar entero en el SQL Editor.
-- RESULTADO ESPERADO: un error que empieza por "RLS_OK". Es intencionado: así se
-- deshacen los datos de prueba. Cualquier error que empiece por "FALLO" es un problema real.
do $$
declare
  xavi uuid := (select id from profiles where nombre = 'Xavi');
  andrea uuid := (select id from profiles where nombre = 'Andrea');
  yo uuid; otro uuid; cuenta_otro text; n int;
begin
  if xavi is null or andrea is null then
    raise exception 'FALLO: faltan los perfiles de Xavi y Andrea (ejecuta perfiles.sql)';
  end if;

  -- Datos de prueba, como administrador
  insert into cuentas (id, nombre, banco, tipo, owner) values
    ('test-xavi', 'Test Xavi', 'test', 'corriente', xavi),
    ('test-andrea', 'Test Andrea', 'test', 'corriente', andrea);
  insert into movimientos (cuenta_id, fecha, importe_cent, comercio, origen, huella) values
    ('test-xavi', '2026-09-01', -100, 'PRIVADO XAVI', 'import', 'test-1'),
    ('test-andrea', '2026-09-01', -100, 'PRIVADO ANDREA', 'import', 'test-2'),
    ('comun', '2026-09-01', -100, 'COMPARTIDO', 'import', 'test-3');
  insert into saldos values ('test-xavi', '2026-09-01', 1), ('test-andrea', '2026-09-01', 1);
  insert into reglas (patron, categoria_id, owner) values
    ('test-xavi', 'otros', xavi), ('test-andrea', 'otros', andrea);

  perform set_config('role', 'authenticated', true);

  for i in 1..2 loop
    if i = 1 then yo := xavi; otro := andrea; cuenta_otro := 'test-andrea';
    else yo := andrea; otro := xavi; cuenta_otro := 'test-xavi'; end if;
    perform set_config('request.jwt.claims',
      json_build_object('sub', yo, 'role', 'authenticated')::text, true);

    select count(*) into n from cuentas where id = cuenta_otro;
    if n <> 0 then raise exception 'FALLO: % ve la cuenta privada del otro', yo; end if;
    select count(*) into n from movimientos where cuenta_id = cuenta_otro;
    if n <> 0 then raise exception 'FALLO: % ve movimientos privados del otro', yo; end if;
    select count(*) into n from saldos where cuenta_id = cuenta_otro;
    if n <> 0 then raise exception 'FALLO: % ve saldos privados del otro', yo; end if;
    select count(*) into n from reglas where owner = otro;
    if n <> 0 then raise exception 'FALLO: % ve reglas privadas del otro', yo; end if;
    select count(*) into n from movimientos where huella = 'test-3';
    if n <> 1 then raise exception 'FALLO: % no ve la cuenta común', yo; end if;

    update movimientos set nota = 'hack' where cuenta_id = cuenta_otro;
    get diagnostics n = row_count;
    if n <> 0 then raise exception 'FALLO: % puede editar movimientos del otro', yo; end if;

    begin
      insert into movimientos (cuenta_id, fecha, importe_cent, comercio, origen)
      values (cuenta_otro, '2026-09-02', -1, 'HACK', 'manual');
      raise exception 'FALLO: % puede apuntar en la cuenta del otro', yo;
    exception when insufficient_privilege then null;
    end;

    begin
      insert into movimientos (cuenta_id, fecha, importe_cent, comercio, origen)
      values ('comun', '2026-09-02', -1, 'HACK', 'import');
      raise exception 'FALLO: % puede crear movimientos "importados"', yo;
    exception when insufficient_privilege then null;
    end;

    begin
      update movimientos set importe_cent = 0 where huella = 'test-3';
      raise exception 'FALLO: % puede cambiar importes', yo;
    exception when insufficient_privilege then null;
    end;

    insert into movimientos (cuenta_id, fecha, importe_cent, comercio, origen)
    values ('comun', '2026-09-02', -1, 'GASTO A MANO', 'manual');
    update movimientos set categoria_id = 'otros', nota = 'ok' where huella = 'test-3';
    get diagnostics n = row_count;
    if n <> 1 then raise exception 'FALLO: % no puede recategorizar la común', yo; end if;
  end loop;

  raise exception 'RLS_OK: todas las comprobaciones pasaron (error intencionado para deshacer los datos de prueba)';
end $$;
```

- [ ] **Step 5: Commit de los SQL**

```bash
git add supabase
git commit -m "Esquema Supabase con RLS, semilla y prueba de privacidad

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 6: [Xavi] Crear el proyecto y aplicar el esquema**

Claude guía a Xavi, paso a paso:
1. supabase.com → New project → nombre `cuentas-casa`, región `West EU`. Si el plan gratuito ya tiene 2 proyectos activos, parar y decidir con Xavi (pausar uno o usar uno existente).
2. SQL Editor → pegar y ejecutar `supabase/schema.sql`; después, `supabase/seed.sql`.
3. Authentication → Users → *Add user* → *Create new user* (marcar *Auto Confirm User*): uno con `el email de Xavi` y otro con el email de Andrea. Cada uno pone su propia contraseña; no se escriben en el chat.
4. Authentication → Sign In / Providers → desactivar *Allow new users to sign up*.
5. SQL Editor → ejecutar `supabase/perfiles.sql`. Expected: 2 filas (Xavi, Andrea).
6. SQL Editor → ejecutar `supabase/test_rls.sql`. Expected: error `RLS_OK: ...`. Si sale `FALLO: ...`, se corrige `schema.sql` (y su copia en la base de datos) antes de seguir.
7. Project Settings → API Keys: Xavi pega en el chat la **URL** y la clave **anon/publishable** (son públicas). La **service_role/secret** NO va al chat: Xavi la pone él mismo en `~/Desktop/NEXO/Otros-proyectos/cuentas/.env` (Task 4, paso 5).

---

### Task 4: Script `cuentas.py` y primera importación real

**Files:**
- Create: `importador/api.py`, `cuentas.py`, `.env.example`, `CLAUDE.md`, `tests/test_api.py`

**Interfaces:**
- Consumes: `revolut.es_extracto_revolut`, `revolut.parsear`, `FormatoError`, `euros` (Task 1); `preparar_importacion`, `gasto_por_mes` (Task 2); tablas del Task 3.
- Produces:
  - `api.Api(url: str, clave: str)` con `.leer(tabla, **filtros_postgrest) -> list` e `.insertar(tabla, filas: list, conflicto: Optional[str] = None, al_chocar: str = "ignore")`; `api.ApiError`.
  - CLI: `python3 cuentas.py importar <pdf> [--sin-categoria]` (sale con código 2 si hay comercios sin regla y no sube nada), `python3 cuentas.py regla <patrón> <categoria_id> [--cuenta <cuenta_id>]`, `python3 cuentas.py categorias`.

- [ ] **Step 1: Test que falla para las cabeceras de la API**

`tests/test_api.py`:

```python
import unittest

from importador.api import Api


class Cabeceras(unittest.TestCase):
    def test_clave_jwt_va_tambien_en_authorization(self):
        api = Api("https://x.supabase.co/", "eyJabc")
        self.assertEqual(api.base, "https://x.supabase.co/rest/v1/")
        self.assertEqual(api.cabeceras["apikey"], "eyJabc")
        self.assertEqual(api.cabeceras["Authorization"], "Bearer eyJabc")

    def test_clave_nueva_sb_solo_en_apikey(self):
        api = Api("https://x.supabase.co", "sb_secret_abc")
        self.assertEqual(api.cabeceras["apikey"], "sb_secret_abc")
        self.assertNotIn("Authorization", api.cabeceras)


if __name__ == "__main__":
    unittest.main()
```

Run: `python3 -m unittest tests.test_api -v` → Expected: ERROR `No module named 'importador.api'`.

- [ ] **Step 2: Implementar `importador/api.py`**

```python
"""Cliente mínimo de la API REST de Supabase (PostgREST). Solo librería estándar.
Se usa con la clave de servicio, que se salta RLS: solo vive en el .env del Mac de Xavi."""
import json
import urllib.error
import urllib.parse
import urllib.request


class ApiError(Exception):
    pass


class Api:
    def __init__(self, url, clave):
        self.base = url.rstrip("/") + "/rest/v1/"
        self.cabeceras = {"apikey": clave, "Content-Type": "application/json"}
        if not clave.startswith("sb_"):  # las claves nuevas (sb_secret_…) no son JWT
            self.cabeceras["Authorization"] = "Bearer " + clave

    def _pedir(self, metodo, ruta, cuerpo=None, extra=None):
        datos = None if cuerpo is None else json.dumps(cuerpo).encode("utf-8")
        cabeceras = dict(self.cabeceras, **(extra or {}))
        req = urllib.request.Request(self.base + ruta, data=datos, method=metodo, headers=cabeceras)
        try:
            with urllib.request.urlopen(req) as r:
                texto = r.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            raise ApiError("%s %s → %s: %s" % (metodo, ruta.split("?")[0], e.code,
                                              e.read().decode("utf-8")))
        return json.loads(texto) if texto else None

    def leer(self, tabla, **filtros):
        """Filtros al estilo PostgREST: leer('movimientos', select='huella', cuenta_id='eq.comun')."""
        return self._pedir("GET", tabla + "?" + urllib.parse.urlencode(filtros))

    def insertar(self, tabla, filas, conflicto=None, al_chocar="ignore"):
        """Todo en una petición = una transacción. al_chocar: 'ignore' deja lo que ya
        existe; 'merge' lo actualiza."""
        ruta = tabla + ("?on_conflict=" + conflicto if conflicto else "")
        prefer = "return=minimal"
        if conflicto:
            prefer += ",resolution=%s-duplicates" % al_chocar
        self._pedir("POST", ruta, filas, {"Prefer": prefer})
```

Run: `python3 -m unittest discover -s tests -t . -v` → Expected: todo OK.

- [ ] **Step 3: Implementar `cuentas.py`**

```python
#!/usr/bin/env python3
"""Importa extractos bancarios a Cuentas de casa (Supabase). Lo ejecuta Claude; ver CLAUDE.md.

  python3 cuentas.py importar <extracto.pdf> [--sin-categoria]
  python3 cuentas.py regla <patrón> <categoria_id> [--cuenta <cuenta_id>]
  python3 cuentas.py categorias
"""
import argparse
import sys
from pathlib import Path

from importador import revolut
from importador.api import Api, ApiError
from importador.categorizar import gasto_por_mes, preparar_importacion
from importador.modelo import FormatoError, euros

LECTORES = [(revolut.es_extracto_revolut, revolut.parsear)]


def leer_env():
    ruta = Path(__file__).parent / ".env"
    if not ruta.exists():
        sys.exit("No encuentro %s. Cópialo de .env.example y rellénalo." % ruta)
    valores = {}
    for linea in ruta.read_text().splitlines():
        linea = linea.strip()
        if linea and not linea.startswith("#") and "=" in linea:
            clave, _, valor = linea.partition("=")
            valores[clave.strip()] = valor.strip()
    for clave in ("SUPABASE_URL", "SUPABASE_SERVICE_KEY"):
        if not valores.get(clave):
            sys.exit("Falta %s en .env (mira .env.example)." % clave)
    return valores


def paginas_pdf(ruta):
    import fitz
    with fitz.open(ruta) as doc:
        return [p.get_text() for p in doc]


def cuenta_por_iban(api, iban):
    for c in api.leer("cuentas", select="id,nombre,owner,iban_final"):
        if c["iban_final"] and iban.endswith(c["iban_final"]):
            return c
    raise FormatoError("Ninguna cuenta tiene un IBAN acabado en %s." % iban[-4:])


def importar(api, ruta, sin_categoria):
    paginas = paginas_pdf(ruta)
    parsear = next((p for detecta, p in LECTORES if detecta(paginas)), None)
    if parsear is None:
        raise FormatoError("No reconozco el banco de " + ruta)
    extracto = parsear(paginas)
    if not extracto.movimientos:
        print("El extracto no tiene movimientos consolidados.")
        return 0
    cuenta = cuenta_por_iban(api, extracto.iban)
    desde = min(m.fecha for m in extracto.movimientos)
    existentes = {f["huella"] for f in api.leer(
        "movimientos", select="huella", cuenta_id="eq." + cuenta["id"], fecha="gte." + desde)}
    reglas = api.leer("reglas", select="patron,categoria_id,owner")
    plan = preparar_importacion(extracto, cuenta, reglas, existentes)

    print("%s · %d movimientos en el extracto · %d nuevos · %d ya estaban"
          % (cuenta["nombre"], len(extracto.movimientos), len(plan.nuevos), plan.duplicados))
    if plan.sin_regla and not sin_categoria:
        print("\nComercios sin regla (NO se ha subido nada):")
        for comercio in plan.sin_regla:
            print("  - " + comercio)
        print('\nCrea las reglas con:  python3 cuentas.py regla "<patrón>" <categoria_id>')
        return 2

    if plan.nuevos:
        api.insertar("movimientos", plan.nuevos, conflicto="huella", al_chocar="ignore")
    if plan.saldos:
        api.insertar("saldos", plan.saldos, conflicto="cuenta_id,fecha", al_chocar="merge")

    gasto = {c["id"] for c in api.leer("categorias", select="id", cuenta_como_gasto="eq.true")}
    print("Subido. Saldo a %s: %s" % (extracto.movimientos[-1].fecha_valor,
                                      euros(extracto.saldo_final_cent)))
    for mes, cent in gasto_por_mes(plan.nuevos, gasto).items():
        print("  Gasto nuevo en %s: %s" % (mes, euros(cent)))
    return 0


def regla(api, patron, categoria_id, cuenta_id):
    if not api.leer("categorias", select="id", id="eq." + categoria_id):
        raise FormatoError("No existe la categoría '%s' (mira: python3 cuentas.py categorias)." % categoria_id)
    cuentas = api.leer("cuentas", select="owner", id="eq." + cuenta_id)
    if not cuentas:
        raise FormatoError("No existe la cuenta '%s'." % cuenta_id)
    api.insertar("reglas", [{"patron": patron.lower(), "categoria_id": categoria_id,
                             "owner": cuentas[0]["owner"]}],
                 conflicto="patron,owner", al_chocar="merge")
    print("Regla: '%s' → %s" % (patron.lower(), categoria_id))
    return 0


def categorias(api):
    for c in api.leer("categorias", select="id,nombre,cuenta_como_gasto", order="orden"):
        print("%-15s %s%s" % (c["id"], c["nombre"], "" if c["cuenta_como_gasto"] else "  (no es gasto)"))
    return 0


def main():
    p = argparse.ArgumentParser(description="Cuentas de casa")
    sub = p.add_subparsers(dest="orden", required=True)
    pi = sub.add_parser("importar")
    pi.add_argument("archivo")
    pi.add_argument("--sin-categoria", action="store_true",
                    help="sube aunque haya comercios sin regla (quedan 'Sin categoría')")
    pr = sub.add_parser("regla")
    pr.add_argument("patron")
    pr.add_argument("categoria_id")
    pr.add_argument("--cuenta", default="comun")
    sub.add_parser("categorias")
    args = p.parse_args()

    env = leer_env()
    api = Api(env["SUPABASE_URL"], env["SUPABASE_SERVICE_KEY"])
    try:
        if args.orden == "importar":
            return importar(api, args.archivo, args.sin_categoria)
        if args.orden == "regla":
            return regla(api, args.patron, args.categoria_id, args.cuenta)
        return categorias(api)
    except (FormatoError, ApiError) as e:
        print("ERROR: %s" % e, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Escribir `.env.example` y `CLAUDE.md`**

`.env.example`:
```
# Copia este archivo a .env (git lo ignora) y rellénalo.
# Supabase → Project Settings → API Keys. La clave de servicio (service_role o sb_secret_…)
# se salta la privacidad: no la pegues nunca en un chat ni la subas a GitHub.
SUPABASE_URL=https://TU-PROYECTO.supabase.co
SUPABASE_SERVICE_KEY=
```

`CLAUDE.md`:
```markdown
# Cuentas de casa

PWA (GitHub Pages) + Supabase para el gasto por categoría/mes de Xavi y Andrea.
Spec: `docs/superpowers/specs/2026-10-04-cuentas-casa-design.md`.

## Cuando Xavi pasa un extracto

1. `python3 cuentas.py importar "<ruta del archivo>"`
2. Si sale "Comercios sin regla": pregunta a Xavi la categoría de cada uno (propón tú una
   para que solo tenga que confirmar) y crea las reglas:
   `python3 cuentas.py regla "<trozo del comercio>" <categoria_id>`
   (`--cuenta <id>` si el extracto es de una cuenta personal). Después repite el paso 1.
3. Resume a Xavi: nuevos, ya estaban, saldo y gasto nuevo por mes.

- Ids de categoría: `python3 cuentas.py categorias`.
- Cadencia: cuentas corrientes cada semana; ahorro/inversión cada mes (fase 3).
- Si el script dice `ERROR: ...` de formato, no fuerces nada: el banco ha cambiado el
  extracto. Adapta el lector en `importador/` con un test nuevo.
- Nunca commitear extractos (`.pdf/.xlsx/.csv`) ni `.env`. La clave de servicio solo vive en `.env`.

## Tests

    python3 -m unittest discover -s tests -t .
    node --test tests/calculos.test.js

## Publicar cambios de la app

Subir `?v=N` en `index.html` y en `sw.js` (`CACHE` y `ASSETS`), commit y `git push`.
GitHub Pages redespliega en ~1 minuto.
```

- [ ] **Step 5: [Xavi] Crear `.env`**

Xavi ejecuta `cp ~/Desktop/NEXO/Otros-proyectos/cuentas/.env.example ~/Desktop/NEXO/Otros-proyectos/cuentas/.env` y pega él mismo la URL y la clave de servicio. Comprobación (Claude): `python3 cuentas.py categorias` → Expected: 12 líneas, de `super` a `transferencias`.

- [ ] **Step 6: Commit**

```bash
git add importador/api.py cuentas.py .env.example CLAUDE.md tests/test_api.py
git commit -m "CLI cuentas.py: importar extractos, crear reglas, listar categorías

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 7: Primera importación real (con Xavi)**

Run: `python3 cuentas.py importar "/Users/xaviarnedo/Desktop/Extracto Revolut.pdf"`
Expected: `Común · 56 movimientos en el extracto · 56 nuevos · 0 ya estaban`, seguido de la lista de comercios sin regla y código de salida 2.

Claude propone una categoría para cada comercio, Xavi confirma o corrige, Claude crea las reglas con `python3 cuentas.py regla ...` y repite. Expected al final: `Subido. Saldo a 2026-10-03: <saldo final del extracto>` y el gasto de sept y oct.

Run otra vez el mismo comando → Expected: `0 nuevos · 56 ya estaban` (los duplicados no entran).

---

### Task 5: Cálculos de la app (`calculos.js`)

**Files:**
- Create: `calculos.js`, `tests/calculos.test.js`

**Interfaces:**
- Produces (`window.Calculos` en el navegador, `module.exports` en node). Los movimientos son objetos con las columnas de la tabla `movimientos`; `cats` es un mapa `{id: categoria}`.
  - `mesDe(fecha) -> "YYYY-MM"`, `moverMes(mes, delta) -> "YYYY-MM"`, `nombreMes(mes) -> "Octubre 2026"`, `fechaCorta("2026-09-12") -> "12 sept"`, `fechaISO(date) -> "YYYY-MM-DD"` (hora local), `ultimosMeses(mes, n) -> [más antiguo, …, mes]`
  - `esGasto(mov, cats) -> bool`
  - `resumenMes(movs, cats, mes) -> { total, filas: [{ categoria_id (null = sin categoría), total, anterior }] }`, con las filas ordenadas de mayor a menor
  - `comparacion(movs, cats, mes, n) -> { pct, meses } | null`
  - `variacion(actual, anterior) -> int % | null`
  - `formatoEuros(cent) -> "-1.234,56 €"`
  - `parseImporte(texto) -> cent > 0 | null`

- [ ] **Step 1: Escribir los tests que fallan**

`tests/calculos.test.js`:

```js
const test = require("node:test");
const assert = require("node:assert");
const C = require("../calculos.js");

const cats = {
  super: { id: "super", cuenta_como_gasto: true },
  compras: { id: "compras", cuenta_como_gasto: true },
  transferencias: { id: "transferencias", cuenta_como_gasto: false }
};
const m = (fecha, importe_cent, categoria_id, extra) =>
  Object.assign({ fecha, importe_cent, categoria_id, no_es_gasto: false }, extra);

test("meses", () => {
  assert.strictEqual(C.mesDe("2026-09-12"), "2026-09");
  assert.strictEqual(C.moverMes("2026-01", -1), "2025-12");
  assert.strictEqual(C.moverMes("2026-11", 3), "2027-02");
  assert.strictEqual(C.nombreMes("2026-10"), "Octubre 2026");
  assert.strictEqual(C.fechaCorta("2026-09-02"), "2 sept");
  assert.strictEqual(C.fechaISO(new Date(2026, 0, 5)), "2026-01-05");
  assert.deepStrictEqual(C.ultimosMeses("2026-02", 3), ["2025-12", "2026-01", "2026-02"]);
});

test("esGasto", () => {
  assert.strictEqual(C.esGasto(m("2026-09-01", -100, "super"), cats), true);
  assert.strictEqual(C.esGasto(m("2026-09-01", -100, null), cats), true);
  assert.strictEqual(C.esGasto(m("2026-09-01", 5000, "transferencias"), cats), false);
  assert.strictEqual(C.esGasto(m("2026-09-01", -100, "super", { no_es_gasto: true }), cats), false);
});

test("resumenMes: devoluciones restan, transferencias fuera, orden y mes anterior", () => {
  const movs = [
    m("2026-08-10", -1000, "super"),
    m("2026-09-01", 50000, "transferencias"),
    m("2026-09-03", -6237, "super"),
    m("2026-09-06", -2297, "compras"),
    m("2026-09-17", 2297, "compras"),
    m("2026-09-20", -500, null),
    m("2026-09-21", -800, "compras")
  ];
  assert.deepStrictEqual(C.resumenMes(movs, cats, "2026-09"), {
    total: 7537,
    filas: [
      { categoria_id: "super", total: 6237, anterior: 1000 },
      { categoria_id: "compras", total: 800, anterior: 0 },
      { categoria_id: null, total: 500, anterior: 0 }
    ]
  });
});

test("comparacion con la media de los meses anteriores que tienen datos", () => {
  const movs = [m("2026-08-01", -1000, "super"), m("2026-09-01", -3000, "super"), m("2026-10-01", -3000, "super")];
  assert.deepStrictEqual(C.comparacion(movs, cats, "2026-10", 3), { pct: 50, meses: 2 });
  assert.strictEqual(C.comparacion(movs, cats, "2026-08", 3), null);
});

test("variacion", () => {
  assert.strictEqual(C.variacion(108, 100), 8);
  assert.strictEqual(C.variacion(50, 0), null);
});

test("formatoEuros", () => {
  assert.strictEqual(C.formatoEuros(-123456), "-1.234,56 €");
  assert.strictEqual(C.formatoEuros(5), "0,05 €");
  assert.strictEqual(C.formatoEuros(100000000), "1.000.000,00 €");
});

test("parseImporte", () => {
  assert.strictEqual(C.parseImporte("12,50"), 1250);
  assert.strictEqual(C.parseImporte("12.5"), 1250);
  assert.strictEqual(C.parseImporte(" 7 € "), 700);
  assert.strictEqual(C.parseImporte("1234,56"), 123456);
  assert.strictEqual(C.parseImporte("1.234"), null);
  assert.strictEqual(C.parseImporte("0"), null);
  assert.strictEqual(C.parseImporte("abc"), null);
});
```

- [ ] **Step 2: Ejecutar y ver que falla**

Run: `node --test tests/calculos.test.js`
Expected: FAIL `Cannot find module '../calculos.js'`

- [ ] **Step 3: Implementar `calculos.js`**

```js
/* Cuentas de casa — cálculos puros (sin DOM ni red). Se usan en la app y en los tests de node. */
(function (raiz) {
  "use strict";
  var MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto",
    "Septiembre", "Octubre", "Noviembre", "Diciembre"];
  var MESES_CORTOS = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sept", "oct", "nov", "dic"];

  function dos(n) { return String(n).padStart(2, "0"); }
  function mesDe(fecha) { return fecha.slice(0, 7); }
  function moverMes(mes, delta) {
    var total = Number(mes.slice(0, 4)) * 12 + Number(mes.slice(5, 7)) - 1 + delta;
    return Math.floor(total / 12) + "-" + dos(total % 12 + 1);
  }
  function nombreMes(mes) { return MESES[Number(mes.slice(5, 7)) - 1] + " " + mes.slice(0, 4); }
  function fechaCorta(fecha) { return Number(fecha.slice(8, 10)) + " " + MESES_CORTOS[Number(fecha.slice(5, 7)) - 1]; }
  function fechaISO(d) { return d.getFullYear() + "-" + dos(d.getMonth() + 1) + "-" + dos(d.getDate()); }
  function ultimosMeses(mes, n) {
    var r = [];
    for (var i = n - 1; i >= 0; i--) r.push(moverMes(mes, -i));
    return r;
  }

  function esGasto(mov, cats) {
    if (mov.no_es_gasto) return false;
    var c = mov.categoria_id && cats[mov.categoria_id];
    return !c || c.cuenta_como_gasto;
  }

  // Gasto = −(suma de importes): las devoluciones (positivas) restan. Clave "" = sin categoría.
  function gastoPorCategoria(movs, cats, mes) {
    var tot = {};
    movs.forEach(function (m) {
      if (mesDe(m.fecha) !== mes || !esGasto(m, cats)) return;
      var k = m.categoria_id || "";
      tot[k] = (tot[k] || 0) - m.importe_cent;
    });
    return tot;
  }

  function resumenMes(movs, cats, mes) {
    var act = gastoPorCategoria(movs, cats, mes);
    var ant = gastoPorCategoria(movs, cats, moverMes(mes, -1));
    var filas = Object.keys(act).filter(function (k) { return act[k] !== 0; }).map(function (k) {
      return { categoria_id: k || null, total: act[k], anterior: ant[k] || 0 };
    }).sort(function (a, b) { return b.total - a.total; });
    var total = filas.reduce(function (s, f) { return s + f.total; }, 0);
    return { total: total, filas: filas };
  }

  // Compara con la media de los n meses anteriores que tienen algún movimiento.
  function comparacion(movs, cats, mes, n) {
    var conDatos = {};
    movs.forEach(function (m) { conDatos[mesDe(m.fecha)] = true; });
    var totales = [];
    for (var i = 1; i <= n; i++) {
      var p = moverMes(mes, -i);
      if (conDatos[p]) totales.push(resumenMes(movs, cats, p).total);
    }
    if (!totales.length) return null;
    var media = totales.reduce(function (s, t) { return s + t; }, 0) / totales.length;
    if (media <= 0) return null;
    return { pct: Math.round((resumenMes(movs, cats, mes).total - media) / media * 100), meses: totales.length };
  }

  function variacion(actual, anterior) {
    if (!anterior) return null;
    return Math.round((actual - anterior) / anterior * 100);
  }

  function formatoEuros(cent) {
    var abs = Math.abs(cent);
    var enteros = String(Math.floor(abs / 100)).replace(/\B(?=(\d{3})+(?!\d))/g, ".");
    return (cent < 0 ? "-" : "") + enteros + "," + dos(abs % 100) + " €";
  }

  // Acepta "12", "12,5", "12.50", "7 €". Sin separador de miles para evitar ambigüedad.
  function parseImporte(texto) {
    var t = String(texto).replace(/\s|€/g, "");
    if (!/^\d+([.,]\d{1,2})?$/.test(t)) return null;
    var cent = Math.round(parseFloat(t.replace(",", ".")) * 100);
    return cent > 0 ? cent : null;
  }

  var api = {
    mesDe: mesDe, moverMes: moverMes, nombreMes: nombreMes, fechaCorta: fechaCorta, fechaISO: fechaISO,
    ultimosMeses: ultimosMeses, esGasto: esGasto, resumenMes: resumenMes, comparacion: comparacion,
    variacion: variacion, formatoEuros: formatoEuros, parseImporte: parseImporte
  };
  if (typeof module === "object" && module.exports) module.exports = api;
  else raiz.Calculos = api;
})(this);
```

- [ ] **Step 4: Ejecutar y ver que pasa**

Run: `node --test tests/calculos.test.js`
Expected: `# pass 7`, `# fail 0`

- [ ] **Step 5: Commit**

```bash
git add calculos.js tests/calculos.test.js
git commit -m "Cálculos de la app: gasto por categoría/mes, comparación, formato

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Esqueleto de la PWA (login, pestañas, meses, modo demo)

**Files:**
- Create: `index.html`, `styles.css`, `manifest.json`, `sw.js`, `gen_icons.py`, `icons/*`, `supabase-client.js`, `datos.js`, `datos-demo.js`, `app.js`, `.nojekyll` (vacío), `.claude/launch.json`
- Copy: `~/Desktop/nexo-ideas/supabase-js.min.js` → `supabase-js.min.js`
- Create (vacíos de momento, se rellenan en Tasks 7–9): `ui-mes.js`, `ui-movs.js`, `ui-nuevo.js`, cada uno con solo su stub:
  - `ui-mes.js`: `window.UiMes = { pintar: function () {} };`
  - `ui-movs.js`: `window.UiMovs = { abrir: function () {}, pintarSiVisible: function () {} };`
  - `ui-nuevo.js`: `// Task 9`

**Interfaces:**
- Consumes: `window.Calculos` (Task 5); `SUPABASE_URL` y la clave pública (Task 3, paso 6.7).
- Produces:
  - `window.Datos` / `window.DatosDemo`, con la misma forma: `usuario() -> Promise<user|null>`, `entrar(email, pass)`, `salir()`, `cuentas()`, `categorias()`, `movimientos(cuentaIds, desde, hastaExclusivo) -> Promise<mov[]>` (fecha desc), `actualizarMovimiento(id, cambios)`, `recategorizarComercio(cuentaId, comercio, categoriaId)`, `guardarRegla(patron, categoriaId, owner)`, `crearMovimiento(fila)`, `borrarMovimiento(id)`.
  - `window.App`: `D` (Datos activo), `estado { usuario, cuentas, cats, catsLista, grupo, mes, movs }`, `gruposVisibles()`, `cuentasDelGrupo(grupoId)`, `pintarPestanas()`, `recargar() -> Promise`, `pintar()`, `aviso(texto)`, `chips(contenedor, seleccionadaId, lista?)`.
  - IDs del DOM que usan las Tasks 7–9 (todos en `index.html`, abajo).

- [ ] **Step 1: Copiar supabase-js y escribir `supabase-client.js`**

```bash
cp ~/Desktop/nexo-ideas/supabase-js.min.js ~/Desktop/NEXO/Otros-proyectos/cuentas/supabase-js.min.js
```

`supabase-client.js` (con los valores que Xavi pegó en el Task 3):
```js
/* Cuentas de casa — cliente Supabase. La clave pública lo es por diseño: protege RLS. */
(function () {
  "use strict";
  var SUPABASE_URL = "https://TU-PROYECTO.supabase.co";   // ← Task 3, paso 6.7
  var SUPABASE_CLAVE_PUBLICA = "PEGAR_AQUI";               // ← Task 3, paso 6.7 (anon / publishable)
  window.CUENTAS_DB = window.supabase.createClient(SUPABASE_URL, SUPABASE_CLAVE_PUBLICA);
})();
```
Sustituir los dos valores por los reales antes de commitear (comprobar con `grep -c PEGAR_AQUI supabase-client.js` → `0`).

- [ ] **Step 2: Escribir `datos.js`**

```js
/* Cuentas de casa — acceso a Supabase. Todo devuelve promesas; los errores se lanzan como Error. */
(function () {
  "use strict";
  var db = window.CUENTAS_DB;
  function ok(r) { if (r.error) throw new Error(r.error.message); return r.data; }

  function movimientos(cuentaIds, desde, hasta) {
    var filas = [];
    function pagina(inicio) {
      return db.from("movimientos").select("*").in("cuenta_id", cuentaIds)
        .gte("fecha", desde).lt("fecha", hasta)
        .order("fecha", { ascending: false }).order("created_at", { ascending: false })
        .range(inicio, inicio + 999).then(ok).then(function (d) {
          filas = filas.concat(d);
          return d.length === 1000 ? pagina(inicio + 1000) : filas;
        });
    }
    return pagina(0);
  }

  window.Datos = {
    usuario: function () {
      return db.auth.getSession().then(function (r) { return r.data.session ? r.data.session.user : null; });
    },
    entrar: function (email, pass) { return db.auth.signInWithPassword({ email: email, password: pass }).then(ok); },
    salir: function () { return db.auth.signOut(); },
    cuentas: function () { return db.from("cuentas").select("*").order("orden").then(ok); },
    categorias: function () { return db.from("categorias").select("*").order("orden").then(ok); },
    movimientos: movimientos,
    actualizarMovimiento: function (id, cambios) {
      return db.from("movimientos").update(cambios).eq("id", id).then(ok);
    },
    recategorizarComercio: function (cuentaId, comercio, categoriaId) {
      return db.from("movimientos").update({ categoria_id: categoriaId })
        .eq("cuenta_id", cuentaId).eq("comercio", comercio).then(ok);
    },
    guardarRegla: function (patron, categoriaId, owner) {
      return db.from("reglas").upsert({ patron: patron, categoria_id: categoriaId, owner: owner },
        { onConflict: "patron,owner" }).then(ok);
    },
    crearMovimiento: function (fila) { return db.from("movimientos").insert(fila).then(ok); },
    borrarMovimiento: function (id) { return db.from("movimientos").delete().eq("id", id).then(ok); }
  };
})();
```

- [ ] **Step 3: Escribir `datos-demo.js`**

```js
/* Cuentas de casa — datos de ejemplo en memoria para ver la app sin Supabase: index.html?demo=1 */
(function () {
  "use strict";
  var C = window.Calculos;
  var YO = { id: "demo-xavi", email: "demo@ejemplo.com" };
  var cuentas = [
    { id: "comun", nombre: "Común", banco: "Revolut", tipo: "corriente", owner: null, orden: 1 },
    { id: "xavi", nombre: "Xavi", banco: "CaixaBank", tipo: "corriente", owner: "demo-xavi", orden: 2 }
  ];
  var categorias = [
    ["super", "Súper", "🛒", true], ["casa", "Casa", "🏠", true], ["restaurantes", "Restaurantes", "🍽️", true],
    ["ocio", "Ocio", "🎉", true], ["transporte", "Transporte", "🚗", true], ["salud", "Salud", "💊", true],
    ["compras", "Compras", "🛍️", true], ["suscripciones", "Suscripciones", "📺", true],
    ["viajes", "Viajes", "✈️", true], ["otros", "Otros", "📦", true], ["ingresos", "Ingresos", "💶", false],
    ["transferencias", "Transferencias / Aportaciones", "🔁", false]
  ].map(function (c, i) { return { id: c[0], nombre: c[1], icono: c[2], cuenta_como_gasto: c[3], orden: i + 1 }; });
  var plantilla = [
    ["Mercadona", "super", -6237], ["Mercadona", "super", -4706], ["Netflix", "suscripciones", -1499],
    ["Galp", "transporte", -2000], ["Don Pedro Cafe Bistro", "restaurantes", -4730], ["H&M", "compras", -2297],
    ["Farmacia Magdalena", "salud", -320], ["Bar nuevo", null, -850], ["Pago de Xavi", "transferencias", 50000]
  ];
  var movs = [], n = 0;
  var mesActual = C.mesDe(C.fechaISO(new Date()));
  [3, 2, 1, 0].forEach(function (atras, i) {
    var mes = C.moverMes(mesActual, -atras);
    plantilla.forEach(function (p, j) {
      ["comun", "xavi"].forEach(function (cuenta, k) {
        n++;
        movs.push({ id: "m" + n, cuenta_id: cuenta, fecha: mes + "-" + String(1 + (j * 3) % 27).padStart(2, "0"),
          importe_cent: Math.round(p[2] * (1 + 0.1 * i) * (k ? 0.5 : 1)), comercio: p[0],
          descripcion: p[0] + " · Palma", categoria_id: p[1], nota: "", no_es_gasto: false,
          origen: "import", creado_por: null });
      });
    });
  });

  function ok(v) { return Promise.resolve(v === undefined ? null : JSON.parse(JSON.stringify(v))); }

  window.DatosDemo = {
    usuario: function () { return ok(YO); },
    entrar: function () { return ok(YO); },
    salir: function () { return ok(); },
    cuentas: function () { return ok(cuentas); },
    categorias: function () { return ok(categorias); },
    movimientos: function (ids, desde, hasta) {
      return ok(movs.filter(function (m) {
        return ids.indexOf(m.cuenta_id) >= 0 && m.fecha >= desde && m.fecha < hasta;
      }).sort(function (a, b) { return a.fecha < b.fecha ? 1 : a.fecha > b.fecha ? -1 : 0; }));
    },
    actualizarMovimiento: function (id, cambios) {
      Object.assign(movs.find(function (m) { return m.id === id; }), cambios);
      return ok();
    },
    recategorizarComercio: function (cuentaId, comercio, categoriaId) {
      movs.forEach(function (m) { if (m.cuenta_id === cuentaId && m.comercio === comercio) m.categoria_id = categoriaId; });
      return ok();
    },
    guardarRegla: function () { return ok(); },
    crearMovimiento: function (fila) {
      n++;
      movs.push(Object.assign({ id: "m" + n, descripcion: "", nota: "", no_es_gasto: false }, fila));
      return ok();
    },
    borrarMovimiento: function (id) {
      movs = movs.filter(function (m) { return m.id !== id; });
      return ok();
    }
  };
})();
```

- [ ] **Step 4: Escribir `index.html`**

```html
<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <meta name="theme-color" content="#0f766e">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-title" content="Cuentas">
  <title>Cuentas de casa</title>
  <link rel="manifest" href="manifest.json">
  <link rel="apple-touch-icon" href="icons/apple-touch-icon.png">
  <link rel="stylesheet" href="styles.css?v=1">
</head>
<body>
  <section id="login" class="login" hidden>
    <h1>Cuentas de casa</h1>
    <form id="login-form">
      <input id="login-email" type="email" autocomplete="username" placeholder="Email" required>
      <input id="login-pass" type="password" autocomplete="current-password" placeholder="Contraseña" required>
      <button type="submit" class="boton">Entrar</button>
      <p id="login-error" class="error" hidden>Email o contraseña incorrectos.</p>
    </form>
  </section>

  <div id="app" hidden>
    <header class="barra">
      <nav id="pestanas" class="pestanas"></nav>
      <span id="demo" class="etiqueta" hidden>Demo</span>
      <button id="salir" class="enlace" type="button">Salir</button>
    </header>
    <div class="selector-mes">
      <button id="mes-ant" type="button" aria-label="Mes anterior">‹</button>
      <h1 id="mes-nombre"></h1>
      <button id="mes-sig" type="button" aria-label="Mes siguiente">›</button>
    </div>

    <main id="vista-mes">
      <p id="sin-cuentas" class="vacio" hidden>Todavía no tienes cuentas.</p>
      <div class="total">
        <span id="total"></span>
        <small id="comparacion"></small>
      </div>
      <div id="grafico" class="grafico"></div>
      <ul id="lista-categorias" class="lista"></ul>
      <button id="ver-todos" class="enlace" type="button">Ver todos los movimientos</button>
    </main>

    <main id="vista-movs" hidden>
      <div class="cabecera-movs">
        <button id="volver" class="enlace" type="button">‹ Volver</button>
        <strong id="titulo-movs"></strong>
      </div>
      <input id="buscar" type="search" placeholder="Buscar">
      <ul id="lista-movs" class="lista"></ul>
    </main>

    <button id="fab" class="fab" type="button" aria-label="Apuntar gasto">+</button>
  </div>

  <dialog id="hoja-mov" class="hoja">
    <form id="ed-form">
      <h2 id="ed-comercio"></h2>
      <p id="ed-detalle" class="detalle"></p>
      <div id="ed-cats" class="chips"></div>
      <label id="ed-todos-fila" class="check"><input id="ed-todos" type="checkbox"> <span id="ed-todos-txt"></span></label>
      <textarea id="ed-nota" rows="2" placeholder="Nota"></textarea>
      <label class="check"><input id="ed-no-gasto" type="checkbox"> No es un gasto (no cuenta en el total)</label>
      <div class="acciones">
        <button id="ed-borrar" class="boton peligro" type="button">Borrar</button>
        <button id="ed-cancelar" class="boton secundario" type="button">Cancelar</button>
        <button class="boton" type="submit">Guardar</button>
      </div>
    </form>
  </dialog>

  <dialog id="hoja-nuevo" class="hoja">
    <form id="nu-form">
      <h2>Apuntar a mano</h2>
      <input id="nu-importe" class="importe-grande" inputmode="decimal" placeholder="0,00 €" autocomplete="off">
      <div id="nu-cats" class="chips"></div>
      <select id="nu-cuenta"></select>
      <input id="nu-fecha" type="date">
      <input id="nu-nota" placeholder="Nota (opcional)">
      <p id="nu-error" class="error" hidden></p>
      <div class="acciones">
        <button id="nu-cancelar" class="boton secundario" type="button">Cancelar</button>
        <button class="boton" type="submit">Guardar</button>
      </div>
    </form>
  </dialog>

  <div id="aviso" class="aviso" hidden></div>

  <script src="supabase-js.min.js?v=1"></script>
  <script src="supabase-client.js?v=1"></script>
  <script src="calculos.js?v=1"></script>
  <script src="datos.js?v=1"></script>
  <script src="datos-demo.js?v=1"></script>
  <script src="ui-mes.js?v=1"></script>
  <script src="ui-movs.js?v=1"></script>
  <script src="ui-nuevo.js?v=1"></script>
  <script src="app.js?v=1"></script>
</body>
</html>
```

- [ ] **Step 5: Escribir `styles.css`**

```css
:root {
  --fondo: #f6f5f2; --tarjeta: #ffffff; --texto: #1c1a17; --suave: #6b665e; --linea: #e7e3dc;
  --acento: #0f766e; --acento-suave: #ccfbf1; --sube: #b42318; --baja: #067647;
  color-scheme: light dark;
}
@media (prefers-color-scheme: dark) {
  :root { --fondo: #141312; --tarjeta: #1f1d1b; --texto: #f2efe9; --suave: #a39d93; --linea: #34312d;
          --acento: #2dd4bf; --acento-suave: #134e4a; --sube: #f97066; --baja: #47cd89; }
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--fondo); color: var(--texto);
       font: 16px/1.4 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
       padding: env(safe-area-inset-top) 16px calc(96px + env(safe-area-inset-bottom)); }
button { font: inherit; color: inherit; cursor: pointer; }
input, select, textarea { font: inherit; width: 100%; padding: 12px; border: 1px solid var(--linea);
  border-radius: 12px; background: var(--tarjeta); color: var(--texto); margin: 6px 0; }
.boton { background: var(--acento); color: #fff; border: 0; border-radius: 12px; padding: 12px 18px; font-weight: 600; }
.boton.secundario { background: transparent; color: var(--texto); border: 1px solid var(--linea); }
.boton.peligro { background: transparent; color: var(--sube); border: 1px solid var(--sube); margin-right: auto; }
.enlace { background: none; border: 0; color: var(--acento); padding: 8px 0; }
.error { color: var(--sube); }
.vacio { color: var(--suave); text-align: center; padding: 24px 0; }

.login { max-width: 360px; margin: 20vh auto 0; text-align: center; }
.login .boton { width: 100%; margin-top: 8px; }

.barra { display: flex; align-items: center; gap: 8px; padding: 12px 0; }
.pestanas { display: flex; gap: 4px; background: var(--linea); padding: 3px; border-radius: 12px; flex: 1; }
.pestana { flex: 1; border: 0; background: transparent; padding: 8px; border-radius: 9px; }
.pestana.activa { background: var(--tarjeta); font-weight: 600; box-shadow: 0 1px 2px rgba(0,0,0,.08); }
.etiqueta { font-size: 12px; background: var(--acento-suave); color: var(--acento); padding: 2px 8px; border-radius: 99px; }

.selector-mes { display: flex; align-items: center; justify-content: space-between; }
.selector-mes h1 { font-size: 20px; margin: 0; }
.selector-mes button { background: none; border: 0; font-size: 28px; padding: 4px 14px; color: var(--acento); }

.total { text-align: center; padding: 16px 0 8px; }
.total span { display: block; font-size: 40px; font-weight: 700; letter-spacing: -0.02em; }
.total small { color: var(--suave); }

.grafico { display: flex; align-items: flex-end; gap: 8px; height: 90px; margin: 8px 0 16px; }
.barra-mes { flex: 1; height: 100%; display: flex; flex-direction: column; justify-content: flex-end;
  align-items: center; gap: 4px; background: none; border: 0; padding: 0; }
.barra-mes span { width: 100%; background: var(--linea); border-radius: 6px 6px 2px 2px; min-height: 2px; }
.barra-mes.actual span { background: var(--acento); }
.barra-mes small { color: var(--suave); font-size: 12px; }

.lista { list-style: none; margin: 0; padding: 0; background: var(--tarjeta); border-radius: 16px; overflow: hidden; }
.lista li { display: flex; align-items: center; gap: 12px; padding: 12px 14px; border-bottom: 1px solid var(--linea); cursor: pointer; }
.lista li:last-child { border-bottom: 0; }
.lista li.vacio { display: block; cursor: default; }
.icono { font-size: 22px; width: 28px; text-align: center; }
.cuerpo { flex: 1; min-width: 0; }
.linea { display: flex; justify-content: space-between; gap: 8px; }
.nombre { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.cuerpo small { display: block; color: var(--suave); font-size: 13px; }
.pista { height: 6px; background: var(--linea); border-radius: 3px; margin-top: 6px; }
.pista i { display: block; height: 100%; background: var(--acento); border-radius: 3px; }
.var { font-size: 13px; width: 52px; text-align: right; color: var(--suave); }
.var.sube { color: var(--sube); }
.var.baja { color: var(--baja); }
.importe { font-variant-numeric: tabular-nums; white-space: nowrap; }
.importe.positivo { color: var(--baja); }
.apagado { opacity: .5; }
#ver-todos { display: block; margin: 12px auto; }

.cabecera-movs { display: flex; align-items: center; gap: 12px; }

.fab { position: fixed; right: 20px; bottom: calc(20px + env(safe-area-inset-bottom)); width: 60px; height: 60px;
  border-radius: 50%; border: 0; background: var(--acento); color: #fff; font-size: 32px;
  box-shadow: 0 6px 16px rgba(0,0,0,.2); }

.hoja { border: 0; border-radius: 20px 20px 0 0; width: 100%; max-width: 560px; margin: auto auto 0;
  padding: 20px 16px calc(20px + env(safe-area-inset-bottom)); background: var(--fondo); color: var(--texto);
  max-height: 90vh; }
.hoja::backdrop { background: rgba(0,0,0,.4); }
.hoja h2 { margin: 0 0 4px; font-size: 20px; }
.detalle { color: var(--suave); font-size: 13px; margin: 0 0 12px; word-break: break-word; }
.chips { display: flex; flex-wrap: wrap; gap: 6px; margin: 8px 0; }
.chip { border: 1px solid var(--linea); background: var(--tarjeta); border-radius: 99px; padding: 8px 12px; font-size: 14px; }
.chip.elegida { background: var(--acento); color: #fff; border-color: var(--acento); }
.check { display: flex; align-items: center; gap: 8px; margin: 8px 0; font-size: 15px; }
.check input { width: auto; margin: 0; }
.acciones { display: flex; justify-content: flex-end; gap: 8px; margin-top: 12px; }
.importe-grande { font-size: 32px; text-align: center; font-weight: 700; }

.aviso { position: fixed; left: 16px; right: 16px; bottom: calc(96px + env(safe-area-inset-bottom));
  background: var(--texto); color: var(--fondo); padding: 12px 16px; border-radius: 12px; text-align: center; }
```

- [ ] **Step 6: Escribir `app.js`**

```js
/* Cuentas de casa — arranque, estado, login, pestañas y navegación de meses. */
(function () {
  "use strict";
  var C = window.Calculos;
  var demo = /[?&]demo=1/.test(location.search);
  var D = demo ? window.DatosDemo : window.Datos;
  function $(id) { return document.getElementById(id); }

  var App = window.App = {
    D: D,
    estado: { usuario: null, cuentas: [], cats: {}, catsLista: [], grupo: null,
              mes: C.mesDe(C.fechaISO(new Date())), movs: [] },
    gruposVisibles: gruposVisibles, cuentasDelGrupo: cuentasDelGrupo, pintarPestanas: pintarPestanas,
    recargar: recargar, pintar: pintar, aviso: aviso, chips: chips
  };

  function cuentasDelGrupo(grupo) {
    var e = App.estado;
    return e.cuentas.filter(function (c) {
      return c.tipo === "corriente" && (grupo === "comun" ? c.owner === null : c.owner === e.usuario.id);
    });
  }
  function gruposVisibles() {
    return [{ id: "comun", nombre: "Común" }, { id: "mia", nombre: "Mía" }]
      .filter(function (g) { return cuentasDelGrupo(g.id).length > 0; });
  }

  function arrancar() {
    $("demo").hidden = !demo;
    D.usuario().then(function (u) {
      if (u) return entrarEnApp(u);
      $("login").hidden = false;
    }).catch(errorFatal);
  }

  $("login-form").addEventListener("submit", function (ev) {
    ev.preventDefault();
    $("login-error").hidden = true;
    D.entrar($("login-email").value.trim(), $("login-pass").value)
      .then(function () { return D.usuario(); })
      .then(entrarEnApp)
      .catch(function () { $("login-error").hidden = false; });
  });

  function entrarEnApp(u) {
    var e = App.estado;
    e.usuario = u;
    return Promise.all([D.cuentas(), D.categorias()]).then(function (r) {
      e.cuentas = r[0];
      e.catsLista = r[1];
      e.cats = {};
      r[1].forEach(function (c) { e.cats[c.id] = c; });
      var grupos = gruposVisibles();
      e.grupo = grupos.length ? grupos[0].id : null;
      $("login").hidden = true;
      $("app").hidden = false;
      pintarPestanas();
      return recargar();
    }).catch(errorFatal);
  }

  function pintarPestanas() {
    var nav = $("pestanas");
    nav.innerHTML = "";
    gruposVisibles().forEach(function (g) {
      var b = document.createElement("button");
      b.type = "button";
      b.className = "pestana" + (g.id === App.estado.grupo ? " activa" : "");
      b.textContent = g.nombre;
      b.addEventListener("click", function () { App.estado.grupo = g.id; pintarPestanas(); recargar(); });
      nav.appendChild(b);
    });
  }

  // Carga el mes elegido y los 6 anteriores (gráfico, comparación y variación por categoría).
  function recargar() {
    var e = App.estado;
    $("sin-cuentas").hidden = !!e.grupo;
    if (!e.grupo) { e.movs = []; pintar(); return Promise.resolve(); }
    var ids = cuentasDelGrupo(e.grupo).map(function (c) { return c.id; });
    return D.movimientos(ids, C.moverMes(e.mes, -6) + "-01", C.moverMes(e.mes, 1) + "-01")
      .then(function (movs) { e.movs = movs; pintar(); })
      .catch(function (err) { aviso("No se pudieron cargar los datos: " + err.message); });
  }

  function pintar() {
    $("mes-nombre").textContent = C.nombreMes(App.estado.mes);
    window.UiMes.pintar();
    window.UiMovs.pintarSiVisible();
  }

  // Botones de categoría: se marca uno; el elegido se lee con contenedor.querySelector(".elegida").dataset.id
  function chips(cont, seleccionada, lista) {
    cont.innerHTML = "";
    (lista || App.estado.catsLista).forEach(function (c) {
      var b = document.createElement("button");
      b.type = "button";
      b.className = "chip" + (c.id === seleccionada ? " elegida" : "");
      b.dataset.id = c.id;
      b.textContent = c.icono + " " + c.nombre;
      b.addEventListener("click", function () {
        var antes = cont.querySelector(".elegida");
        if (antes) antes.classList.remove("elegida");
        b.classList.add("elegida");
      });
      cont.appendChild(b);
    });
  }

  function aviso(texto) {
    var a = $("aviso");
    a.textContent = texto;
    a.hidden = false;
    clearTimeout(aviso.t);
    aviso.t = setTimeout(function () { a.hidden = true; }, 4000);
  }
  function errorFatal(err) { aviso("Error: " + err.message); }

  $("mes-ant").addEventListener("click", function () { App.estado.mes = C.moverMes(App.estado.mes, -1); recargar(); });
  $("mes-sig").addEventListener("click", function () { App.estado.mes = C.moverMes(App.estado.mes, 1); recargar(); });
  $("salir").addEventListener("click", function () { D.salir().then(function () { location.reload(); }); });

  if ("serviceWorker" in navigator && !demo) navigator.serviceWorker.register("sw.js");
  arrancar();
})();
```

- [ ] **Step 7: Escribir `manifest.json`, `sw.js`, `gen_icons.py` y generar los iconos**

`manifest.json`:
```json
{
  "name": "Cuentas de casa",
  "short_name": "Cuentas",
  "description": "Gasto por categoría y mes de la casa.",
  "lang": "es",
  "start_url": "./index.html",
  "scope": "./",
  "display": "standalone",
  "orientation": "portrait",
  "background_color": "#f6f5f2",
  "theme_color": "#0f766e",
  "icons": [
    { "src": "icons/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any" },
    { "src": "icons/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any" },
    { "src": "icons/icon-maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable" }
  ]
}
```

`sw.js`:
```js
var CACHE = "cuentas-v1";
// Esqueleto de la app. Mantener en sync con los <script>/<link> de index.html (incluido ?v=N).
var ASSETS = [
  "./", "./index.html", "./styles.css?v=1", "./manifest.json",
  "./icons/icon-192.png", "./icons/icon-512.png",
  "./supabase-js.min.js?v=1", "./supabase-client.js?v=1", "./calculos.js?v=1", "./datos.js?v=1",
  "./datos-demo.js?v=1", "./ui-mes.js?v=1", "./ui-movs.js?v=1", "./ui-nuevo.js?v=1", "./app.js?v=1"
];

self.addEventListener("install", function (e) {
  e.waitUntil(caches.open(CACHE).then(function (c) {
    return Promise.all(ASSETS.map(function (u) { return c.add(u).catch(function () {}); }));
  }).then(function () { return self.skipWaiting(); }));
});

self.addEventListener("activate", function (e) {
  e.waitUntil(caches.keys().then(function (keys) {
    return Promise.all(keys.filter(function (k) { return k !== CACHE; }).map(function (k) { return caches.delete(k); }));
  }).then(function () { return self.clients.claim(); }));
});

// Solo se cachea el esqueleto propio; las peticiones a Supabase (otro origen) van siempre a la red.
self.addEventListener("fetch", function (e) {
  if (e.request.method !== "GET") return;
  if (new URL(e.request.url).origin !== self.location.origin) return;
  e.respondWith(caches.match(e.request).then(function (r) { return r || fetch(e.request); }));
});
```

`gen_icons.py`:
```python
#!/usr/bin/env python3
"""Genera los iconos PWA (icons/): dos monedas solapadas sobre fondo verde azulado.
Ejecuta: python3 gen_icons.py"""
from pathlib import Path

from PIL import Image, ImageDraw

FONDO = (15, 118, 110)
MONEDA_ATRAS = (204, 251, 241)
MONEDA_DELANTE = (247, 245, 242)


def icono(tam):
    img = Image.new("RGBA", (tam, tam), FONDO + (255,))
    d = ImageDraw.Draw(img)
    r, cy = tam * 0.22, tam * 0.5
    for cx, color in ((tam * 0.40, MONEDA_ATRAS), (tam * 0.60, MONEDA_DELANTE)):
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color, outline=FONDO, width=max(2, tam // 40))
    return img


Path("icons").mkdir(exist_ok=True)
icono(192).convert("RGB").save("icons/icon-192.png")
icono(512).convert("RGB").save("icons/icon-512.png")
icono(512).save("icons/icon-maskable-512.png")
icono(180).convert("RGB").save("icons/apple-touch-icon.png")
print("iconos generados en icons/.")
```

Run: `cd ~/Desktop/NEXO/Otros-proyectos/cuentas && python3 gen_icons.py && touch .nojekyll`
Expected: `iconos generados en icons/.`

- [ ] **Step 8: Configurar la vista previa**

Comprobar si existe `~/Desktop/.claude/launch.json` (el directorio de trabajo de la sesión es `~/Desktop`). Si existe, añadir la configuración a su lista; si no, crearlo:
```json
{
  "version": "0.0.1",
  "configurations": [
    {
      "name": "cuentas",
      "runtimeExecutable": "python3",
      "runtimeArgs": ["-m", "http.server", "8765", "--directory", "/Users/xaviarnedo/Desktop/NEXO/Otros-proyectos/cuentas"],
      "port": 8765
    }
  ]
}
```

- [ ] **Step 9: Verificar en el navegador (modo demo)**

`preview_start {name: "cuentas"}` → navegar a `http://localhost:8765/index.html?demo=1`.
Expected:
- `read_console_messages` sin errores.
- `read_page`: pestañas "Común" y "Mía", etiqueta "Demo" y el nombre del mes actual.
- Al pulsar `‹`, cambia al mes anterior.

Sin `?demo=1` → aparece el formulario de login (no se inicia sesión: las credenciales son de Xavi y Andrea).

- [ ] **Step 10: Commit**

```bash
git add index.html styles.css manifest.json sw.js gen_icons.py icons .nojekyll supabase-js.min.js \
  supabase-client.js datos.js datos-demo.js app.js ui-mes.js ui-movs.js ui-nuevo.js
git commit -m "Esqueleto PWA: login, pestañas, meses, modo demo

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Pantalla "El mes"

**Files:**
- Modify: `ui-mes.js` (sustituye el stub entero)

**Interfaces:**
- Consumes: `window.App.estado`, `App.recargar`, `window.Calculos.{resumenMes, comparacion, ultimosMeses, nombreMes, formatoEuros, variacion}`, `window.UiMovs.abrir({categoria, titulo})` (Task 8; con el stub no hace nada).
- Produces: `window.UiMes.pintar()`.

- [ ] **Step 1: Implementar `ui-mes.js`**

```js
/* Cuentas de casa — pantalla "El mes": total, comparación, gráfico de 6 meses y gasto por categoría. */
(function () {
  "use strict";
  var C = window.Calculos;
  function $(id) { return document.getElementById(id); }

  function pintar() {
    var e = window.App.estado;
    var r = C.resumenMes(e.movs, e.cats, e.mes);
    $("total").textContent = C.formatoEuros(r.total);
    var comp = C.comparacion(e.movs, e.cats, e.mes, 3);
    $("comparacion").textContent = !comp ? "" : (comp.pct > 0 ? "+" : "") + comp.pct + " % " +
      (comp.meses === 1 ? "frente al mes anterior" : "frente a la media de los " + comp.meses + " meses anteriores");
    pintarGrafico(e);
    pintarCategorias(e, r);
  }

  function pintarGrafico(e) {
    var meses = C.ultimosMeses(e.mes, 6);
    var totales = meses.map(function (m) { return C.resumenMes(e.movs, e.cats, m).total; });
    var max = Math.max.apply(null, totales.concat([1]));
    var g = $("grafico");
    g.innerHTML = "";
    meses.forEach(function (m, i) {
      var col = document.createElement("button");
      col.type = "button";
      col.className = "barra-mes" + (m === e.mes ? " actual" : "");
      col.title = C.nombreMes(m) + ": " + C.formatoEuros(totales[i]);
      var barra = document.createElement("span");
      barra.style.height = Math.max(0, totales[i]) / max * 80 + "%";
      var etiqueta = document.createElement("small");
      etiqueta.textContent = C.nombreMes(m).slice(0, 3);
      col.appendChild(barra);
      col.appendChild(etiqueta);
      col.addEventListener("click", function () { e.mes = m; window.App.recargar(); });
      g.appendChild(col);
    });
  }

  function pintarCategorias(e, r) {
    var ul = $("lista-categorias");
    ul.innerHTML = "";
    if (!r.filas.length) {
      ul.innerHTML = '<li class="vacio">Sin gastos este mes</li>';
      return;
    }
    var max = Math.max(r.filas[0].total, 1);
    r.filas.forEach(function (f) {
      var cat = f.categoria_id ? e.cats[f.categoria_id] : null;
      var nombre = cat ? cat.nombre : "Sin categoría";
      var li = document.createElement("li");
      li.innerHTML = '<span class="icono"></span><div class="cuerpo"><div class="linea">' +
        '<span class="nombre"></span><span class="importe"></span></div><div class="pista"><i></i></div></div>' +
        '<span class="var"></span>';
      li.querySelector(".icono").textContent = cat ? cat.icono : "❓";
      li.querySelector(".nombre").textContent = nombre;
      li.querySelector(".importe").textContent = C.formatoEuros(f.total);
      li.querySelector("i").style.width = Math.max(0, f.total) / max * 100 + "%";
      var v = C.variacion(f.total, f.anterior), vs = li.querySelector(".var");
      if (v !== null) {
        vs.textContent = (v > 0 ? "↑" : v < 0 ? "↓" : "=") + Math.abs(v) + " %";
        if (v !== 0) vs.classList.add(v > 0 ? "sube" : "baja");
      }
      li.addEventListener("click", function () {
        window.UiMovs.abrir({ categoria: f.categoria_id || "", titulo: nombre });
      });
      ul.appendChild(li);
    });
  }

  $("ver-todos").addEventListener("click", function () {
    window.UiMovs.abrir({ categoria: null, titulo: "Todos los movimientos" });
  });

  window.UiMes = { pintar: pintar };
})();
```

- [ ] **Step 2: Verificar en el navegador (modo demo)**

Recargar `http://localhost:8765/index.html?demo=1`.
Expected:
- Sin errores en la consola.
- Total del mes en grande.
- Texto de comparación con "frente a la media de los 3 meses anteriores".
- 6 barras con la del mes actual resaltada.
- Lista con Súper en primer lugar.
- "Transferencias" no aparece.
- "Sin categoría ❓" aparece (por "Bar nuevo").
- Al pulsar la pestaña "Mía", los importes son la mitad.
- Screenshot a ancho móvil (`resize_window` preset `mobile`, y después volver a `desktop`).

- [ ] **Step 3: Commit**

```bash
git add ui-mes.js
git commit -m "Pantalla El mes: total, comparación, gráfico y categorías

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Movimientos y edición (categoría + regla, nota, "no es gasto", borrar)

**Files:**
- Modify: `ui-movs.js` (sustituye el stub entero)

**Interfaces:**
- Consumes: `App.estado`, `App.D.{actualizarMovimiento, guardarRegla, recategorizarComercio, borrarMovimiento}`, `App.recargar`, `App.aviso`, `App.chips`, `Calculos.{mesDe, esGasto, fechaCorta, formatoEuros}`.
- Produces: `window.UiMovs.abrir({ categoria: string|null, titulo })` (`null` = todos; `""` = sin categoría) y `window.UiMovs.pintarSiVisible()`.

- [ ] **Step 1: Implementar `ui-movs.js`**

```js
/* Cuentas de casa — lista de movimientos del mes y hoja de edición. */
(function () {
  "use strict";
  var C = window.Calculos;
  var filtro = { categoria: null, titulo: "" };
  var enEdicion = null;
  function $(id) { return document.getElementById(id); }

  function abrir(f) {
    filtro = f;
    $("buscar").value = "";
    $("vista-mes").hidden = true;
    $("vista-movs").hidden = false;
    pintar();
    window.scrollTo(0, 0);
  }
  function cerrar() {
    $("vista-movs").hidden = true;
    $("vista-mes").hidden = false;
  }
  function pintarSiVisible() { if (!$("vista-movs").hidden) pintar(); }

  function visibles() {
    var e = window.App.estado, texto = $("buscar").value.trim().toLowerCase();
    return e.movs.filter(function (m) {
      if (C.mesDe(m.fecha) !== e.mes) return false;
      if (filtro.categoria !== null &&
          ((m.categoria_id || "") !== filtro.categoria || !C.esGasto(m, e.cats))) return false;
      return !texto || (m.comercio + " " + m.nota + " " + m.descripcion).toLowerCase().indexOf(texto) >= 0;
    });
  }

  function pintar() {
    var e = window.App.estado;
    $("titulo-movs").textContent = filtro.titulo;
    var ul = $("lista-movs");
    ul.innerHTML = "";
    var lista = visibles();
    if (!lista.length) {
      ul.innerHTML = '<li class="vacio">Nada por aquí</li>';
      return;
    }
    lista.forEach(function (m) {
      var cat = m.categoria_id && e.cats[m.categoria_id];
      var li = document.createElement("li");
      if (m.no_es_gasto) li.className = "apagado";
      li.innerHTML = '<span class="icono"></span><div class="cuerpo"><span class="nombre"></span><small></small></div>' +
        '<span class="importe"></span>';
      li.querySelector(".icono").textContent = cat ? cat.icono : "❓";
      li.querySelector(".nombre").textContent = m.comercio;
      li.querySelector("small").textContent = C.fechaCorta(m.fecha) + (m.nota ? " · " + m.nota : "") +
        (m.origen === "manual" ? " · a mano" : "");
      var imp = li.querySelector(".importe");
      imp.textContent = C.formatoEuros(m.importe_cent);
      if (m.importe_cent > 0) imp.classList.add("positivo");
      li.addEventListener("click", function () { editar(m); });
      ul.appendChild(li);
    });
  }

  function editar(m) {
    var e = window.App.estado;
    enEdicion = m;
    $("ed-comercio").textContent = m.comercio;
    $("ed-detalle").textContent = C.fechaCorta(m.fecha) + " · " + C.formatoEuros(m.importe_cent) +
      (m.descripcion && m.descripcion !== m.comercio ? " · " + m.descripcion : "");
    window.App.chips($("ed-cats"), m.categoria_id);
    $("ed-todos-fila").hidden = m.origen !== "import";
    $("ed-todos").checked = m.origen === "import";
    $("ed-todos-txt").textContent = "Aplicar a todos los de " + m.comercio;
    $("ed-nota").value = m.nota || "";
    $("ed-no-gasto").checked = !!m.no_es_gasto;
    $("ed-borrar").hidden = !(m.origen === "manual" && m.creado_por === e.usuario.id);
    $("hoja-mov").showModal();
  }

  $("ed-form").addEventListener("submit", function (ev) {
    ev.preventDefault();
    var App = window.App, m = enEdicion;
    var elegida = $("ed-cats").querySelector(".elegida");
    var categoria = elegida ? elegida.dataset.id : null;
    var p = App.D.actualizarMovimiento(m.id, {
      categoria_id: categoria, nota: $("ed-nota").value.trim(), no_es_gasto: $("ed-no-gasto").checked
    });
    if (categoria && categoria !== m.categoria_id && m.origen === "import" && $("ed-todos").checked) {
      var cuenta = App.estado.cuentas.find(function (c) { return c.id === m.cuenta_id; });
      p = p.then(function () { return App.D.guardarRegla(m.comercio.toLowerCase(), categoria, cuenta.owner); })
           .then(function () { return App.D.recategorizarComercio(m.cuenta_id, m.comercio, categoria); });
    }
    p.then(function () { $("hoja-mov").close(); return App.recargar(); })
     .catch(function (err) { App.aviso("No se pudo guardar: " + err.message); });
  });

  $("ed-borrar").addEventListener("click", function () {
    if (!confirm("¿Borrar este movimiento?")) return;
    window.App.D.borrarMovimiento(enEdicion.id)
      .then(function () { $("hoja-mov").close(); return window.App.recargar(); })
      .catch(function (err) { window.App.aviso("No se pudo borrar: " + err.message); });
  });
  $("ed-cancelar").addEventListener("click", function () { $("hoja-mov").close(); });
  $("volver").addEventListener("click", cerrar);
  $("buscar").addEventListener("input", pintar);

  window.UiMovs = { abrir: abrir, pintarSiVisible: pintarSiVisible };
})();
```

- [ ] **Step 2: Verificar en el navegador (modo demo)**

Recargar `?demo=1` y comprobar:
1. Al tocar la fila "Sin categoría", la lista contiene solo "Bar nuevo".
2. Al tocarlo se abre la hoja; elige "🍽️ Restaurantes" con "Aplicar a todos" marcado y pulsa Guardar. La hoja se cierra, "Sin categoría" desaparece de la pantalla del mes y Restaurantes sube.
3. "Ver todos los movimientos" muestra las transferencias en verde (positivas). El buscador "merca" filtra.
4. Marcar "No es un gasto" en un Mercadona hace que baje el total del mes.
5. Consola sin errores.

- [ ] **Step 3: Commit**

```bash
git add ui-movs.js
git commit -m "Lista de movimientos y edición con reglas automáticas

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Apuntar a mano

**Files:**
- Modify: `ui-nuevo.js` (sustituye el stub entero)

**Interfaces:**
- Consumes: `App.estado`, `App.cuentasDelGrupo`, `App.chips`, `App.D.crearMovimiento`, `App.pintarPestanas`, `App.recargar`, `Calculos.{parseImporte, fechaISO, mesDe}`.
- Produces: el comportamiento del botón `#fab`.

- [ ] **Step 1: Implementar `ui-nuevo.js`**

```js
/* Cuentas de casa — hoja "Apuntar a mano". Gasto en negativo; la categoría Ingresos, en positivo. */
(function () {
  "use strict";
  var C = window.Calculos;
  function $(id) { return document.getElementById(id); }

  function abrir() {
    var App = window.App, e = App.estado;
    $("nu-importe").value = "";
    $("nu-nota").value = "";
    $("nu-fecha").value = C.fechaISO(new Date());
    $("nu-error").hidden = true;
    var sel = $("nu-cuenta");
    sel.innerHTML = "";
    ["comun", "mia"].forEach(function (g) {
      App.cuentasDelGrupo(g).forEach(function (c) {
        var o = document.createElement("option");
        o.value = c.id;
        o.textContent = c.nombre + " (" + c.banco + ")";
        sel.appendChild(o);
      });
    });
    var actual = App.cuentasDelGrupo(e.grupo)[0];
    if (actual) sel.value = actual.id;
    App.chips($("nu-cats"), null, e.catsLista.filter(function (c) { return c.id !== "transferencias"; }));
    $("hoja-nuevo").showModal();
    $("nu-importe").focus();
  }

  function error(texto) {
    $("nu-error").textContent = texto;
    $("nu-error").hidden = false;
  }

  $("nu-form").addEventListener("submit", function (ev) {
    ev.preventDefault();
    var App = window.App, e = App.estado;
    var cent = C.parseImporte($("nu-importe").value);
    var elegida = $("nu-cats").querySelector(".elegida");
    if (!cent) return error("Escribe un importe válido (por ejemplo, 12,50).");
    if (!elegida) return error("Elige una categoría.");
    if (!$("nu-cuenta").value) return error("No tienes ninguna cuenta donde apuntarlo.");
    var cat = e.cats[elegida.dataset.id];
    var nota = $("nu-nota").value.trim();
    var fila = {
      cuenta_id: $("nu-cuenta").value, fecha: $("nu-fecha").value || C.fechaISO(new Date()),
      importe_cent: cat.id === "ingresos" ? cent : -cent, comercio: nota || cat.nombre,
      descripcion: "", nota: "", categoria_id: cat.id, origen: "manual", creado_por: e.usuario.id
    };
    App.D.crearMovimiento(fila).then(function () {
      $("hoja-nuevo").close();
      var cuenta = e.cuentas.find(function (c) { return c.id === fila.cuenta_id; });
      e.grupo = cuenta.owner === null ? "comun" : "mia";
      e.mes = C.mesDe(fila.fecha);
      App.pintarPestanas();
      return App.recargar();
    }).catch(function (err) { error("No se pudo guardar: " + err.message); });
  });

  $("fab").addEventListener("click", abrir);
  $("nu-cancelar").addEventListener("click", function () { $("hoja-nuevo").close(); });
})();
```

- [ ] **Step 2: Verificar en el navegador (modo demo)**

1. Pulsar "+" con el importe vacío y "Guardar" → "Escribe un importe válido…".
2. Escribir `12,50`, elegir 🛒 Súper y la cuenta "Común", poner "Fruta" en la nota y pulsar Guardar. Súper sube 12,50 €. En "Ver todos" aparece "Fruta · … · a mano".
3. Tocar ese movimiento muestra el botón "Borrar". Borrarlo hace que Súper vuelva a su importe anterior.
4. Elegir la cuenta "Xavi (CaixaBank)" hace que la app cambie a la pestaña "Mía".
5. Consola sin errores. Screenshot a ancho móvil.

- [ ] **Step 3: Commit**

```bash
git add ui-nuevo.js
git commit -m "Apuntar gastos a mano

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: Publicar y probar en los móviles

**Files:**
- Ninguno nuevo (como mucho, subir `?v=N` si hay que corregir algo).

- [ ] **Step 1: Pasar todos los tests**

Run: `python3 -m unittest discover -s tests -t . && node --test tests/calculos.test.js`
Expected: todo OK.

Run: `git status --porcelain | grep -Ei '\.(pdf|xlsx|xls|csv)$|\.env$'`
Expected: sin salida (no hay extractos ni `.env` a punto de subirse).

- [ ] **Step 2: [Xavi] Crear el repo y activar Pages**

Xavi ejecuta (`gh repo create` lo bloquea el clasificador si lo lanza Claude):
```bash
cd ~/Desktop/NEXO/Otros-proyectos/cuentas && ~/.local/bin/gh repo create xaviarnedo-ui/cuentas-casa --public --source=. --push
```
```bash
~/.local/bin/gh api -X POST repos/xaviarnedo-ui/cuentas-casa/pages -f "source[branch]=main" -f "source[path]=/"
```

- [ ] **Step 3: Comprobar el despliegue**

Esperar a que termine el despliegue de Pages y abrir `https://xaviarnedo-ui.github.io/cuentas-casa/` en el navegador integrado. Expected:
- aparece el formulario de login, sin errores en la consola;
- `?demo=1` funciona igual que en local.

- [ ] **Step 4: [Xavi y Andrea] Instalar y entrar**

Cada uno, en su móvil: abrir la URL en Safari, pulsar Compartir → "Añadir a pantalla de inicio" y entrar con su email y contraseña. Expected:
- los dos ven la pestaña "Común" con los datos de septiembre y octubre;
- el total de septiembre coincide con el que dio `cuentas.py` en el Task 4.

- [ ] **Step 5: Guardar la memoria del proyecto**

Actualizar `~/.claude/projects/-Users-xaviarnedo-Desktop/memory/cuentas-casa-app.md` con la URL de producción, el id del proyecto Supabase y "fase 1 en producción (fecha)".
