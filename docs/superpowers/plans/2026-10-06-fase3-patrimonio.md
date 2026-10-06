# Cuentas de casa — Fase 3 (Patrimonio) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Registrar el saldo de fin de mes de MyInvestor, Trade Republic y MyAXA y mostrar una pestaña **Patrimonio** (solo del dueño). Incluye el total actual, una gráfica de 12 meses, el desglose por cuenta y la común aparte sin sumar.

**Architecture:**
- La tabla `saldos` ya existe. El importador ya escribe en ella los saldos de las cuentas corrientes.
- Nueva orden `cuentas.py saldo` para los saldos que se dictan a mano.
- El efectivo no tiene saldos en esa tabla: se calcula acumulando sus movimientos.
- Dos funciones puras en `calculos.js` (saldo de cada cuenta al cierre de cada mes, arrastrando el último dato) y una pantalla nueva, `ui-patrimonio.js`.

**Tech Stack:** igual que las fases anteriores.

**Spec:** `docs/superpowers/specs/2026-10-04-cuentas-casa-design.md` (§2 cuentas, §5 pantalla Patrimonio)

## Global Constraints

- Céntimos enteros. El patrimonio de un mes es la suma, en cuentas PROPIAS (owner = usuario), del último saldo con fecha ≤ fin de ese mes. Si una cuenta no tiene dato todavía, no suma.
- La común (owner null) se muestra aparte, como información, y NO suma al total personal.
- Cuentas nuevas (owner Xavi): `myinvestor` (MyInvestor, tipo `inversion`, orden 4), `traderepublic` (Trade Republic, banco "Trade Republic", `inversion`, orden 5) y `myaxa` (MyAXA, banco "AXA", `ahorro`, orden 6).
- La pestaña "Patrimonio" solo aparece si el usuario tiene alguna cuenta propia de tipo `ahorro` o `inversion`.
- Textos en español. JS: IIFE + "use strict" + var/function, sin build. Python: stdlib, unittest.
- NUNCA ejecutar `cuentas.py importar/regla/categorias/saldo` contra la BD real (hay un .env real) ni imprimir `.env`: los tests usan ApiFalsa.
- Commits terminan con `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`; añadir archivos explícitamente.

---

### Task 1: Orden `cuentas.py saldo` y cuentas nuevas en SQL

**Files:** Modify `cuentas.py`, `tests/test_cuentas.py`, `supabase/perfiles.sql`, `CLAUDE.md`

**Interfaces:**
- Produces:
  - `leer_importe(texto) -> int` (céntimos; acepta `12.340`, `12.340,5`, `12340,50`, `12340.5`, `1.234,56 €`; si no, `FormatoError`).
  - `saldo(api, cuenta_id, importe_texto, fecha=None) -> 0`.
  - CLI `python3 cuentas.py saldo <cuenta_id> <importe> [--fecha AAAA-MM-DD]`.

- [ ] **Step 1: Tests (RED)** — añadir a `tests/test_cuentas.py` (importar `leer_importe` y `saldo` de `cuentas`):
```python
class LeerImporte(unittest.TestCase):
    def test_formatos(self):
        self.assertEqual(leer_importe("12.340"), 1234000)
        self.assertEqual(leer_importe("12.340,5"), 1234050)
        self.assertEqual(leer_importe("12340,50"), 1234050)
        self.assertEqual(leer_importe("12340.5"), 1234050)
        self.assertEqual(leer_importe(" 1.234,56 € "), 123456)
        self.assertEqual(leer_importe("0"), 0)

    def test_no_validos(self):
        for malo in ("", "abc", "-5", "1,2,3", "12.34.5", "1.2345"):
            with self.assertRaises(FormatoError):
                leer_importe(malo)


class Saldo(unittest.TestCase):
    def test_registra_con_fecha(self):
        api = ApiFalsa(cuentas_=[{"id": "myinvestor", "nombre": "MyInvestor"}])
        self.assertEqual(silencio(saldo, api, "myinvestor", "12.340,50", "2026-09-30")[0], 0)
        tabla, filas, opciones = api.inserciones[-1]
        self.assertEqual(tabla, "saldos")
        self.assertEqual(filas, [{"cuenta_id": "myinvestor", "fecha": "2026-09-30", "saldo_cent": 1234050}])
        self.assertEqual(opciones, {"conflicto": "cuenta_id,fecha", "al_chocar": "merge"})

    def test_cuenta_inexistente(self):
        api = ApiFalsa(cuentas_=[{"id": "myinvestor", "nombre": "MyInvestor"}])
        with self.assertRaises(FormatoError):
            saldo(api, "nada", "100", "2026-09-30")

    def test_fecha_no_valida(self):
        api = ApiFalsa(cuentas_=[{"id": "myinvestor", "nombre": "MyInvestor"}])
        with self.assertRaises(FormatoError):
            saldo(api, "myinvestor", "100", "30/09/2026")
```
(`silencio` returns `(resultado, salida)`.)

