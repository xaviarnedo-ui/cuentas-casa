# Cuentas de casa — Fase 1b (Efectivo, tickets, Piso, Formación) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ampliar la app para registrar el efectivo (con foto del ticket), ver la rentabilidad del piso alquilado en una pestaña propia y categorizar Formación. Además, preparar el SQL para que Xavi monte Supabase una sola vez.

**Architecture:** Mismas piezas que la fase 1. Los cambios en el SQL se aplican antes de su primera ejecución, así que no hacen falta migraciones. El piso se modela con categorías del grupo `piso`, privadas de Xavi (`categorias.owner`). Las fotos van a Supabase Storage (bucket privado `tickets`, ruta `<cuenta_id>/<uuid>.jpg`), protegidas con la misma regla `puede_ver_cuenta`. Los cálculos del piso son una función pura en `calculos.js`.

**Tech Stack:** igual que la fase 1 (Python 3.9 + unittest; Supabase Postgres/Auth/RLS/Storage; JS vanilla + supabase-js vendorizado; `node --test`).

**Spec:** `docs/superpowers/specs/2026-10-04-cuentas-casa-design.md` (sección 9 = esta ampliación)

## Global Constraints

- Importes en céntimos enteros; negativo = sale dinero. Gasto = −(suma) de movimientos con `no_es_gasto = false` y categoría `cuenta_como_gasto = true` o sin categoría.
- Categorías del piso: `piso-alquiler`, `piso-luz-gas`, `piso-agua`, `piso-comunidad`, `piso-ibi`, `piso-seguro`, `piso-reparaciones`, `piso-otros`. Todas tienen `cuenta_como_gasto = false`, `grupo = 'piso'` y `owner` = Xavi.
- Rendimiento neto del piso = alquiler − (comunidad + IBI + seguro + reparaciones + otros). Los suministros NO entran en el rendimiento.
- Agua: una factura (cargo `piso-agua` negativo) está devuelta si hay un `piso-agua` positivo con el mismo importe exacto en los 45 días siguientes (emparejamiento uno a uno, por orden de fecha).
- Alquiler: 950 € (`95000`), en efectivo.
- Cuenta de efectivo: id `efectivo`, tipo `efectivo`, dueño Xavi. Su saldo es la suma de todos sus movimientos.
- Fotos: JPEG, lado máximo 1600 px, calidad 0,7, bucket privado `tickets`, máximo 5 MB.
- No poner nombres reales de terceros (inquilina, profesores, familia) en el repo: van en reglas de la BD.
- Python: solo stdlib + `fitz` (el importador). JS: IIFE + `"use strict"`, `var`/`function`, sin build. Textos en español.
- Tests: `python3 -m unittest discover -s tests -t .` y `node --test tests/calculos.test.js`.
- Commits terminan con `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Añadir archivos explícitamente (nunca `git add -A`).

## Estructura de archivos

```
importador/revolut.py        (modificar) solo "Una recarga de…" es transferencia automática
tests/test_revolut.py        (modificar)
CLAUDE.md                    (modificar) cómo marcar transferencias propias con reglas
supabase/schema.sql          (modificar) efectivo, categorias.grupo/owner, ticket_path, storage
supabase/seed.sql            (modificar) categoría formacion
supabase/perfiles.sql        (modificar) cuenta efectivo + categorías piso de Xavi
supabase/test_rls.sql        (modificar) privacidad de categorías y tickets
calculos.js                  (modificar) sumarDias, resumenPiso
tests/calculos.test.js       (modificar)
tickets.js                   (crear)     reducir foto
datos.js / datos-demo.js     (reemplazar) + movimientosDeCategorias, subirTicket, urlTicket
app.js                       (modificar) Efectivo en "Mía", pestaña Piso, saldo efectivo, chips con callback
ui-mes.js                    (modificar) línea "En efectivo"
ui-piso.js                   (crear)     pestaña Piso
ui-nuevo.js                  (reemplazar) gasto/entrada, foto, atajo alquiler
ui-movs.js                   (modificar) ver/añadir ticket
index.html / styles.css / sw.js (modificar) nuevos elementos y versión ?v=2
```

---

### Task 1: Importador — las transferencias propias se deciden con reglas

**Files:**
- Modify: `importador/revolut.py:17`, `tests/test_revolut.py` (método `test_transferencias`), `CLAUDE.md`

**Interfaces:**
- Produces: `Movimiento.es_transferencia` es `True` solo cuando el título empieza por `"Una recarga de "`.

- [ ] **Step 1: Cambiar el test (RED)**

En `tests/test_revolut.py`, `test_transferencias` pasa a:
```python
    def test_transferencias(self):
        # Solo las recargas son transferencias automáticas; "Pago de"/"To" se deciden con reglas
        # (una transferencia a un tercero, p. ej. un profesor, es un gasto).
        self.assertEqual([m.es_transferencia for m in self.movs],
                         [False, True, False, False, False, False, False])
```
Run: `python3 -m unittest tests.test_revolut -v` → Expected: FAIL en `test_transferencias`.

- [ ] **Step 2: Implementar**

En `importador/revolut.py`:
```python
PREFIJOS_TRANSFERENCIA = ("Una recarga de ",)
```
Run: `python3 -m unittest discover -s tests -t .` → Expected: 28 OK.

- [ ] **Step 3: CLAUDE.md**

En `## Cuando Xavi pasa un extracto`, después del paso 2, añadir:
```markdown
   - Transferencias entre vuestras cuentas ("Pago de <Xavi/Andrea>", "To <Xavi/Andrea>", Bizum
     entre vosotros): regla con el trozo del nombre → `transferencias`. Una transferencia o Bizum a
     cualquier otra persona es un gasto/ingreso normal (p. ej. clases de inglés → `formacion`,
     Bizum de la inquilina → `piso-luz-gas` o `piso-agua`). Los nombres viven solo en las reglas
     de la BD, nunca en el repo.
```

- [ ] **Step 4: Commit**

```bash
git add importador/revolut.py tests/test_revolut.py CLAUDE.md
git commit -m "Transferencias propias por reglas: solo las recargas son automáticas

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: SQL — efectivo, categorías del piso, tickets y su prueba de privacidad

**Files:**
- Modify: `supabase/schema.sql`, `supabase/seed.sql`, `supabase/perfiles.sql`, `supabase/test_rls.sql`

**Interfaces:**
- Produces: `cuentas.tipo` admite `'efectivo'`; `categorias.grupo` (`null` | `'piso'`) y `categorias.owner` (`null` = de todos); `movimientos.ticket_path`, que la app puede insertar y actualizar; bucket `tickets`. Ids: cuenta `efectivo`; categorías `formacion` y las 8 `piso-*`.

- [ ] **Step 1: `schema.sql`**

1. En `cuentas`: `check (tipo in ('corriente', 'ahorro', 'inversion', 'efectivo'))`.
2. En `categorias`, tras `orden`:
```sql
  orden int not null default 0,
  grupo text check (grupo in ('piso')),      -- null = categoría normal
  owner uuid references auth.users           -- null = de todos; si no, solo la ve su dueño
