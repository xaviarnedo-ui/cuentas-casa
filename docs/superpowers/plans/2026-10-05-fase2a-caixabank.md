# Cuentas de casa — Fase 2a (CaixaBank) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Importar el CSV de movimientos de CaixaBankNow de Xavi. Los conceptos genéricos sin nombre ("BIZUM RECIBIDO", "TRANSFER INMEDIATA"…) se categorizan uno a uno con `--asignar`. Los Bizum que devuelven una factura de agua se detectan solos.

**Architecture:**
- Nuevo lector `importador/caixabank.py`, con la misma salida (`Extracto`) que el de Revolut.
- `preparar_importacion` gana dos parámetros opcionales: `asignaciones` y `agua_previa`. Separa los genéricos (numerados) de los comercios con regla.
- `cuentas.py` lee también `.csv`, decide la cuenta por IBAN, por banco o por `--cuenta`, y acepta `--asignar N=categoria`.

**Tech Stack:** Python 3.9 stdlib + unittest (como la fase 1).

**Spec:** `docs/superpowers/specs/2026-10-04-cuentas-casa-design.md` (§6 importación, §9 Bizum de la inquilina)

## Global Constraints

- Importes en céntimos enteros; negativo = sale dinero. Mes = fecha de transacción.
- Formato CSV CaixaBank: cabecera exacta `Concepto;Fecha;Importe;Saldo`, separador `;`, fecha `dd/mm/aaaa`, importes `+70,00EUR` / `-1.234,56EUR`, del más reciente al más antiguo, sin IBAN.
- Cada fila debe cuadrar con el saldo de la anterior (en orden cronológico); si no, `FormatoError` y no se sube nada.
- Genéricos (comparación sin mayúsculas y con espacios normalizados): `bizum recibido`, `bizum enviado`, `transfer inmediata`, `pago transferencias`. Nunca generan ni usan reglas.
- Un genérico `bizum recibido` positivo es devolución de agua si existe un cargo `piso-agua` del mismo importe exacto, aún sin devolver, con fecha en los 45 días anteriores (o el mismo día). El emparejamiento es uno a uno.
- La cuenta CaixaBank de Xavi tiene id `caixabank`, banco `CaixaBank`, owner Xavi e `iban_final` `5987`.
- Sin datos reales en el repo (las fixtures van anonimizadas). Python: solo stdlib + `fitz`.
- Commits terminan con `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`; añadir archivos explícitamente.

---

### Task 1: Lector CSV de CaixaBank y genéricos en la categorización

**Files:**
- Create: `importador/caixabank.py`, `tests/fixtures/caixabank.csv`, `tests/test_caixabank.py`
- Modify: `importador/categorizar.py`, `tests/test_categorizar.py`

**Interfaces:**
- Produces:
  - `caixabank.es_csv_caixabank(texto) -> bool`
  - `caixabank.parsear(texto) -> Extracto` (`banco="caixabank"`, `iban=""`)
  - `categorizar.GENERICOS`, `categorizar.es_generico(comercio) -> bool`, `categorizar.sumar_dias(fecha, n) -> str`
  - `preparar_importacion(extracto, cuenta, reglas, huellas_existentes, asignaciones=None, agua_previa=None)`, donde `asignaciones` es `{n: categoria_id}` y `agua_previa` es `[{"fecha", "importe_cent"}]`. Su `PlanImportacion` añade el campo `genericos: List[dict]` (`{"n", "fecha", "comercio", "importe_cent"}`), con valor por defecto `[]`.

- [ ] **Step 1: Fixture** `tests/fixtures/caixabank.csv` (exacto, con salto de línea final):
```
Concepto;Fecha;Importe;Saldo
SMAP ORA PALMA;30/09/2026;-1,35EUR;1.488,24EUR
BIZUM RECIBIDO;28/09/2026;+70,00EUR;1.489,59EUR
Activacion;28/09/2026;-0,01EUR;1.419,59EUR
SumUp  *TIENDA;05/09/2026;-14,00EUR;1.419,60EUR
Comun;01/09/2026;-500,00EUR;1.433,60EUR
```