- [ ] **Step 2: Implementar en `cuentas.py`**
```python
import re
from datetime import date
from decimal import Decimal

RE_IMPORTE_ES = re.compile(r"^(\d{1,3}(?:\.\d{3})+|\d+)(?:,(\d{1,2}))?$")   # 12.340 / 12.340,5 / 12340,50
RE_IMPORTE_PUNTO = re.compile(r"^(\d+)\.(\d{1,2})$")                      # 12340.5


def leer_importe(texto):
    """Importe dictado por Xavi → céntimos. El punto con 3 cifras detrás es de miles."""
    t = texto.replace("€", "").replace(" ", "").strip()
    m = RE_IMPORTE_ES.match(t)
    if m:
        enteros, dec = m.group(1).replace(".", ""), (m.group(2) or "0")
    else:
        m = RE_IMPORTE_PUNTO.match(t)
        if not m:
            raise FormatoError("Importe no válido: '%s' (ej. 12.340,50)" % texto)
        enteros, dec = m.group(1), m.group(2)
    return int(Decimal(enteros + "." + dec) * 100)


def saldo(api, cuenta_id, importe_texto, fecha=None):
    cuenta = next((c for c in api.leer("cuentas", select="id,nombre") if c["id"] == cuenta_id), None)
    if cuenta is None:
        raise FormatoError("No existe la cuenta '%s'." % cuenta_id)
    fecha = fecha or date.today().isoformat()
    try:
        date.fromisoformat(fecha)
    except ValueError:
        raise FormatoError("Fecha no válida: '%s' (formato AAAA-MM-DD)." % fecha)
    cent = leer_importe(importe_texto)
    api.insertar("saldos", [{"cuenta_id": cuenta_id, "fecha": fecha, "saldo_cent": cent}],
                 conflicto="cuenta_id,fecha", al_chocar="merge")
    print("Saldo de %s a %s: %s" % (cuenta["nombre"], fecha, euros(cent)))
    return 0
```
argparse: `ps = sub.add_parser("saldo")`, then `ps.add_argument("cuenta_id")`, `ps.add_argument("importe")` and `ps.add_argument("--fecha")`. In `main`, call `saldo(api, args.cuenta_id, args.importe, args.fecha)` inside the existing try. Update the module docstring usage list.

- [ ] **Step 3: `supabase/perfiles.sql`** — after the caixabank account insert:
```sql
insert into cuentas (id, nombre, banco, tipo, owner, orden)
select c.id, c.nombre, c.banco, c.tipo, p.id, c.orden
from (values
  ('myinvestor', 'MyInvestor', 'MyInvestor', 'inversion', 4),
  ('traderepublic', 'Trade Republic', 'Trade Republic', 'inversion', 5),
  ('myaxa', 'MyAXA', 'AXA', 'ahorro', 6)
) as c(id, nombre, banco, tipo, orden)
cross join profiles p
where p.nombre = 'Xavi'
on conflict (id) do nothing;
```

- [ ] **Step 4: `CLAUDE.md`** — new section before `## Tests`:
```markdown
### Saldos de ahorro e inversión (fin de mes)

Xavi pasa el saldo de MyInvestor, Trade Republic y MyAXA el último día de cada mes (texto o captura):
`python3 cuentas.py saldo <myinvestor|traderepublic|myaxa> <importe> --fecha AAAA-MM-DD`
(fecha = último día del mes al que corresponde; repetir la orden corrige el valor de ese día).
```

- [ ] **Step 5:** Suites green (python: previous 71 + 5 new = 76), `python3 cuentas.py saldo --help`. Commit `cuentas.py tests/test_cuentas.py supabase/perfiles.sql CLAUDE.md`, message "Orden saldo para ahorro e inversión y sus cuentas".

---

### Task 2: Cálculos del patrimonio (`calculos.js`)

**Files:** Modify `calculos.js`, `tests/calculos.test.js`

