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
      gastos.appendChild(fila(cat ? cat.icono : "📎", cat ? cat.nombre : g.categoria_id, "", C.formatoEuros(-g.total)));
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
