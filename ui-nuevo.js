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
    App.chips($("nu-cats"), null, e.catsLista, function (id) { if (ENTRADAS[id]) ponerSigno(true); });
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
    var cuentaElegida = e.cuentas.find(function (c) { return c.id === $("nu-cuenta").value; });
    if (cat.grupo === "piso" && cuentaElegida && cuentaElegida.owner === null)
      return error("Las categorías del piso son privadas: elige una cuenta tuya (Efectivo o CaixaBank).");
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
      if (e.grupo !== "piso" && e.grupo !== "patrimonio") {
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