- [ ] **Step 2: Tests (RED)**

`tests/test_caixabank.py`:
```python
"""Lector del CSV de CaixaBankNow, con una fixture anonimizada."""
import unittest
from pathlib import Path

from importador import caixabank
from importador.modelo import FormatoError

FIXTURE = Path(__file__).parent / "fixtures" / "caixabank.csv"


def texto():
    return FIXTURE.read_text(encoding="utf-8")


class Parsear(unittest.TestCase):
    def setUp(self):
        self.ext = caixabank.parsear(texto())
        self.movs = self.ext.movimientos

    def test_detecta(self):
        self.assertTrue(caixabank.es_csv_caixabank(texto()))
        self.assertTrue(caixabank.es_csv_caixabank("﻿" + texto()))
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
        self.assertEqual(len(caixabank.parsear("﻿" + texto()).movimientos), 5)

    def test_saldo_que_no_cuadra_aborta(self):
        with self.assertRaises(FormatoError):
            caixabank.parsear(texto().replace("1.419,59EUR", "1.419,58EUR"))

    def test_cabecera_distinta_aborta(self):
        with self.assertRaises(FormatoError):
            caixabank.parsear("Fecha;Concepto\n")

    def test_columnas_de_mas_aborta(self):
        with self.assertRaises(FormatoError):
            caixabank.parsear(texto().replace("Activacion;", "Activa;cion;"))


if __name__ == "__main__":
    unittest.main()
```

En `tests/test_categorizar.py` añadir (los imports de arriba se amplían con `es_generico`):
```python
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

    def test_sumar_dias(self):
        self.assertEqual(sumar_dias("2026-01-30", 45), "2026-03-16")
```
(The import line becomes `from importador.categorizar import TRANSFERENCIAS, buscar_regla, es_generico, gasto_por_mes, posibles_duplicados, preparar_importacion, sumar_dias`. Keep `posibles_duplicados` if it is already imported there.)

Run: `python3 -m unittest discover -s tests -t . -v` → Expected: errors from the missing module and functions.

- [ ] **Step 3: `importador/caixabank.py`**
```python
"""Lector del CSV de movimientos de CaixaBankNow (Concepto;Fecha;Importe;Saldo).

Viene del más reciente al más antiguo y no trae IBAN: la cuenta se decide por el banco.
Cada fila debe cuadrar con el saldo de la anterior (en orden cronológico)."""
import re

from .modelo import Extracto, FormatoError, Movimiento

CABECERA = "Concepto;Fecha;Importe;Saldo"
RE_FECHA = re.compile(r"^(\d{2})/(\d{2})/(\d{4})$")
RE_IMPORTE = re.compile(r"^([+-]?)([\d.]+),(\d{2})EUR$")


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
```

- [ ] **Step 4: `importador/categorizar.py`**
1. Imports: `from dataclasses import dataclass, field` and `from datetime import date, timedelta`.
2. After `TRANSFERENCIAS`:
```python
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
        for p in sorted(previos, key=lambda x: x["fecha"]):
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
```
3. `PlanImportacion` gets a final field: `genericos: List[dict] = field(default_factory=list)`.
4. `preparar_importacion`: new signature `preparar_importacion(extracto, cuenta, reglas, huellas_existentes, asignaciones=None, agua_previa=None)`. At the start: `asignaciones = asignaciones or {}`, `agua = _FacturasAgua(agua_previa or [])`, `genericos, num_generico = [], 0`. The category is decided like this, after the duplicate check, replacing the current if/else:
```python
        if m.es_transferencia:
            categoria = TRANSFERENCIAS
        elif es_generico(m.comercio):
            num_generico += 1
            if num_generico in asignaciones:
                categoria = asignaciones[num_generico]
            elif m.comercio.lower().startswith("bizum recibido") and agua.es_devolucion(m.fecha, m.importe_cent):
                categoria = "piso-agua"
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
```
(The existing huella/k-th-repeat logic and the row dict stay as they are. Keep the old "sin_regla" behaviour for non-generic rows exactly.) Return `PlanImportacion(nuevos, duplicados, sin_regla, saldos, genericos)`.

