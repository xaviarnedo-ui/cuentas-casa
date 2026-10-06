# Cuentas de casa — Diseño (v1)

Fecha: 2026-10-04 · Estado: aprobado (fase 1 = cuenta común)

## 1. Objetivo

App móvil sencilla para que Xavi y su pareja vean **en qué se gasta el dinero, por categoría y mes**, tanto de la cuenta común como de sus cuentas personales, y para que Xavi vea la **evolución de su patrimonio** (ahorro + inversión).

Criterio de éxito: abrir la app y en menos de 10 segundos saber cuánto se ha gastado este mes, en qué, y si es más o menos de lo habitual.

## 2. Usuarios y cuentas

| Cuenta | Banco | Dueño | Tipo | Qué se guarda |
|---|---|---|---|---|
| Común | Revolut | compartida | corriente | movimientos + saldo |
| Xavi | CaixaBank | Xavi | corriente | movimientos + saldo |
| Pareja | Sabadell | Pareja | corriente | movimientos + saldo |
| MyInvestor | MyInvestor | Xavi | inversión | solo saldo |
| Trade Republic | Trade Republic | Xavi | inversión | solo saldo |
| MyAXA | AXA | Xavi | ahorro | solo saldo |

- Dos usuarios con login (email + contraseña). Registro desactivado tras crear ambos.
- **Privacidad:** cada usuario ve solo las cuentas compartidas y las suyas. Garantizado por RLS en la base de datos, no por la app.
- Se pueden añadir más cuentas de cualquier tipo sin cambiar el diseño.

**Fases:** 1) cuenta común (Revolut) de punta a punta: BD, importador, PWA. 2) CaixaBank y Sabadell (un lector nuevo cada uno). 3) Saldos de ahorro/inversión y pestaña Patrimonio.

**Histórico y cadencia:** datos desde el **1 sept 2026** (no hay carga de 12 meses). Extractos de cuentas corrientes **semanales**; saldos de ahorro/inversión **mensuales**.

## 3. Arquitectura

```
Extracto banco ──► Xavi ──► Claude ejecuta cuentas.py ──► Supabase (Postgres + Auth + RLS)
                                                               ▲
                              PWA (GitHub Pages) ◄─────────────┘  lectura + gastos manuales
```

- **Frontend:** PWA en HTML/CSS/JS vanilla (mismo patrón que carga-gps / nexo-ideas), alojada en GitHub Pages. Instalable en el móvil. Usa `supabase-js` con la clave anon.
- **Backend:** proyecto Supabase **nuevo y dedicado** (no se reutilizan los de hábitos/GPS). Si el plan gratuito ya tiene 2 proyectos activos, se decide al montar (pausar uno o esquema separado).
- **Importación:** script Python `cuentas.py` en el Mac de Xavi, con la clave `service_role` en `.env` (en `.gitignore`, nunca en el repo).
- **Repo:** `~/Desktop/cuentas/`, publicado en GitHub. Solo código; ningún dato bancario en el repo.

## 4. Modelo de datos

- **profiles** — `id` (= auth.uid), `nombre`.
- **cuentas** — `id`, `nombre`, `banco`, `tipo` (`corriente` | `ahorro` | `inversion` | `efectivo`), `owner` (uuid o `null` = compartida), `orden`.
- **categorias** — `id`, `nombre`, `icono`, `cuenta_como_gasto` (bool), `orden`.
  - Iniciales con gasto: Súper, Casa (alquiler + suministros), Restaurantes, Ocio, Transporte, Salud, Compras, Suscripciones, Viajes, Otros.
  - Sin gasto: Ingresos, Transferencias/Aportaciones.
  - Lista fija en v1; las añade Claude bajo petición.
- **movimientos** — `id`, `cuenta_id`, `fecha`, `importe_cent` (int; negativo = salida), `descripcion` (original del banco), `comercio` (normalizado), `categoria_id` (nullable), `nota`, `no_es_gasto` (bool), `origen` (`import` | `manual`), `creado_por`, `huella` (único).
- **reglas** — `id`, `patron` (texto contenido en `comercio`), `categoria_id`, `owner` (uuid o `null` = compartida).
- **saldos** — `id`, `cuenta_id`, `fecha`, `saldo_cent`. Único por (`cuenta_id`, `fecha`).

**Huella (deduplicación):** hash de `cuenta_id + fecha + importe_cent + descripcion + n` donde `n` es el índice de ocurrencia de esa combinación ese día. Reimportar extractos solapados no duplica.

**Qué es "gasto":** gasto de una categoría = −(suma de `importe_cent`) de sus movimientos con `no_es_gasto = false` y categoría con `cuenta_como_gasto = true` (o sin categoría, que se muestra como "Sin categoría"). Así las devoluciones restan.

### RLS

