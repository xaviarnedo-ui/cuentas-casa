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

test("resumenPiso: la hipoteca cuenta como gasto del piso", () => {
  const r = C.resumenPiso([
    p("1", "2026-09-02", 95000, "piso-alquiler"),
    p("2", "2026-09-01", -49433, "piso-hipoteca")
  ], 2026);
  assert.deepStrictEqual(r.gastos, [{ categoria_id: "piso-hipoteca", total: 49433 }]);
  assert.strictEqual(r.neto, 95000 - 49433);
});

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
