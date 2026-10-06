/* Cuentas de casa — lista de movimientos del mes y hoja de edición. */
(function () {
  "use strict";
  var C = window.Calculos;
  var filtro = { categoria: null, titulo: "" };
  var enEdicion = null;
  function $(id) { return document.getElementById(id); }
  function errorHoja(texto) { $("ed-error").textContent = texto; $("ed-error").hidden = false; }

  function abrir(f) {
    filtro = f;
    $("buscar").value = "";
    $("vista-mes").hidden = true;
    $("vista-movs").hidden = false;
    pintar();
    window.scrollTo(0, 0);
  }
  function cerrar() {
    $("vista-movs").hidden = true;
    $("vista-mes").hidden = false;
  }
  function pintarSiVisible() { if (!$("vista-movs").hidden) pintar(); }

  function visibles() {
    var e = window.App.estado, texto = $("buscar").value.trim().toLowerCase();
    return e.movs.filter(function (m) {
      if (C.mesDe(m.fecha) !== e.mes) return false;
      if (filtro.categoria !== null &&
          ((m.categoria_id || "") !== filtro.categoria || !C.esGasto(m, e.cats))) return false;
      return !texto || (m.comercio + " " + m.nota + " " + m.descripcion).toLowerCase().indexOf(texto) >= 0;
    });
  }

  function pintar() {
    var e = window.App.estado;
    $("titulo-movs").textContent = filtro.titulo;
    var ul = $("lista-movs");
    ul.innerHTML = "";
    var lista = visibles();
    if (!lista.length) {
      ul.innerHTML = '<li class="vacio">Nada por aquí</li>';
      return;
    }
    lista.forEach(function (m) {
      var cat = m.categoria_id && e.cats[m.categoria_id];
      var li = document.createElement("li");
      if (m.no_es_gasto) li.className = "apagado";
      li.innerHTML = '<span class="icono"></span><div class="cuerpo"><span class="nombre"></span><small></small></div>' +
        '<span class="importe"></span>';
      li.querySelector(".icono").textContent = cat ? cat.icono : "❓";
      li.querySelector(".nombre").textContent = m.comercio;
      li.querySelector("small").textContent = C.fechaCorta(m.fecha) + (m.nota ? " · " + m.nota : "") +
        (m.origen === "manual" ? " · a mano" : "") + (m.ticket_path ? " · 📎" : "");
      var imp = li.querySelector(".importe");
      imp.textContent = C.formatoEuros(m.importe_cent);
      if (m.importe_cent > 0) imp.classList.add("positivo");
      li.addEventListener("click", function () { editar(m); });
      ul.appendChild(li);
    });
  }

  function editar(m) {
    var e = window.App.estado;
    enEdicion = m;
    $("ed-error").hidden = true;
    $("ed-comercio").textContent = m.comercio;
    $("ed-detalle").textContent = C.fechaCorta(m.fecha) + " · " + C.formatoEuros(m.importe_cent) +
      (m.descripcion && m.descripcion !== m.comercio ? " · " + m.descripcion : "");
    var cuenta = e.cuentas.find(function (c) { return c.id === m.cuenta_id; });
    var lista = e.catsLista.filter(function (c) { return !(c.grupo === "piso" && cuenta && cuenta.owner === null); });
    window.App.chips($("ed-cats"), m.categoria_id, lista);
    $("ed-todos-fila").hidden = m.origen !== "import";
    $("ed-todos").checked = m.origen === "import";
    $("ed-todos-txt").textContent = "Aplicar a todos los de " + m.comercio;
    $("ed-nota").value = m.nota || "";
    $("ed-no-gasto").checked = !!m.no_es_gasto;
    $("ed-borrar").hidden = !(m.origen === "manual" && m.creado_por === e.usuario.id);
    $("ed-foto").value = "";
    $("ed-ticket").hidden = true;
    $("ed-ticket").removeAttribute("src");
    $("ed-foto-txt").textContent = m.ticket_path ? "📷 Cambiar ticket" : "📷 Añadir ticket";
    if (m.ticket_path) mostrarTicket(m);
    $("hoja-mov").showModal();
  }

  $("ed-form").addEventListener("submit", function (ev) {
    ev.preventDefault();
    var App = window.App, m = enEdicion;
    var elegida = $("ed-cats").querySelector(".elegida");
    var categoria = elegida ? elegida.dataset.id : null;
    var p = App.D.actualizarMovimiento(m.id, {
      categoria_id: categoria, nota: $("ed-nota").value.trim(), no_es_gasto: $("ed-no-gasto").checked
    });
    if (categoria && categoria !== m.categoria_id && m.origen === "import" && $("ed-todos").checked) {
      var cuenta = App.estado.cuentas.find(function (c) { return c.id === m.cuenta_id; });
      p = p.then(function () { return App.D.guardarRegla(m.comercio.toLowerCase(), categoria, cuenta.owner); })
           .then(function () { return App.D.recategorizarComercio(m.cuenta_id, m.comercio, categoria); });
    }
    p.then(function () { $("hoja-mov").close(); return App.recargar(); })
     .catch(function (err) { errorHoja("No se pudo guardar: " + err.message); });
  });

  $("ed-borrar").addEventListener("click", function () {
    if (!confirm("¿Borrar este movimiento?")) return;
    window.App.D.borrarMovimiento(enEdicion.id)
      .then(function () { $("hoja-mov").close(); return window.App.recargar(); })
      .catch(function (err) { errorHoja("No se pudo borrar: " + err.message); });
  });
  $("ed-cancelar").addEventListener("click", function () { $("hoja-mov").close(); });
  $("volver").addEventListener("click", cerrar);
  $("buscar").addEventListener("input", pintar);

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

  window.UiMovs = { abrir: abrir, pintarSiVisible: pintarSiVisible };
})();