```
3. En `movimientos`, tras `nota`: `ticket_path text,                         -- foto en Storage: <cuenta_id>/<uuid>.jpg`
4. La política de categorías pasa a:
```sql
create policy "categorias visibles" on categorias for select to authenticated
  using (es_de_casa() and (owner is null or owner = auth.uid()));
```
5. Grants (sustituyen a los actuales de movimientos):
```sql
revoke update on movimientos from authenticated;
grant update (categoria_id, nota, no_es_gasto, ticket_path) on movimientos to authenticated;
revoke insert on movimientos from authenticated;
grant insert (cuenta_id, fecha, importe_cent, descripcion, comercio, categoria_id, nota, no_es_gasto, origen, creado_por, ticket_path)
  on movimientos to authenticated;
```
6. Al final del archivo:
```sql
-- Fotos de tickets ---------------------------------------------------------------
-- Ruta <cuenta_id>/<uuid>.jpg: solo quien puede ver la cuenta ve o sube sus fotos.
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('tickets', 'tickets', false, 5242880, array['image/jpeg']);

create policy "ver tickets" on storage.objects for select to authenticated
  using (bucket_id = 'tickets' and public.puede_ver_cuenta(split_part(name, '/', 1)));
create policy "subir tickets" on storage.objects for insert to authenticated
  with check (bucket_id = 'tickets' and public.puede_ver_cuenta(split_part(name, '/', 1)));
```

- [ ] **Step 2: `seed.sql`** — la lista de categorías pasa a ser:
```sql
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
  ('formacion', 'Formación', '📚', true, 10),
  ('otros', 'Otros', '📦', true, 11),
  ('ingresos', 'Ingresos', '💶', false, 12),
  ('transferencias', 'Transferencias / Aportaciones', '🔁', false, 13);
```

- [ ] **Step 3: `perfiles.sql`** — entre el `insert into profiles …;` y el `select` final, insertar:
```sql
-- Lo privado de Xavi: su cuenta de efectivo y las categorías del piso alquilado.
insert into cuentas (id, nombre, banco, tipo, owner, orden)
select 'efectivo', 'Efectivo', 'Efectivo', 'efectivo', id, 2 from profiles where nombre = 'Xavi'
on conflict (id) do nothing;

insert into categorias (id, nombre, icono, cuenta_como_gasto, orden, grupo, owner)
select c.id, c.nombre, c.icono, false, c.orden, 'piso', p.id
from (values
  ('piso-alquiler', 'Piso · Alquiler', '🔑', 20),
  ('piso-luz-gas', 'Piso · Luz y gas', '💡', 21),
  ('piso-agua', 'Piso · Agua', '🚰', 22),
  ('piso-comunidad', 'Piso · Comunidad', '🏢', 23),
  ('piso-ibi', 'Piso · IBI', '🧾', 24),
  ('piso-seguro', 'Piso · Seguro', '🛡️', 25),
  ('piso-reparaciones', 'Piso · Reparaciones', '🔧', 26),
  ('piso-otros', 'Piso · Otros', '📎', 27)
) as c(id, nombre, icono, orden)
cross join profiles p
where p.nombre = 'Xavi'
on conflict (id) do nothing;
```

- [ ] **Step 4: `test_rls.sql`** — cambios (mantener todo lo existente):
1. No hacen falta variables nuevas: se reutilizan `cuenta_otro`, `cuenta_propia`, `yo` y `otro`.
2. En el bloque de datos de prueba, tras las reglas:
```sql
  insert into categorias (id, nombre, icono, owner) values
    ('test-cat-xavi', 'T', 'x', xavi), ('test-cat-andrea', 'T', 'x', andrea);
  -- Solo las filas de metadatos (sin fichero): bastan para probar las políticas de Storage.
  insert into storage.objects (bucket_id, name) values
    ('tickets', 'test-xavi/t.jpg'), ('tickets', 'test-andrea/t.jpg'), ('tickets', 'comun/t.jpg');
```
3. Dentro del bucle, tras las comprobaciones positivas existentes:
```sql
    select count(*) into n from categorias where owner = yo and id like 'test-cat-%';
    if n <> 1 then raise exception 'FALLO: % no ve su propia categoría', yo; end if;
    select count(*) into n from storage.objects where bucket_id = 'tickets' and name = cuenta_propia || '/t.jpg';
    if n <> 1 then raise exception 'FALLO: % no ve sus tickets', yo; end if;
    select count(*) into n from storage.objects where bucket_id = 'tickets' and name = 'comun/t.jpg';
    if n <> 1 then raise exception 'FALLO: % no ve los tickets de la común', yo; end if;
```
y tras las negativas existentes de `reglas`:
```sql
    select count(*) into n from categorias where owner = otro;
    if n <> 0 then raise exception 'FALLO: % ve categorías privadas del otro', yo; end if;
    select count(*) into n from storage.objects where bucket_id = 'tickets' and name = cuenta_otro || '/t.jpg';
    if n <> 0 then raise exception 'FALLO: % ve tickets privados del otro', yo; end if;
    begin
      insert into storage.objects (bucket_id, name) values ('tickets', cuenta_otro || '/hack.jpg');
      raise exception 'FALLO: % puede subir tickets a la cuenta del otro', yo;
    exception when insufficient_privilege then null;
    end;
```
y tras `if n <> 1 then raise exception 'FALLO: % no puede recategorizar la común', yo; end if;`:
```sql
    update movimientos set ticket_path = 'comun/t.jpg' where huella = 'test-3';
    get diagnostics n = row_count;
    if n <> 1 then raise exception 'FALLO: % no puede adjuntar un ticket', yo; end if;
```
4. En el bloque del extraño, antes del `raise exception 'RLS_OK…'`:
```sql
  select count(*) into n from storage.objects where bucket_id = 'tickets';
  if n <> 0 then raise exception 'FALLO: un extraño ve tickets'; end if;
```

- [ ] **Step 5: Revisión por lectura** (no hay BD): cada `select`/`insert` nuevo usa columnas que existen; los nombres de los objetos de prueba empiezan por un id de cuenta que existe (`test-xavi`, `test-andrea`, `comun`).

- [ ] **Step 6: Commit**

```bash
git add supabase/schema.sql supabase/seed.sql supabase/perfiles.sql supabase/test_rls.sql
git commit -m "SQL: efectivo, categorías del piso privadas, Formación y tickets en Storage

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Cálculos del piso (`calculos.js`)

**Files:**
- Modify: `calculos.js`, `tests/calculos.test.js`