Run: full suite → all OK (28 previous + 8 caixabank + 8 new categorizar = 44).

- [ ] **Step 5: Commit**
```bash
git add importador/caixabank.py importador/categorizar.py tests/fixtures/caixabank.csv tests/test_caixabank.py tests/test_categorizar.py
git commit -m "Lector CSV de CaixaBank y movimientos genéricos (Bizum, transferencias) por asignación

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: `cuentas.py` — CSV, cuenta por banco, `--asignar`; cuenta CaixaBank en SQL; CLAUDE.md

**Files:**
- Modify: `cuentas.py`, `supabase/perfiles.sql`, `CLAUDE.md`

**Interfaces:**
- Consumes: Task 1 (`caixabank.*`, `preparar_importacion(..., asignaciones, agua_previa)`, `plan.genericos`, `sumar_dias`).
- Produces: `python3 cuentas.py importar <archivo.pdf|.csv> [--cuenta ID] [--asignar N=categoria ...] [--sin-categoria]`.

- [ ] **Step 1: `cuentas.py`**
1. Import `caixabank` next to `revolut`, and `sumar_dias` from categorizar.
2. Replace the reader detection in `importar` with a function:
```python
def leer_extracto(ruta):
    if ruta.lower().endswith(".csv"):
        datos = Path(ruta).read_bytes()
        try:
            texto = datos.decode("utf-8-sig")
        except UnicodeDecodeError:
            texto = datos.decode("latin-1")
        if caixabank.es_csv_caixabank(texto):
            return caixabank.parsear(texto)
        raise FormatoError("No reconozco el formato del CSV " + ruta)
    paginas = paginas_pdf(ruta)
    parsear = next((p for detecta, p in LECTORES if detecta(paginas)), None)
    if parsear is None:
        raise FormatoError("No reconozco el banco de " + ruta)
    return parsear(paginas)
```
3. Replace `cuenta_por_iban` with:
```python
def cuenta_del_extracto(api, extracto, cuenta_id):
    cuentas = api.leer("cuentas", select="id,nombre,banco,owner,iban_final")
    if cuenta_id:
        for c in cuentas:
            if c["id"] == cuenta_id:
                return c
        raise FormatoError("No existe la cuenta '%s'." % cuenta_id)
    if extracto.iban:
        for c in cuentas:
            if c["iban_final"] and extracto.iban.endswith(c["iban_final"]):
                return c
        raise FormatoError("Ninguna cuenta tiene un IBAN acabado en %s." % extracto.iban[-4:])
    del_banco = [c for c in cuentas if c["banco"].lower() == extracto.banco]
    if len(del_banco) == 1:
        return del_banco[0]
    raise FormatoError("No sé a qué cuenta de %s va este extracto: usa --cuenta <id>." % extracto.banco)