**Interfaces:**
- Produces:
  - `saldosDesdeMovimientos(movs, cuentaId) -> [{cuenta_id, fecha, saldo_cent}]`: saldo acumulado al final de cada día con movimientos, en orden de fecha.
  - `patrimonioPorMes(saldos, cuentaIds, meses) -> [{mes, total, porCuenta: {id: {saldo_cent, fecha} | null}}]`.

- [ ] **Step 1: Tests (RED)**:
```js
test("saldosDesdeMovimientos acumula por día", () => {
  const movs = [
    { cuenta_id: "efectivo", fecha: "2026-09-02", importe_cent: -1000 },
    { cuenta_id: "efectivo", fecha: "2026-09-01", importe_cent: 120000 },
    { cuenta_id: "efectivo", fecha: "2026-09-02", importe_cent: 95000 },
    { cuenta_id: "otra", fecha: "2026-09-01", importe_cent: 5 }
  ];
  assert.deepStrictEqual(C.saldosDesdeMovimientos(movs, "efectivo"), [
    { cuenta_id: "efectivo", fecha: "2026-09-01", saldo_cent: 120000 },
    { cuenta_id: "efectivo", fecha: "2026-09-02", saldo_cent: 214000 }
  ]);
});

test("patrimonioPorMes arrastra el último saldo y no suma cuentas sin dato", () => {
  const saldos = [
    { cuenta_id: "a", fecha: "2026-08-31", saldo_cent: 1000 },
    { cuenta_id: "a", fecha: "2026-09-30", saldo_cent: 1500 },
    { cuenta_id: "b", fecha: "2026-09-15", saldo_cent: 300 },
    { cuenta_id: "c", fecha: "2026-08-31", saldo_cent: 999 }
  ];
  assert.deepStrictEqual(C.patrimonioPorMes(saldos, ["a", "b"], ["2026-08", "2026-09", "2026-10"]), [
    { mes: "2026-08", total: 1000, porCuenta: { a: { saldo_cent: 1000, fecha: "2026-08-31" }, b: null } },
    { mes: "2026-09", total: 1800, porCuenta: { a: { saldo_cent: 1500, fecha: "2026-09-30" }, b: { saldo_cent: 300, fecha: "2026-09-15" } } },
    { mes: "2026-10", total: 1800, porCuenta: { a: { saldo_cent: 1500, fecha: "2026-09-30" }, b: { saldo_cent: 300, fecha: "2026-09-15" } } }
  ]);
});
```
Run `node --test tests/calculos.test.js` → FAIL.

- [ ] **Step 2: Implementar** (antes de `var api = {`) y exportar ambas:
```js
  // Saldo acumulado al cierre de cada día con movimientos (para cuentas sin extracto, como el efectivo).
  function saldosDesdeMovimientos(movs, cuentaId) {
    var acumulado = 0, porFecha = {};
    movs.filter(function (m) { return m.cuenta_id === cuentaId; })
      .sort(function (a, b) { return a.fecha < b.fecha ? -1 : a.fecha > b.fecha ? 1 : 0; })
      .forEach(function (m) { acumulado += m.importe_cent; porFecha[m.fecha] = acumulado; });
    return Object.keys(porFecha).sort().map(function (f) {
      return { cuenta_id: cuentaId, fecha: f, saldo_cent: porFecha[f] };
    });
  }

  // Patrimonio al cierre de cada mes: último saldo conocido de cada cuenta (se arrastra si ese mes no hay dato).
  function patrimonioPorMes(saldos, cuentaIds, meses) {
    return meses.map(function (mes) {
      var fin = moverMes(mes, 1) + "-01", total = 0, porCuenta = {};
      cuentaIds.forEach(function (id) {
        var ultimo = null;
        saldos.forEach(function (s) {
          if (s.cuenta_id === id && s.fecha < fin && (!ultimo || s.fecha > ultimo.fecha)) ultimo = s;
        });
        porCuenta[id] = ultimo ? { saldo_cent: ultimo.saldo_cent, fecha: ultimo.fecha } : null;
        if (ultimo) total += ultimo.saldo_cent;
      });
      return { mes: mes, total: total, porCuenta: porCuenta };
    });
  }
```
Run → `pass 13`. Commit `calculos.js tests/calculos.test.js`, message "Cálculos del patrimonio: saldo al cierre de cada mes".

---

### Task 3: Datos (saldos) y pestaña Patrimonio