**Interfaces:**
- Produces:
  - `sumarDias("2026-01-30", 45) -> "2026-03-16"`.
  - `resumenPiso(movs, anio) -> { alquiler, gastos: [{categoria_id, total}], neto, luzGas: {pagado, devuelto, diferencia}, agua: {…}, meses: [{mes, alquiler: bool, cuotaLuzGas: bool, bizumLuzGas: bool}] (12), facturasAgua: [{fecha, importe, devuelta, fechaBizum}] }`.
  - Los `movs` llevan `id`, `fecha`, `importe_cent` y `categoria_id`; pueden incluir días del año siguiente (Bizum de una factura de diciembre).

- [ ] **Step 1: Tests (RED)** — añadir al final de `tests/calculos.test.js`:
```js
const p = (id, fecha, importe_cent, categoria_id) => ({ id, fecha, importe_cent, categoria_id });

test("sumarDias", () => {
  assert.strictEqual(C.sumarDias("2026-01-30", 45), "2026-03-16");
  assert.strictEqual(C.sumarDias("2026-12-20", 15), "2027-01-04");
});

test("resumenPiso: rendimiento, suministros y control", () => {
  const movs = [
    p("1", "2026-01-02", 95000, "piso-alquiler"),
    p("2", "2026-02-02", 95000, "piso-alquiler"),
    p("3", "2026-01-10", -4500, "piso-comunidad"),
    p("4", "2026-06-15", -32000, "piso-ibi"),
    p("5", "2026-01-05", -6000, "piso-luz-gas"),
    p("6", "2026-01-12", 5230, "piso-luz-gas"),
    p("7", "2026-02-05", -6000, "piso-luz-gas"),
    p("8", "2026-02-20", -3540, "piso-agua"),
    p("9", "2026-02-25", 3540, "piso-agua"),
    p("10", "2026-04-20", -2900, "piso-agua"),
    p("11", "2025-12-30", 95000, "piso-alquiler")
  ];
  const r = C.resumenPiso(movs, 2026);
  assert.strictEqual(r.alquiler, 190000);
  assert.deepStrictEqual(r.gastos, [
    { categoria_id: "piso-ibi", total: 32000 },
    { categoria_id: "piso-comunidad", total: 4500 }
  ]);
  assert.strictEqual(r.neto, 190000 - 36500);
  assert.deepStrictEqual(r.luzGas, { pagado: 12000, devuelto: 5230, diferencia: -6770 });
  assert.deepStrictEqual(r.agua, { pagado: 6440, devuelto: 3540, diferencia: -2900 });
  assert.strictEqual(r.meses.length, 12);
  assert.deepStrictEqual(r.meses[0], { mes: "2026-01", alquiler: true, cuotaLuzGas: true, bizumLuzGas: true });
  assert.deepStrictEqual(r.meses[1], { mes: "2026-02", alquiler: true, cuotaLuzGas: true, bizumLuzGas: false });
  assert.deepStrictEqual(r.facturasAgua, [
    { fecha: "2026-02-20", importe: 3540, devuelta: true, fechaBizum: "2026-02-25" },
    { fecha: "2026-04-20", importe: 2900, devuelta: false, fechaBizum: null }
  ]);
});

test("resumenPiso: el Bizum de agua solo cuenta en 45 días y una vez", () => {
  const movs = [
    p("a", "2026-01-10", -3000, "piso-agua"),
    p("b", "2026-03-10", -3000, "piso-agua"),
    p("c", "2026-03-12", 3000, "piso-agua"),
    p("d", "2026-12-20", -2500, "piso-agua"),
    p("e", "2027-01-08", 2500, "piso-agua")
  ];
  assert.deepStrictEqual(C.resumenPiso(movs, 2026).facturasAgua, [
    { fecha: "2026-01-10", importe: 3000, devuelta: false, fechaBizum: null },
    { fecha: "2026-03-10", importe: 3000, devuelta: true, fechaBizum: "2026-03-12" },
    { fecha: "2026-12-20", importe: 2500, devuelta: true, fechaBizum: "2027-01-08" }
  ]);
});
```
Run: `node --test tests/calculos.test.js` → Expected: FAIL (`C.sumarDias is not a function`).

- [ ] **Step 2: Implementar** — en `calculos.js`, antes de `var api = {`:
```js
  function sumarDias(fecha, n) {
    var d = new Date(fecha + "T00:00:00Z");
    d.setUTCDate(d.getUTCDate() + n);
    return d.toISOString().slice(0, 10);
  }

  var PISO_GASTOS = ["piso-comunidad", "piso-ibi", "piso-seguro", "piso-reparaciones", "piso-otros"];
  var DIAS_BIZUM_AGUA = 45;

  // Una factura de agua está devuelta si llega un Bizum por el mismo importe en los 45 días siguientes.
  function facturasAgua(movs, anio) {
    var agua = movs.filter(function (m) { return m.categoria_id === "piso-agua"; })
      .sort(function (a, b) { return a.fecha < b.fecha ? -1 : a.fecha > b.fecha ? 1 : 0; });
    var usados = {};
    return agua.filter(function (m) { return m.importe_cent < 0; }).map(function (f) {
      var limite = sumarDias(f.fecha, DIAS_BIZUM_AGUA);
      var bizum = agua.find(function (b) {
        return b.importe_cent === -f.importe_cent && !usados[b.id] && b.fecha >= f.fecha && b.fecha <= limite;
      });
      if (bizum) usados[bizum.id] = true;
      return { fecha: f.fecha, importe: -f.importe_cent, devuelta: !!bizum, fechaBizum: bizum ? bizum.fecha : null };
    }).filter(function (f) { return f.fecha.slice(0, 4) === String(anio); });
  }

  // Rendimiento = alquiler − gastos del piso. Los suministros son un pase de dinero: van aparte.
  function resumenPiso(movs, anio) {
    var delAnio = movs.filter(function (m) { return m.fecha.slice(0, 4) === String(anio); });
    function suma(cat, signo) {  // signo 1: solo entradas; −1: solo salidas; 0: todo
      return delAnio.reduce(function (s, m) {
        if (m.categoria_id !== cat || (signo > 0 && m.importe_cent <= 0) || (signo < 0 && m.importe_cent >= 0)) return s;
        return s + m.importe_cent;
      }, 0);
    }
    function suministro(cat) {
      var pagado = -suma(cat, -1), devuelto = suma(cat, 1);
      return { pagado: pagado, devuelto: devuelto, diferencia: devuelto - pagado };
    }
    var alquiler = suma("piso-alquiler", 0);
    var gastos = PISO_GASTOS.map(function (c) { return { categoria_id: c, total: -suma(c, 0) }; })
      .filter(function (g) { return g.total !== 0; })
      .sort(function (a, b) { return b.total - a.total; });
    var totalGastos = gastos.reduce(function (s, g) { return s + g.total; }, 0);
    var meses = [];
    for (var i = 1; i <= 12; i++) {
      var mes = anio + "-" + dos(i);
      var enMes = delAnio.filter(function (m) { return mesDe(m.fecha) === mes; });
      meses.push({
        mes: mes,
        alquiler: enMes.some(function (m) { return m.categoria_id === "piso-alquiler" && m.importe_cent > 0; }),
        cuotaLuzGas: enMes.some(function (m) { return m.categoria_id === "piso-luz-gas" && m.importe_cent < 0; }),
        bizumLuzGas: enMes.some(function (m) { return m.categoria_id === "piso-luz-gas" && m.importe_cent > 0; })
      });
    }
    return { alquiler: alquiler, gastos: gastos, neto: alquiler - totalGastos,
             luzGas: suministro("piso-luz-gas"), agua: suministro("piso-agua"),
             meses: meses, facturasAgua: facturasAgua(movs, anio) };
  }
```
y añadir `sumarDias: sumarDias, resumenPiso: resumenPiso` al objeto `api`.