- `cuentas`: SELECT si `owner is null or owner = auth.uid()`.
- `movimientos`, `saldos`: SELECT / INSERT / UPDATE si la cuenta es visible según la regla anterior. DELETE solo de movimientos `origen = 'manual'` creados por uno mismo.
- `reglas`: SELECT / INSERT si `owner is null or owner = auth.uid()`. Una regla creada desde una cuenta personal lleva `owner = auth.uid()`; desde la común, `owner = null`.
- `categorias`: SELECT para cualquier usuario autenticado; sin escritura desde la app.
- `cuentas`, `categorias`: sin INSERT/UPDATE/DELETE desde la app (solo `service_role`).

## 5. Pantallas (PWA)

1. **Login** — email + contraseña; sesión persistente. (No magic link: en iOS abre Safari, no la PWA.)
2. **El mes** (pantalla principal)
   - Pestañas: **Común** · **Mía** · **Patrimonio**. "Mía" agrega las cuentas corrientes propias.
   - Selector de mes `‹ Octubre 2026 ›`.
   - Total gastado + comparación con la media de los meses anteriores disponibles (hasta 3; si no hay ninguno, no se muestra).
   - Mini gráfico de barras de los últimos 6 meses.
   - Lista de categorías ordenada por gasto: barra, importe y variación respecto al mes anterior. Tocar → movimientos filtrados.
3. **Movimientos** — lista por fecha con buscador. Al tocar uno: cambiar categoría (con la opción "¿aplicar a todos los de X?", que crea una regla), nota, marcar "no es gasto".
4. **Añadir (+)** — importe, categoría (botones grandes), cuenta (corrientes visibles), fecha (hoy por defecto), nota. `origen = manual`.
5. **Patrimonio** — total actual (último saldo de cada cuenta propia), línea de evolución mensual (último saldo de cada mes por cuenta) y desglose por cuenta. La común se muestra aparte, como línea informativa, sin sumarse al total personal.

Fuera de la v1: presupuestos, objetivos de ahorro, notificaciones, rentabilidad de la inversión y vista combinada personal + común.

## 6. Importación (`cuentas.py`)

Flujo cuando Xavi pasa un archivo:

1. **Detectar** banco y cuenta por formato o cabeceras (CaixaBank, Sabadell, Revolut). Un lector por banco, todos con la misma salida: `(fecha, importe_cent, descripcion, saldo_cent?)`.
2. **Normalizar** el comercio (quitar prefijos tipo `COMPRA TARJ.`, números de tarjeta, ciudad).
3. **Categorizar** con las reglas (primero las del dueño de la cuenta, luego las compartidas). Las transferencias entre cuentas propias o la común → Transferencias/Aportaciones.
4. **Preguntar** a Xavi solo por los comercios sin regla y crear las reglas con su respuesta.
5. **Subir** los movimientos nuevos (upsert por `huella`) y el último saldo de cada día a `saldos`.
6. **Resumir:** nuevos, duplicados ignorados y total del mes por cuenta.

**Saldos de ahorro e inversión:** a partir de un extracto, una captura o un valor dictado (`cuentas.py saldo myinvestor 12340`), con fecha de hoy salvo que se indique otra.

**Errores:** si un archivo no encaja con ningún lector, o le faltan columnas esperadas, el script aborta con un mensaje claro y no sube nada (todo o nada por archivo).

**Carga inicial:** desde el 1 sept 2026.

### Formato Revolut (cuenta común) — visto en el extracto real del 4 oct 2026

- **PDF** ("Extracto de cuenta conjunta en EUR"), texto extraíble con PyMuPDF (`fitz`, ya instalado). El extracto PDF no se commitea nunca.
- Secciones: *Resumen del saldo* (saldo inicial / saliente / entrante / final), *Pendientes* y *Transacciones de la cuenta*.
- **Pendientes se ignoran**: aún no están consolidadas; entrarán con el extracto de la semana siguiente.
- Cada transacción: fecha transacción, fecha valor, título (= comercio, p. ej. "Mercadona"), importe, saldo, y líneas de detalle ("A Mercadona Estadi Balea, Palma…", "Tarjeta: XXXXXX******XXXX", "Referencia: …", "De …, IBAN").
- El texto no distingue la columna saliente/entrante → **el signo se deduce del cambio de saldo** respecto a la fila anterior (la primera, respecto al saldo inicial del resumen). Ej.: la devolución de H&M sube el saldo → entrada.
- **Validación:** el saldo de la última fila debe coincidir con el saldo final del resumen, y cada fila debe cumplir `saldo_anterior ± importe = saldo`. Si no cuadra, aborta.
- Mes del movimiento = **fecha de transacción** (no la fecha valor). El orden del PDF es por fecha valor.
- `comercio` = título de la transacción; `descripcion` = título + líneas de detalle.
- Clasificación automática de entradas/salidas no comerciales:
  - "Una recarga de Apple Pay…" (entradas) → Transferencias/Aportaciones automáticamente.
  - "Pago de <nombre>" / "To <nombre>": SOLO son transferencias propias si el nombre es de Xavi o Andrea, y eso lo deciden **reglas guardadas en la BD** (no en el repo). Una transferencia a terceros (p. ej. profesores de inglés) se categoriza como cualquier gasto (ver §9).
  - Devoluciones de un comercio (entrada con "De <comercio>") → misma categoría del comercio, en positivo, restando del gasto de esa categoría.