**Files:**
- Modify: `datos.js`, `datos-demo.js`, `app.js`, `index.html`, `styles.css`, `sw.js`
- Create: `ui-patrimonio.js`

**Interfaces:**
- Consumes: Task 2 functions; `App.D.movimientos`.
- Produces: `Datos.saldos(cuentaIds) -> Promise<[{cuenta_id, fecha, saldo_cent}]>` (same in DatosDemo); grupo `"patrimonio"`; `window.UiPatrimonio.cargar()`.

- [ ] **Step 1: `datos.js`** — add to `window.Datos`:
```js
    saldos: function (cuentaIds) {
      return db.from("saldos").select("*").in("cuenta_id", cuentaIds).order("fecha").then(ok);
    },
```
**`datos-demo.js`**:
- Add three accounts to `cuentas`, all with owner `"demo-xavi"`:
  - `{ id: "myinvestor", nombre: "MyInvestor", banco: "MyInvestor", tipo: "inversion", owner: "demo-xavi", orden: 4 }`
  - `{ id: "traderepublic", nombre: "Trade Republic", banco: "Trade Republic", tipo: "inversion", owner: "demo-xavi", orden: 5 }`
  - `{ id: "myaxa", nombre: "MyAXA", banco: "AXA", tipo: "ahorro", owner: "demo-xavi", orden: 6 }`
- Add a `saldos` array: for the last 6 months (`C.moverMes(mesActual, -k)`, k = 6..1), month-end rows built with `C.sumarDias(C.moverMes(mes, 1) + "-01", -1)`:
  - myinvestor: 1200000 + 35000 × i
  - traderepublic: 500000 + 8000 × i
  - myaxa: 300000 + 5000 × i
  - xavi: 250000 − 3000 × i
  - comun: 70000 + 1000 × i
- Expose `saldos: function (ids) { return ok(saldos.filter(function (s) { return ids.indexOf(s.cuenta_id) >= 0; })); }`.

- [ ] **Step 2: `index.html`**
  - After `</main>` of `vista-piso`:
```html
    <main id="vista-patrimonio" hidden>
      <div class="total">
        <span id="pat-total"></span>
        <small id="pat-variacion"></small>
      </div>
      <div id="pat-grafico" class="grafico"></div>
      <ul id="pat-cuentas" class="lista"></ul>
      <p id="pat-comun" class="nota"></p>
    </main>
```
  - Add `<script src="ui-patrimonio.js?v=5"></script>` before `app.js`.
  - Change every `?v=4` → `?v=5`.
  - **`sw.js`**: set `CACHE = "cuentas-v5"`; ASSETS use `?v=5` and add `./ui-patrimonio.js?v=5`. The lists in index.html and sw.js must match one-to-one.
  - **`styles.css`**: `.pestana` → add `font-size: 14px; padding: 8px 4px; white-space: nowrap;` so 4 tabs fit at 375 px.

- [ ] **Step 3: `app.js`**
1. `gruposVisibles`: after Piso, append `{ id: "patrimonio", nombre: "Patrimonio" }` if `App.estado.cuentas.some(function (c) { return c.owner === App.estado.usuario.id && (c.tipo === "ahorro" || c.tipo === "inversion"); })`.
2. `recargar`: the start becomes:
```js
    var e = App.estado;
    var esta = ++peticion;
    var propia = e.grupo === "piso" || e.grupo === "patrimonio";   // pestañas con carga y selector propios
    $("selector-mes").hidden = propia;
    $("vista-piso").hidden = e.grupo !== "piso";
    $("vista-patrimonio").hidden = e.grupo !== "patrimonio";
    if (propia) {
      $("vista-mes").hidden = true;
      $("vista-movs").hidden = true;
      return e.grupo === "piso" ? window.UiPiso.cargar() : window.UiPatrimonio.cargar();
    }
```
(keep the rest of recargar unchanged).