```
4. In `importar(api, ruta, sin_categoria, asignar, cuenta_id)`:
   - `extracto = leer_extracto(ruta)`; `cuenta = cuenta_del_extracto(api, extracto, cuenta_id)`.
   - Validate `asignar` (dict `{n: categoria}`) against the category ids. Unknown id → `FormatoError("No existe la categoría '%s'." % cat)`.
   - `agua_previa = api.leer("movimientos", select="fecha,importe_cent", cuenta_id="eq." + cuenta["id"], categoria_id="eq.piso-agua", fecha="gte." + sumar_dias(desde, -DIAS))`, with `DIAS = 45` imported as `DIAS_BIZUM_AGUA`.
   - `plan = preparar_importacion(extracto, cuenta, reglas, existentes, asignar, agua_previa)`.
   - Pending output, uploading nothing, exit code 2 when `plan.sin_regla` or `plan.genericos` (unless `--sin-categoria`):
```python
    if (plan.sin_regla or plan.genericos) and not sin_categoria:
        if plan.sin_regla:
            print("\nComercios sin regla (NO se ha subido nada):")
            for comercio in plan.sin_regla:
                print("  - " + comercio)
            print('Crea las reglas con:  python3 cuentas.py regla "<patrón>" <categoria_id> [--cuenta %s]' % cuenta["id"])
        if plan.genericos:
            print("\nMovimientos genéricos por asignar (NO se ha subido nada):")
            for g in plan.genericos:
                print("  [%d] %s  %s  %s" % (g["n"], g["fecha"], g["comercio"], euros(g["importe_cent"])))
            print("Repite la importación con:  --asignar N=<categoria_id>  (uno por movimiento)")
        return 2
```
   - Everything else (dup count line, posibles duplicados, upload, summary) stays the same.
5. argparse for `importar`: add `pi.add_argument("--cuenta")` and `pi.add_argument("--asignar", action="append", default=[], metavar="N=CATEGORIA")`. Parse them into a dict in `main` (or a helper `leer_asignaciones(lista)`). A malformed item (no `=` or non-integer N) → `FormatoError("Asignación no válida: %s (formato N=categoria)" % item)`. Pass the dict and `args.cuenta` to `importar`.

- [ ] **Step 2: `supabase/perfiles.sql`**
- Efectivo `orden` 2 → 3.
- Add before the piso categories:
```sql
insert into cuentas (id, nombre, banco, tipo, owner, iban_final, orden)
select 'caixabank', 'CaixaBank', 'CaixaBank', 'corriente', id, '5987', 2 from profiles where nombre = 'Xavi'
on conflict (id) do nothing;
```

- [ ] **Step 3: `CLAUDE.md`** — after the "Cuando Xavi pasa un extracto" list, add:
```markdown
### CaixaBank (CSV de CaixaBankNow)

- Xavi descarga el **CSV** (Cuentas → Movimientos → exportar). No trae IBAN: va a la cuenta `caixabank`.
- Las reglas de CaixaBank son de Xavi: `python3 cuentas.py regla "<patrón>" <categoria> --cuenta caixabank`.
  Cuidado con patrones cortos que puedan estar dentro de otros conceptos (las reglas buscan "contiene").
- "BIZUM RECIBIDO/ENVIADO", "TRANSFER INMEDIATA" y "PAGO TRANSFERENCIAS" no dicen quién es: el script
  los lista numerados y hay que preguntar a Xavi cada uno, después repetir con `--asignar N=categoria`.
  Los Bizum que coinciden con una factura de agua (≤45 días) se asignan solos a `piso-agua`.
```

- [ ] **Step 4: Verification**
  - Both suites green.
  - `python3 cuentas.py importar --help` shows `--cuenta` and `--asignar`.
  - Without network, run a small Python snippet that calls `leer_extracto("tests/fixtures/caixabank.csv")` and prints the number of movements (5).

- [ ] **Step 5: Commit**
```bash
git add cuentas.py supabase/perfiles.sql CLAUDE.md
git commit -m "cuentas.py: CSV de CaixaBank, cuenta por banco y asignación de genéricos

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### After the plan (controller, with Xavi)
1. Create the `caixabank` account in the DB (same row as perfiles.sql) using the service key; efectivo `orden` → 3.
2. `python3 cuentas.py importar ~/Downloads/CaixaBank_…csv`. Ask Xavi about the merchants/concepts without a rule and each generic. Create the rules with `--cuenta caixabank`, then re-run with `--asignar`.