- **Huella** para Revolut: `cuenta + fecha + importe + comercio + saldo` (el saldo hace única cada fila y es estable entre extractos semanales solapados).

**Documentación operativa:** `CLAUDE.md` en el repo con el procedimiento, para que cualquier sesión de Claude pueda importar solo con recibir el archivo.

## 7. Pruebas

- **Lectores:** tests con extractos reales anonimizados de cada banco (fixtures en `tests/fixtures/`, sin datos reales).
- **Normalización, categorización y huella:** tests unitarios (incluye dos movimientos idénticos el mismo día y la reimportación de un periodo solapado).
- **RLS:** test que inicia sesión como un usuario e intenta leer o escribir movimientos, saldos y reglas privadas del otro; debe fallar.
- **PWA:** verificación manual en el navegador (escritorio y ancho móvil) de las tres pestañas, el cambio de categoría y el alta manual.

## 8. Pendientes para la implementación

- Extracto de ejemplo de CaixaBank y Sabadell (fase 2). Revolut ya recibido.
- Crear el proyecto Supabase y los dos usuarios (Xavi lo hace desde el panel; Claude le guía).
- Crear el repo de GitHub (lo crea Xavi; `gh repo create` lo bloquea el clasificador).

## 9. Ampliación (2026-10-04): Efectivo, tickets, Piso alquilado y Formación

Decisión: opción A — categorías del grupo "Piso" que no cuentan en el gasto personal; los movimientos siguen en su cuenta real.

**Cuentas:** nueva cuenta `efectivo` (tipo `efectivo`, dueño Xavi, privada). Todo a mano. Primera entrada "Saldo inicial" (categoría transferencias). Saldo = suma de sus movimientos. Retirada de cajero = transferencia (no gasto); en fase 2 el importador de CaixaBank creará automáticamente la entrada espejo en Efectivo.

**Categorías nuevas** (columna nueva `categorias.grupo`: `null` | `'piso'`):
- Grupo piso, todas `cuenta_como_gasto = false`: `piso-alquiler` (ingreso), `piso-luz-gas`, `piso-agua`, `piso-comunidad`, `piso-ibi`, `piso-seguro`, `piso-reparaciones`, `piso-otros`.
- `formacion` (Formación, cuenta como gasto): clases de inglés; reglas por nombre de los profesores, guardadas en la BD.

**Tickets:** columna `movimientos.ticket_path` (nullable; añadida a los grants de INSERT/UPDATE de la app). Bucket privado de Supabase Storage `tickets`, ruta `<cuenta_id>/<uuid>.jpg`; políticas de storage con `puede_ver_cuenta(split_part(name,'/',1))` (mismas reglas de privacidad). La app reduce la foto (máx. 1600 px, JPEG ~0,7) antes de subirla. Botón "📷 Ticket" al apuntar a mano y "Añadir ticket" al editar; miniatura ampliable.

**Pestaña Piso** (solo el dueño de las categorías piso las ve; v1: Xavi), selector de año:
1. Rendimiento neto = `piso-alquiler` − (comunidad + IBI + seguro + reparaciones + otros), con desglose.
2. Suministros: pagado vs devuelto por la inquilina y **diferencia acumulada** (Iberdrola cobra cuota fija; la inquilina devuelve la factura real; se compensa con la regularización anual). No entra en el rendimiento.
3. Control: por mes ✅/⏳ alquiler cobrado (950 €) y Bizum de luz y gas; por **cada factura de agua** ✅/⏳ su Bizum.

**Bizum de la inquilina (fase 2, importador CaixaBank):** si coincide al céntimo con un cargo de `piso-agua` de los 45 días anteriores aún sin Bizum → `piso-agua`; si no → `piso-luz-gas`. Corregible a mano.

**App:** "Mía" incluye Efectivo y muestra "💶 En efectivo: X €"; atajo "Alquiler cobrado" (+950 € en Efectivo, `piso-alquiler`, hoy).

**Fases revisadas:** los cambios de esquema (tipo efectivo, `grupo`, `ticket_path`, bucket y políticas, categorías nuevas) entran YA, antes de ejecutar el SQL. **Fase 1b** (solo app, sin banco): Efectivo, tickets, pestaña Piso, atajo alquiler. **Fase 2**: CaixaBank (Bizum inquilina, Iberdrola, agua, clases, cajero→Efectivo) y Sabadell. **Fase 3**: patrimonio.