- [ ] **Step 4: `ui-patrimonio.js`**
```js
/* Cuentas de casa — pestaña Patrimonio: total, últimos 12 meses y desglose por cuenta. */
(function () {
  "use strict";
  var C = window.Calculos;
  var ICONOS = { inversion: "📈", ahorro: "🏦", corriente: "💳", efectivo: "💶" };
  var peticion = 0;
  function $(id) { return document.getElementById(id); }

  function cargar() {
    var App = window.App, e = App.estado, esta = ++peticion;
    var mias = e.cuentas.filter(function (c) { return c.owner === e.usuario.id; });
    var comun = e.cuentas.filter(function (c) { return c.owner === null && c.tipo === "corriente"; });
    var efectivo = mias.filter(function (c) { return c.tipo === "efectivo"; });
    var conSaldo = mias.filter(function (c) { return c.tipo !== "efectivo"; }).concat(comun);
    return Promise.all([
      conSaldo.length ? App.D.saldos(conSaldo.map(function (c) { return c.id; })) : Promise.resolve([]),
      efectivo.length ? App.D.movimientos(efectivo.map(function (c) { return c.id; }), "2000-01-01", "2100-01-01")
        : Promise.resolve([])
    ]).then(function (r) {
      if (esta !== peticion) return;
      var saldos = r[0];
      efectivo.forEach(function (c) { saldos = saldos.concat(C.saldosDesdeMovimientos(r[1], c.id)); });
      pintar(mias, comun, saldos);
    }).catch(function (err) { App.aviso("No se pudo cargar el patrimonio: " + err.message); });
  }

  function pintar(mias, comun, saldos) {
    var hoy = C.mesDe(C.fechaISO(new Date()));
    var meses = C.ultimosMeses(hoy, 12);
    var serie = C.patrimonioPorMes(saldos, mias.map(function (c) { return c.id; }), meses);
    var actual = serie[serie.length - 1], anterior = serie[serie.length - 2];
    $("pat-total").textContent = C.formatoEuros(actual.total);
    var dif = actual.total - anterior.total;
    $("pat-variacion").textContent = anterior.total ? (dif >= 0 ? "+" : "") + C.formatoEuros(dif) + " frente al mes anterior" : "";

    var max = Math.max.apply(null, serie.map(function (s) { return s.total; }).concat([1]));
    var g = $("pat-grafico");
    g.innerHTML = "";
    serie.forEach(function (s) {
      var col = document.createElement("div");
      col.className = "barra-mes" + (s.mes === hoy ? " actual" : "");
      col.title = C.nombreMes(s.mes) + ": " + C.formatoEuros(s.total);
      var barra = document.createElement("span");
      barra.style.height = Math.max(0, s.total) / max * 80 + "%";
      var etiqueta = document.createElement("small");
      etiqueta.textContent = C.nombreMes(s.mes).slice(0, 1);
      col.appendChild(barra);
      col.appendChild(etiqueta);
      g.appendChild(col);
    });

    var ul = $("pat-cuentas");
    ul.innerHTML = "";
    mias.forEach(function (c) {
      var dato = actual.porCuenta[c.id];
      var li = document.createElement("li");
      li.className = "fija";
      li.innerHTML = '<span class="icono"></span><div class="cuerpo"><span class="nombre"></span><small></small></div>' +
        '<span class="importe"></span>';
      li.querySelector(".icono").textContent = ICONOS[c.tipo] || "💳";
      li.querySelector(".nombre").textContent = c.nombre;
      li.querySelector("small").textContent = dato ? "a " + C.fechaCorta(dato.fecha) : "Sin datos todavía";
      li.querySelector(".importe").textContent = dato ? C.formatoEuros(dato.saldo_cent) : "—";
      ul.appendChild(li);
    });

    var comunHoy = C.patrimonioPorMes(saldos, comun.map(function (c) { return c.id; }), [hoy])[0];
    $("pat-comun").textContent = comun.length
      ? "Común (compartida, no suma a tu total): " + C.formatoEuros(comunHoy.total) : "";
  }

  window.UiPatrimonio = { cargar: cargar };
})();
```

- [ ] **Step 5: Verification offline:**
  - `node --check` on every changed or new JS file.
  - Every `$("…")` id used by ui-patrimonio.js and app.js exists in index.html.
  - The index.html ↔ sw.js asset lists match one-to-one.
  - Suites green: python 76; node 13.
  - Commit the files listed above with the message "Pestaña Patrimonio: total, 12 meses y desglose por cuenta; assets v5".

---

### After the plan (controller)
1. Verify `?demo=1` in the browser:
   - 4 tabs fit at 375 px;
   - Patrimonio shows total, variation, 12 bars, 6 accounts and the común line;
   - switching between tabs restores the views.
2. Create the 3 accounts in the DB (same rows as perfiles.sql).
3. Merge, push, and confirm Pages is serving v5.
4. Register the balances Xavi sends with `cuentas.py saldo … --fecha 2026-09-30`.