Run: `node --test tests/calculos.test.js` → Expected: `pass 10`, `fail 0`.

- [ ] **Step 3: Commit**

```bash
git add calculos.js tests/calculos.test.js
git commit -m "Cálculos del piso: rendimiento, suministros y facturas de agua

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Capa de datos — consultas por categoría, tickets y demo ampliada

**Files:**
- Create: `tickets.js`
- Modify: `datos.js`, `datos-demo.js`

**Interfaces:**
- Produces (en `window.Datos` y en `window.DatosDemo`, con la misma forma):
  - `movimientosDeCategorias(catIds, desde, hastaExclusivo) -> Promise<mov[]>` (fecha descendente)
  - `subirTicket(cuentaId, blob) -> Promise<ruta>`
  - `urlTicket(ruta) -> Promise<url>`
  - Todo lo demás, sin cambios.
- Produces: `window.Tickets.reducir(archivo) -> Promise<Blob JPEG>`.
- La demo tiene la cuenta `efectivo` (dueño `demo-xavi`), `formacion` y las 8 `piso-*` (`grupo: "piso"`, `owner: "demo-xavi"`), con un año de movimientos del piso.

- [ ] **Step 1: `tickets.js`**
```js
/* Cuentas de casa — reduce la foto de un ticket antes de subirla (lado máximo 1600 px, JPEG 0,7). */
(function () {
  "use strict";
  var LADO_MAX = 1600, CALIDAD = 0.7;

  function reducir(archivo) {
    return createImageBitmap(archivo).then(function (img) {
      var escala = Math.min(1, LADO_MAX / Math.max(img.width, img.height));
      var lienzo = document.createElement("canvas");
      lienzo.width = Math.round(img.width * escala);
      lienzo.height = Math.round(img.height * escala);
      lienzo.getContext("2d").drawImage(img, 0, 0, lienzo.width, lienzo.height);
      return new Promise(function (resolver, rechazar) {
        lienzo.toBlob(function (blob) {
          if (blob) resolver(blob); else rechazar(new Error("No se pudo procesar la foto"));
        }, "image/jpeg", CALIDAD);
      });
    });
  }

  window.Tickets = { reducir: reducir };
})();
```

- [ ] **Step 2: `datos.js`** (sustituir el archivo entero)
```js
/* Cuentas de casa — acceso a Supabase. Todo devuelve promesas; los errores se lanzan como Error. */
(function () {
  "use strict";
  var db = window.CUENTAS_DB;
  function ok(r) { if (r.error) throw new Error(r.error.message); return r.data; }

  // Pide de 1000 en 1000 con un orden total (fecha, created_at, id) para no saltar ni repetir filas.
  function paginado(consulta) {
    var filas = [];
    function pagina(inicio) {
      return consulta()
        .order("fecha", { ascending: false }).order("created_at", { ascending: false }).order("id", { ascending: false })
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
    movimientos: function (cuentaIds, desde, hasta) {
      return paginado(function () {
        return db.from("movimientos").select("*").in("cuenta_id", cuentaIds).gte("fecha", desde).lt("fecha", hasta);
      });
    },
    movimientosDeCategorias: function (catIds, desde, hasta) {
      return paginado(function () {
        return db.from("movimientos").select("*").in("categoria_id", catIds).gte("fecha", desde).lt("fecha", hasta);
      });
    },
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
    borrarMovimiento: function (id) { return db.from("movimientos").delete().eq("id", id).then(ok); },
    subirTicket: function (cuentaId, blob) {
      var ruta = cuentaId + "/" + crypto.randomUUID() + ".jpg";
      return db.storage.from("tickets").upload(ruta, blob, { contentType: "image/jpeg" })
        .then(ok).then(function () { return ruta; });
    },
    urlTicket: function (ruta) {
      return db.storage.from("tickets").createSignedUrl(ruta, 3600).then(ok)
        .then(function (d) { return d.signedUrl; });
    }
  };
})();
```

- [ ] **Step 3: `datos-demo.js`** (sustituir el archivo entero)
```js
/* Cuentas de casa — datos de ejemplo en memoria para ver la app sin Supabase: index.html?demo=1 */
(function () {
  "use strict";
  var C = window.Calculos;
  var YO = { id: "demo-xavi", email: "demo@ejemplo.com" };
  var cuentas = [
    { id: "comun", nombre: "Común", banco: "Revolut", tipo: "corriente", owner: null, orden: 1 },
    { id: "xavi", nombre: "Xavi", banco: "CaixaBank", tipo: "corriente", owner: "demo-xavi", orden: 2 },
    { id: "efectivo", nombre: "Efectivo", banco: "Efectivo", tipo: "efectivo", owner: "demo-xavi", orden: 3 }
  ];
  var categorias = [
    ["super", "Súper", "🛒", true], ["casa", "Casa", "🏠", true], ["restaurantes", "Restaurantes", "🍽️", true],
    ["ocio", "Ocio", "🎉", true], ["transporte", "Transporte", "🚗", true], ["salud", "Salud", "💊", true],
    ["compras", "Compras", "🛍️", true], ["suscripciones", "Suscripciones", "📺", true],
    ["viajes", "Viajes", "✈️", true], ["formacion", "Formación", "📚", true], ["otros", "Otros", "📦", true],
    ["ingresos", "Ingresos", "💶", false], ["transferencias", "Transferencias / Aportaciones", "🔁", false]
  ].map(function (c, i) {
    return { id: c[0], nombre: c[1], icono: c[2], cuenta_como_gasto: c[3], orden: i + 1, grupo: null, owner: null };
  }).concat([
    ["piso-alquiler", "Piso · Alquiler", "🔑"], ["piso-luz-gas", "Piso · Luz y gas", "💡"],
    ["piso-agua", "Piso · Agua", "🚰"], ["piso-comunidad", "Piso · Comunidad", "🏢"], ["piso-ibi", "Piso · IBI", "🧾"],
    ["piso-seguro", "Piso · Seguro", "🛡️"], ["piso-reparaciones", "Piso · Reparaciones", "🔧"],
    ["piso-otros", "Piso · Otros", "📎"]
  ].map(function (c, i) {
    return { id: c[0], nombre: c[1], icono: c[2], cuenta_como_gasto: false, orden: 20 + i, grupo: "piso", owner: YO.id };
  }));
  var plantilla = [
    ["Mercadona", "super", -6237], ["Mercadona", "super", -4706], ["Netflix", "suscripciones", -1499],
    ["Galp", "transporte", -2000], ["Don Pedro Cafe Bistro", "restaurantes", -4730], ["H&M", "compras", -2297],
    ["Farmacia Magdalena", "salud", -320], ["Bar nuevo", null, -850], ["Pago de Xavi", "transferencias", 50000]
  ];
  var movs = [], n = 0, fotos = {};
  var mesActual = C.mesDe(C.fechaISO(new Date()));
  var anio = mesActual.slice(0, 4), mesNum = Number(mesActual.slice(5, 7));

  function apunte(cuenta, fecha, importe, comercio, cat) {
    n++;
    var manual = cuenta === "efectivo";
    movs.push({ id: "m" + n, cuenta_id: cuenta, fecha: fecha, importe_cent: importe, comercio: comercio,
      descripcion: comercio, categoria_id: cat, nota: "", no_es_gasto: false, origen: manual ? "manual" : "import",
      creado_por: manual ? YO.id : null, ticket_path: null });
  }

  [3, 2, 1, 0].forEach(function (atras, i) {
    var mes = C.moverMes(mesActual, -atras);
    plantilla.forEach(function (p, j) {
      ["comun", "xavi"].forEach(function (cuenta, k) {
        apunte(cuenta, mes + "-" + String(1 + (j * 3) % 27).padStart(2, "0"),
          Math.round(p[2] * (1 + 0.1 * i) * (k ? 0.5 : 1)), p[0], p[1]);
        movs[movs.length - 1].descripcion = p[0] + " · Palma";
      });
    });
  });

  // Un año de piso: alquiler en efectivo, cuota de Iberdrola + Bizum de la factura real,
  // agua cada dos meses con su Bizum (el último aún pendiente), comunidad e IBI.
  apunte("efectivo", anio + "-01-01", 120000, "Saldo inicial", "transferencias");
  for (var mes = 1; mes <= mesNum; mes++) {
    var m = anio + "-" + String(mes).padStart(2, "0");
    apunte("efectivo", m + "-02", 95000, "Alquiler", "piso-alquiler");
    apunte("xavi", m + "-05", -6000, "Iberdrola", "piso-luz-gas");
    if (mes < mesNum) apunte("xavi", m + "-12", 5000 + mes * 150, "Bizum inquilina", "piso-luz-gas");
    apunte("xavi", m + "-10", -4500, "Comunidad", "piso-comunidad");
    if (mes % 2 === 0) {
      apunte("xavi", m + "-20", -3540, "Agua", "piso-agua");
      if (mes < mesNum) apunte("xavi", m + "-25", 3540, "Bizum inquilina", "piso-agua");
    }
  }
  apunte("xavi", anio + "-06-15", -32000, "IBI", "piso-ibi");
  apunte("efectivo", mesActual + "-03", -1250, "Ferretería", "casa");

  function ok(v) { return Promise.resolve(v === undefined ? null : JSON.parse(JSON.stringify(v))); }
  function porFechaDesc(lista) {
    return lista.sort(function (a, b) { return a.fecha < b.fecha ? 1 : a.fecha > b.fecha ? -1 : 0; });
  }

  window.DatosDemo = {
    usuario: function () { return ok(YO); },
    entrar: function () { return ok(YO); },
    salir: function () { return ok(); },
    cuentas: function () { return ok(cuentas); },
    categorias: function () { return ok(categorias); },
    movimientos: function (ids, desde, hasta) {
      return ok(porFechaDesc(movs.filter(function (m) {
        return ids.indexOf(m.cuenta_id) >= 0 && m.fecha >= desde && m.fecha < hasta;
      })));
    },
    movimientosDeCategorias: function (catIds, desde, hasta) {
      return ok(porFechaDesc(movs.filter(function (m) {
        return catIds.indexOf(m.categoria_id) >= 0 && m.fecha >= desde && m.fecha < hasta;
      })));
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
      movs.push(Object.assign({ id: "m" + n, descripcion: "", nota: "", no_es_gasto: false, ticket_path: null }, fila));
      return ok();
    },
    borrarMovimiento: function (id) {
      movs = movs.filter(function (m) { return m.id !== id; });
      return ok();
    },
    subirTicket: function (cuentaId, blob) {
      var ruta = cuentaId + "/demo-" + (++n) + ".jpg";
      fotos[ruta] = URL.createObjectURL(blob);
      return ok(ruta);
    },
    urlTicket: function (ruta) { return Promise.resolve(fotos[ruta] || null); }
  };
})();
```

- [ ] **Step 4: Verificación offline:** `node --check` de los tres archivos; los dos test suites siguen verdes.

- [ ] **Step 5: Commit**

```bash
git add tickets.js datos.js datos-demo.js
git commit -m "Datos: consultas por categoría, tickets en Storage y demo con efectivo y piso

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Efectivo en "Mía" y pestaña Piso (estructura y pantalla)

**Files:**
- Modify: `app.js`, `ui-mes.js`, `index.html`, `styles.css`
- Create: `ui-piso.js`

**Interfaces:**
- Consumes: `Datos.movimientos`, `Datos.movimientosDeCategorias` (Task 4); `Calculos.resumenPiso` (Task 3).
- Produces:
  - `App.cuentasDelGrupo("mia")` incluye las cuentas de tipo `efectivo`.
  - Grupo/pestaña `"piso"`, visible si alguna categoría de `catsLista` tiene `grupo === "piso"`.
  - `App.estado.saldoEfectivo` (céntimos, o `null`).
  - `App.chips(cont, sel, lista, alElegir)`: el 4º parámetro es opcional y se llama con el id elegido.
  - `window.UiPiso.cargar()`.

- [ ] **Step 1: `index.html`**
1. `<div class="selector-mes">` (el del mes) → `<div id="selector-mes" class="selector-mes">`.
2. Tras `<small id="comparacion"></small>` y dentro de `.total`: `<small id="saldo-efectivo" class="saldo-efectivo" hidden></small>`.
3. Tras `</main>` de `vista-movs`:
```html
    <main id="vista-piso" hidden>
      <div class="selector-mes">
        <button id="piso-ant" type="button" aria-label="Año anterior">‹</button>
        <h1 id="piso-anio"></h1>
        <button id="piso-sig" type="button" aria-label="Año siguiente">›</button>
      </div>
      <div class="total">
        <span id="piso-neto"></span>
        <small>Rendimiento neto del año</small>
      </div>
      <h2 class="seccion">Ingresos y gastos</h2>
      <ul class="lista">
        <li class="fija"><span class="icono">🔑</span><div class="cuerpo"><span class="nombre">Alquiler cobrado</span></div><span id="piso-alquiler" class="importe positivo"></span></li>
      </ul>
      <ul id="piso-gastos" class="lista"></ul>
      <h2 class="seccion">Suministros</h2>
      <ul class="lista">
        <li class="fija"><span class="icono">💡</span><div class="cuerpo"><span class="nombre">Luz y gas</span><small id="piso-luzgas-detalle"></small></div><span id="piso-luzgas-dif" class="importe"></span></li>
        <li class="fija"><span class="icono">🚰</span><div class="cuerpo"><span class="nombre">Agua</span><small id="piso-agua-detalle"></small></div><span id="piso-agua-dif" class="importe"></span></li>
      </ul>
      <p class="nota">La diferencia de luz y gas se compensa con la regularización anual de Iberdrola.</p>
      <h2 class="seccion">Mes a mes</h2>
      <ul id="piso-meses" class="lista"></ul>
      <h2 class="seccion">Facturas de agua</h2>
      <ul id="piso-facturas-agua" class="lista"></ul>
    </main>
```
4. Scripts: añadir `<script src="ui-piso.js?v=1"></script>` antes de `app.js` (la versión se sube en el Task 8).

- [ ] **Step 2: `styles.css`** — añadir al final:
```css
.saldo-efectivo { display: block; margin-top: 4px; color: var(--texto); font-weight: 600; }
.seccion { font-size: 15px; color: var(--suave); margin: 20px 4px 8px; font-weight: 600; }
.nota { color: var(--suave); font-size: 13px; margin: 6px 4px 0; }
.lista + .lista { margin-top: 8px; }
.lista li.fija { cursor: default; }
.marcas { display: flex; gap: 14px; font-size: 14px; color: var(--suave); }
.signo { display: flex; gap: 6px; margin: 8px 0; }
.foto { display: inline-block; color: var(--acento); padding: 8px 0; cursor: pointer; }
.ticket-img { display: block; max-width: 100%; max-height: 240px; border-radius: 12px; margin: 8px 0; cursor: zoom-in; }
```

- [ ] **Step 3: `app.js`** — cambios:
1. `cuentasDelGrupo`:
```js
  function cuentasDelGrupo(grupo) {
    var e = App.estado;
    return e.cuentas.filter(function (c) {
      if (c.tipo !== "corriente" && c.tipo !== "efectivo") return false;
      return grupo === "comun" ? c.owner === null : c.owner === e.usuario.id;
    });
  }
```
2. `gruposVisibles`:
```js
  function gruposVisibles() {
    var tienePiso = App.estado.catsLista.some(function (c) { return c.grupo === "piso"; });
    return [{ id: "comun", nombre: "Común" }, { id: "mia", nombre: "Mía" }]
      .filter(function (g) { return cuentasDelGrupo(g.id).length > 0; })
      .concat(tienePiso ? [{ id: "piso", nombre: "Piso" }] : []);
  }
```
3. `recargar` (sustituir entera):
```js
  // Carga el mes elegido y los 6 anteriores (gráfico, comparación y variación por categoría).
  // En "Mía" también el saldo de efectivo (todos sus movimientos). La pestaña Piso tiene su propia carga.
  function recargar() {
    var e = App.estado;
    var esta = ++peticion;
    var piso = e.grupo === "piso";
    $("selector-mes").hidden = piso;
    $("vista-piso").hidden = !piso;
    if (piso) {
      $("vista-mes").hidden = true;
      $("vista-movs").hidden = true;
      return window.UiPiso.cargar();
    }
    if ($("vista-movs").hidden) $("vista-mes").hidden = false;
    $("sin-cuentas").hidden = !!e.grupo;
    if (!e.grupo) { e.movs = []; e.saldoEfectivo = null; pintar(); return Promise.resolve(); }
    var ids = cuentasDelGrupo(e.grupo).map(function (c) { return c.id; });
    var efectivo = e.grupo === "mia" ? cuentasDelGrupo("mia").filter(function (c) { return c.tipo === "efectivo"; })
      .map(function (c) { return c.id; }) : [];
    return Promise.all([
      D.movimientos(ids, C.moverMes(e.mes, -6) + "-01", C.moverMes(e.mes, 1) + "-01"),
      efectivo.length ? D.movimientos(efectivo, "2000-01-01", "2100-01-01") : Promise.resolve(null)
    ]).then(function (r) {
      if (esta !== peticion) return;
      e.movs = r[0];
      e.saldoEfectivo = r[1] === null ? null : r[1].reduce(function (s, m) { return s + m.importe_cent; }, 0);
      pintar();
    }).catch(function (err) { aviso("No se pudieron cargar los datos: " + err.message); });
  }
```
4. Añadir `saldoEfectivo: null` a `App.estado`.
5. `chips`: firma `function chips(cont, seleccionada, lista, alElegir)`; en el listener del botón, tras `b.classList.add("elegida");`, añadir `if (alElegir) alElegir(c.id);`.

- [ ] **Step 4: `ui-mes.js`** — al final de `pintar()`, añadir:
```js
    var se = $("saldo-efectivo");
    se.hidden = e.grupo !== "mia" || e.saldoEfectivo === null || e.saldoEfectivo === undefined;
    if (!se.hidden) se.textContent = "💶 En efectivo: " + C.formatoEuros(e.saldoEfectivo);
```

- [ ] **Step 5: `ui-piso.js`**
```js
/* Cuentas de casa — pestaña Piso: rendimiento del año, suministros y control mes a mes. */
(function () {
  "use strict";
  var C = window.Calculos;
  var anio = new Date().getFullYear();
  var peticion = 0;
  function $(id) { return document.getElementById(id); }

  function cargar() {
    var App = window.App, esta = ++peticion;
    var ids = App.estado.catsLista.filter(function (c) { return c.grupo === "piso"; }).map(function (c) { return c.id; });
    $("piso-anio").textContent = anio;
    // Hasta mediados de febrero del año siguiente: ahí puede llegar el Bizum de una factura de diciembre.
    return App.D.movimientosDeCategorias(ids, anio + "-01-01", (anio + 1) + "-02-15")
      .then(function (movs) { if (esta === peticion) pintar(C.resumenPiso(movs, anio)); })
      .catch(function (err) { App.aviso("No se pudieron cargar los datos del piso: " + err.message); });
  }

  function fila(icono, nombre, detalle, importe, claseImporte) {
    var li = document.createElement("li");
    li.className = "fija";
    li.innerHTML = '<span class="icono"></span><div class="cuerpo"><span class="nombre"></span><small></small></div>' +
      '<span class="importe"></span>';
    li.querySelector(".icono").textContent = icono;
    li.querySelector(".nombre").textContent = nombre;
    li.querySelector("small").textContent = detalle;
    li.querySelector(".importe").textContent = importe;
    if (claseImporte) li.querySelector(".importe").classList.add(claseImporte);
    return li;
  }

  function diferencia(cent) {
    if (cent === 0) return "En paz";
    return (cent > 0 ? "+" : "") + C.formatoEuros(cent) + (cent > 0 ? " a tu favor" : " en contra");
  }

  function pintarSuministro(prefijo, s) {
    $(prefijo + "-detalle").textContent = "Pagado " + C.formatoEuros(s.pagado) + " · Devuelto " + C.formatoEuros(s.devuelto);
    $(prefijo + "-dif").textContent = diferencia(s.diferencia);
  }

  function pintar(r) {
    var cats = window.App.estado.cats;
    $("piso-neto").textContent = C.formatoEuros(r.neto);
    $("piso-alquiler").textContent = C.formatoEuros(r.alquiler);

    var gastos = $("piso-gastos");
    gastos.innerHTML = "";
    if (!r.gastos.length) gastos.innerHTML = '<li class="vacio">Sin gastos del piso este año</li>';
    r.gastos.forEach(function (g) {
      var cat = cats[g.categoria_id];
      gastos.appendChild(fila(cat ? cat.icono : "📎", cat ? cat.nombre : g.categoria_id, "", "-" + C.formatoEuros(g.total)));
    });

    pintarSuministro("piso-luzgas", r.luzGas);
    pintarSuministro("piso-agua", r.agua);

    var meses = $("piso-meses");
    meses.innerHTML = "";
    var hoy = C.mesDe(C.fechaISO(new Date()));
    r.meses.filter(function (m) { return m.mes <= hoy; }).reverse().forEach(function (m) {
      var luz = m.bizumLuzGas ? "✅" : m.cuotaLuzGas ? "⏳" : "—";
      var li = fila("📅", C.nombreMes(m.mes), "", "", null);
      li.querySelector(".importe").outerHTML = '<span class="marcas"><span>Alquiler ' + (m.alquiler ? "✅" : "⏳") +
        '</span><span>Luz y gas ' + luz + "</span></span>";
      meses.appendChild(li);
    });
    if (!meses.children.length) meses.innerHTML = '<li class="vacio">Sin meses todavía</li>';

    var agua = $("piso-facturas-agua");
    agua.innerHTML = "";
    if (!r.facturasAgua.length) agua.innerHTML = '<li class="vacio">Sin facturas de agua este año</li>';
    r.facturasAgua.forEach(function (f) {
      agua.appendChild(fila(f.devuelta ? "✅" : "⏳", C.fechaCorta(f.fecha),
        f.devuelta ? "Bizum el " + C.fechaCorta(f.fechaBizum) : "Pendiente de Bizum", C.formatoEuros(f.importe), null));
    });
  }

  $("piso-ant").addEventListener("click", function () { anio--; cargar(); });
  $("piso-sig").addEventListener("click", function () { anio++; cargar(); });

  window.UiPiso = { cargar: cargar };
})();
```
(El `outerHTML` de la fila del mes solo inserta texto fijo: no lleva datos del usuario.)

- [ ] **Step 6: Verificación offline:**
  - `node --check` de app.js, ui-mes.js y ui-piso.js.
  - Cada id usado en `$("…")` existe en index.html.
  - Los dos test suites siguen verdes.

- [ ] **Step 7: Commit**

```bash
git add app.js ui-mes.js ui-piso.js index.html styles.css
git commit -m "Efectivo en Mía y pestaña Piso: rendimiento, suministros y control mes a mes

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Apuntar a mano — gasto/entrada, foto del ticket y atajo del alquiler

**Files:**
- Modify: `index.html` (hoja `hoja-nuevo`), `ui-nuevo.js` (sustituir entero)

**Interfaces:**
- Consumes: `App.chips(…, alElegir)` (Task 5), `Tickets.reducir`, `D.subirTicket` (Task 4).

- [ ] **Step 1: `index.html`**, dentro de `<form id="nu-form">`:
  - Tras `<h2>Apuntar a mano</h2>`: `<button id="nu-alquiler" type="button" class="enlace" hidden>🔑 Alquiler cobrado (950 €)</button>`
  - Tras el input `nu-importe`: `<div class="signo"><button id="nu-gasto" type="button" class="chip elegida">− Gasto</button><button id="nu-entrada" type="button" class="chip">+ Entrada</button></div>`
  - Tras el input `nu-nota`: `<label class="foto"><input id="nu-foto" type="file" accept="image/*" hidden><span id="nu-foto-txt">📷 Añadir ticket</span></label>`

- [ ] **Step 2: `ui-nuevo.js`**
```js
/* Cuentas de casa — hoja "Apuntar a mano": gasto o entrada, foto opcional del ticket y atajo del alquiler. */
(function () {
  "use strict";
  var C = window.Calculos;
  var ALQUILER_CENT = 95000;
  var ENTRADAS = { "ingresos": true, "piso-alquiler": true };  // al elegirlas, el apunte pasa a entrada
  var entrada = false;
  function $(id) { return document.getElementById(id); }

  function ponerSigno(esEntrada) {
    entrada = esEntrada;
    $("nu-entrada").classList.toggle("elegida", esEntrada);
    $("nu-gasto").classList.toggle("elegida", !esEntrada);
  }

  function cuentaEfectivo() {
    return window.App.cuentasDelGrupo("mia").find(function (c) { return c.tipo === "efectivo"; });
  }

  function abrir() {
    var App = window.App, e = App.estado;
    $("nu-importe").value = "";
    $("nu-nota").value = "";
    $("nu-foto").value = "";
    $("nu-foto-txt").textContent = "📷 Añadir ticket";
    $("nu-fecha").value = C.fechaISO(new Date());
    $("nu-error").hidden = true;
    $("nu-form").querySelector("[type=submit]").disabled = false;
    ponerSigno(false);
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
    var actual = App.cuentasDelGrupo(e.grupo === "comun" ? "comun" : "mia")[0];
    if (actual) sel.value = actual.id;
    App.chips($("nu-cats"), null, e.catsLista, function (id) { ponerSigno(!!ENTRADAS[id]); });
    $("nu-alquiler").hidden = !(e.cats["piso-alquiler"] && cuentaEfectivo());
    $("hoja-nuevo").showModal();
    $("nu-importe").focus();
  }

  function error(texto) {
    $("nu-error").textContent = texto;
    $("nu-error").hidden = false;
  }

  $("nu-alquiler").addEventListener("click", function () {
    $("nu-importe").value = C.formatoEuros(ALQUILER_CENT).replace(" €", "");
    $("nu-cuenta").value = cuentaEfectivo().id;
    $("nu-nota").value = "Alquiler";
    var chip = $("nu-cats").querySelector('[data-id="piso-alquiler"]');
    if (chip) chip.click();
  });
  $("nu-gasto").addEventListener("click", function () { ponerSigno(false); });
  $("nu-entrada").addEventListener("click", function () { ponerSigno(true); });
  $("nu-foto").addEventListener("change", function () {
    $("nu-foto-txt").textContent = $("nu-foto").files.length ? "📷 Ticket listo ✓" : "📷 Añadir ticket";
  });

  $("nu-form").addEventListener("submit", function (ev) {
    ev.preventDefault();
    var App = window.App, e = App.estado;
    var boton = $("nu-form").querySelector("[type=submit]");
    if (boton.disabled) return;
    var cent = C.parseImporte($("nu-importe").value);
    var elegida = $("nu-cats").querySelector(".elegida");
    if (!cent) return error("Escribe un importe válido (por ejemplo, 12,50).");
    if (!elegida) return error("Elige una categoría.");
    if (!$("nu-cuenta").value) return error("No tienes ninguna cuenta donde apuntarlo.");
    var cat = e.cats[elegida.dataset.id];
    var nota = $("nu-nota").value.trim();
    var fila = {
      cuenta_id: $("nu-cuenta").value, fecha: $("nu-fecha").value || C.fechaISO(new Date()),
      importe_cent: entrada ? cent : -cent, comercio: nota || cat.nombre,
      descripcion: "", nota: "", categoria_id: cat.id, origen: "manual", creado_por: e.usuario.id
    };
    var foto = $("nu-foto").files[0];
    boton.disabled = true;
    var subida = foto
      ? window.Tickets.reducir(foto).then(function (blob) { return App.D.subirTicket(fila.cuenta_id, blob); })
      : Promise.resolve(null);
    subida.then(function (ruta) {
      if (ruta) fila.ticket_path = ruta;
      return App.D.crearMovimiento(fila);
    }).then(function () {
      $("hoja-nuevo").close();
      boton.disabled = false;
      if (e.grupo !== "piso") {
        var cuenta = e.cuentas.find(function (c) { return c.id === fila.cuenta_id; });
        e.grupo = cuenta.owner === null ? "comun" : "mia";
        e.mes = C.mesDe(fila.fecha);
      }
      App.pintarPestanas();
      return App.recargar();
    }).catch(function (err) { boton.disabled = false; error("No se pudo guardar: " + err.message); });
  });

  $("fab").addEventListener("click", abrir);
  $("nu-cancelar").addEventListener("click", function () { $("hoja-nuevo").close(); });
})();
```

- [ ] **Step 3: Verificación offline:**
  - `node --check ui-nuevo.js`.
  - Los ids `nu-alquiler`, `nu-gasto`, `nu-entrada`, `nu-foto` y `nu-foto-txt` existen.
  - Los suites siguen verdes.

- [ ] **Step 4: Commit**

```bash
git add index.html ui-nuevo.js
git commit -m "Apuntar a mano: gasto o entrada, foto del ticket y atajo del alquiler

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Ver y añadir el ticket desde un movimiento

**Files:**
- Modify: `index.html` (hoja `hoja-mov`), `ui-movs.js`

- [ ] **Step 1: `index.html`**, en `<form id="ed-form">`, tras `<p id="ed-detalle" class="detalle"></p>`:
```html
      <img id="ed-ticket" class="ticket-img" alt="Foto del ticket" hidden>
      <label class="foto"><input id="ed-foto" type="file" accept="image/*" hidden><span id="ed-foto-txt">📷 Añadir ticket</span></label>
```

- [ ] **Step 2: `ui-movs.js`**
1. En `editar(m)`, antes de `$("hoja-mov").showModal();`:
```js
    $("ed-foto").value = "";
    $("ed-ticket").hidden = true;
    $("ed-ticket").removeAttribute("src");
    $("ed-foto-txt").textContent = m.ticket_path ? "📷 Cambiar ticket" : "📷 Añadir ticket";
    if (m.ticket_path) mostrarTicket(m);
```
2. Añadir estas funciones y listeners antes de `window.UiMovs = …`:
```js
  function mostrarTicket(m) {
    window.App.D.urlTicket(m.ticket_path).then(function (url) {
      if (enEdicion !== m || !url) return;
      $("ed-ticket").src = url;
      $("ed-ticket").hidden = false;
    }).catch(function (err) { errorHoja("No se pudo cargar el ticket: " + err.message); });
  }

  $("ed-ticket").addEventListener("click", function () { window.open($("ed-ticket").src, "_blank"); });

  $("ed-foto").addEventListener("change", function () {
    var App = window.App, m = enEdicion, foto = $("ed-foto").files[0];
    if (!foto) return;
    $("ed-foto-txt").textContent = "📷 Subiendo…";
    window.Tickets.reducir(foto)
      .then(function (blob) { return App.D.subirTicket(m.cuenta_id, blob); })
      .then(function (ruta) {
        return App.D.actualizarMovimiento(m.id, { ticket_path: ruta }).then(function () { return ruta; });
      })
      .then(function (ruta) {
        m.ticket_path = ruta;
        $("ed-foto-txt").textContent = "📷 Cambiar ticket";
        mostrarTicket(m);
      })
      .catch(function (err) {
        $("ed-foto-txt").textContent = "📷 Añadir ticket";
        errorHoja("No se pudo subir el ticket: " + err.message);
      });
  });
```
3. En `pintar()`, el texto `small` de cada fila añade `(m.ticket_path ? " · 📎" : "")` al final.

- [ ] **Step 3: Verificación offline:** `node --check ui-movs.js`, ids presentes, suites verdes.

- [ ] **Step 4: Commit**

```bash
git add index.html ui-movs.js
git commit -m "Ver y añadir la foto del ticket desde un movimiento

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Versión de los assets

**Files:**
- Modify: `index.html`, `sw.js`

- [ ] **Step 1:**
  - En `index.html`, todos los `?v=1` → `?v=2` y añadir `<script src="tickets.js?v=2"></script>` tras `datos-demo.js`.
  - En `sw.js`, `CACHE = "cuentas-v2"`; `ASSETS` con `?v=2` e incluyendo `./tickets.js?v=2` y `./ui-piso.js?v=2`.
  - Comprobar que la lista de `ASSETS` y los `<script>`/`<link>` de index.html coinciden uno a uno.
- [ ] **Step 2:** Suites verdes; `node --check sw.js`.
- [ ] **Step 3: Commit**

```bash
git add index.html sw.js
git commit -m "Assets v2: tickets.js y ui-piso.js en el esqueleto offline

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Verificación en navegador (controlador, modo demo, tras los Tasks 5–8)

1. Pestañas Común · Mía · Piso.
2. En "Mía" aparece "💶 En efectivo: …" y el gasto incluye la Ferretería en efectivo.
3. Piso:
   - neto = alquiler − (comunidad + IBI);
   - luz y gas con "en contra";
   - meses con ✅/⏳ (el mes actual con ⏳ en luz y gas);
   - la última factura de agua ⏳ y las anteriores ✅;
   - `‹` cambia de año.
4. "+":
   - el atajo del alquiler rellena 950,00, Efectivo, "Piso · Alquiler" y "+ Entrada";
   - al guardar, el alquiler del piso sube.
5. Adjuntar una imagen (generada en el navegador con un canvas → File) en un apunte y en un movimiento existente: aparece la miniatura y el 📎 en la lista.
6. Consola sin errores. Capturas a ancho de móvil.
