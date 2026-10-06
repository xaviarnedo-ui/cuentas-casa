# Cuentas de casa

PWA (GitHub Pages) + Supabase para el gasto por categoría/mes de Xavi y Andrea.
Spec: `docs/superpowers/specs/2026-10-04-cuentas-casa-design.md`.

## Cuando Xavi pasa un extracto

1. `python3 cuentas.py importar "<ruta del archivo>"`
2. Si sale "Comercios sin regla": pregunta a Xavi la categoría de cada uno (propón tú una
   para que solo tenga que confirmar) y crea las reglas:
   `python3 cuentas.py regla "<trozo del comercio>" <categoria_id>`
   (`--cuenta <id>` si el extracto es de una cuenta personal). Después repite el paso 1.

   - Transferencias entre vuestras cuentas ("Pago de <Xavi/Andrea>", "To <Xavi/Andrea>", Bizum
     entre vosotros): regla con el trozo del nombre → `transferencias`. Una transferencia o Bizum a
     cualquier otra persona es un gasto/ingreso normal (p. ej. clases de inglés → `formacion`,
     Bizum de la inquilina → `piso-luz-gas` o `piso-agua`). Los nombres viven solo en las reglas
     de la BD, nunca en el repo.

3. Resume a Xavi: nuevos, ya estaban, saldo y gasto nuevo por mes.

- Ids de categoría: `python3 cuentas.py categorias`.
- Cadencia: cuentas corrientes cada semana; ahorro/inversión cada mes (fase 3).
- Si el script dice `ERROR: ...` de formato, no fuerces nada: el banco ha cambiado el
  extracto. Adapta el lector en `importador/` con un test nuevo.
- Nunca commitear extractos (`.pdf/.xlsx/.csv`) ni `.env`. La clave de servicio solo vive en `.env`.

### CaixaBank (CSV de CaixaBankNow)

- Xavi descarga el **CSV** (Cuentas → Movimientos → exportar). No trae IBAN: va a la cuenta `caixabank`.
- Las reglas de CaixaBank son de Xavi: `python3 cuentas.py regla "<patrón>" <categoria> --cuenta caixabank`.
  Cuidado con patrones cortos que puedan estar dentro de otros conceptos (las reglas buscan "contiene").
- "BIZUM RECIBIDO/ENVIADO", "TRANSFER INMEDIATA" y "PAGO TRANSFERENCIAS" no dicen quién es: el script
  los lista numerados y hay que preguntar a Xavi cada uno, después repetir con `--asignar N=categoria`.
  Los Bizum que coinciden con una factura de agua (≤45 días) se asignan solos a `piso-agua`.

### Saldos de ahorro e inversión (fin de mes)

Xavi pasa el saldo de MyInvestor, Trade Republic y MyAXA el último día de cada mes (texto o captura):
`python3 cuentas.py saldo <myinvestor|traderepublic|myaxa> <importe> --fecha AAAA-MM-DD`
(fecha = último día del mes al que corresponde; repetir la orden corrige el valor de ese día).

### Deuda con los padres (cuenta `deuda-padres`, tipo deuda)

Empieza en −5.000 € (2026-10-06). Su saldo sale de sus movimientos y resta en Patrimonio.
Cuando Xavi devuelva dinero: el pago (CaixaBank o efectivo) va a `transferencias` y además se añade
en `deuda-padres` un movimiento manual de +importe (comercio "Devolución a mis padres", categoría
`transferencias`). No usar `cuentas.py saldo` para esta cuenta.

## Tests

    python3 -m unittest discover -s tests -t .
    node --test tests/calculos.test.js

## Publicar cambios de la app

Subir `?v=N` en `index.html` y en `sw.js` (`CACHE` y `ASSETS`), commit y `git push`.
GitHub Pages redespliega en ~1 minuto.
