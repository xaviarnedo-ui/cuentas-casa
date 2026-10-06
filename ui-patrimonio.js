/* Cuentas de casa — pestaña Patrimonio: total, últimos 12 meses y desglose por cuenta. */
(function () {
  "use strict";
  var C = window.Calculos;
  var ICONOS = { inversion: "📈", ahorro: "🏦", corriente: "💳", efectivo: "💶", deuda: "💸" };
  // Efectivo y deudas no tienen extracto: su saldo sale de acumular sus movimientos.
  var DESDE_MOVIMIENTOS = { efectivo: true, deuda: true };
  var peticion = 0;
  function $(id) { return document.getElementById(id); }

  function cargar() {
    var App = window.App, e = App.estado, esta = ++peticion;
    var mias = e.cuentas.filter(function (c) { return c.owner === e.usuario.id; });
    var comun = e.cuentas.filter(function (c) { return c.owner === null && c.tipo === "corriente"; });
    var efectivo = mias.filter(function (c) { return DESDE_MOVIMIENTOS[c.tipo]; });
    var conSaldo = mias.filter(function (c) { return !DESDE_MOVIMIENTOS[c.tipo]; }).concat(comun);
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
    $("pat-variacion").textContent = anterior.total && dif !== 0 ? (dif >= 0 ? "+" : "") + C.formatoEuros(dif) + " frente al mes anterior" : "";

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
