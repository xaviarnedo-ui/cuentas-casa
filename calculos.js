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

  function sumarDias(fecha, n) {
    var d = new Date(fecha + "T00:00:00Z");
    d.setUTCDate(d.getUTCDate() + n);
    return d.toISOString().slice(0, 10);
  }

  var PISO_GASTOS = ["piso-hipoteca", "piso-comunidad", "piso-ibi", "piso-seguro", "piso-reparaciones", "piso-otros"];
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

  var api = {
    mesDe: mesDe, moverMes: moverMes, nombreMes: nombreMes, fechaCorta: fechaCorta, fechaISO: fechaISO,
    ultimosMeses: ultimosMeses, esGasto: esGasto, resumenMes: resumenMes, comparacion: comparacion,
    variacion: variacion, formatoEuros: formatoEuros, parseImporte: parseImporte,
    sumarDias: sumarDias, resumenPiso: resumenPiso, saldosDesdeMovimientos: saldosDesdeMovimientos,
    patrimonioPorMes: patrimonioPorMes
  };
  if (typeof module === "object" && module.exports) module.exports = api;
  else raiz.Calculos = api;
})(this);
