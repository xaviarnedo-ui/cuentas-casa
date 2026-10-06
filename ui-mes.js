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
    var se = $("saldo-efectivo");
    se.hidden = e.grupo !== "mia" || e.saldoEfectivo === null || e.saldoEfectivo === undefined;
    if (!se.hidden) se.textContent = "💶 En efectivo: " + C.formatoEuros(e.saldoEfectivo);
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
