/* Cuentas de casa — arranque, estado, login, pestañas y navegación de meses. */
(function () {
  "use strict";
  var C = window.Calculos;
  var demo = /[?&]demo=1/.test(location.search);
  var D = demo ? window.DatosDemo : window.Datos;
  var peticion = 0;  // la última recarga gana: una respuesta lenta no pisa a otra más reciente
  function $(id) { return document.getElementById(id); }

  var App = window.App = {
    D: D,
    estado: { usuario: null, cuentas: [], cats: {}, catsLista: [], grupo: null,
              mes: C.mesDe(C.fechaISO(new Date())), movs: [], saldoEfectivo: null },
    gruposVisibles: gruposVisibles, cuentasDelGrupo: cuentasDelGrupo, pintarPestanas: pintarPestanas,
    recargar: recargar, pintar: pintar, aviso: aviso, chips: chips
  };

  function cuentasDelGrupo(grupo) {
    var e = App.estado;
    return e.cuentas.filter(function (c) {
      if (c.tipo !== "corriente" && c.tipo !== "efectivo") return false;
      return grupo === "comun" ? c.owner === null : c.owner === e.usuario.id;
    });
  }
  function gruposVisibles() {
    var tienePiso = App.estado.catsLista.some(function (c) { return c.grupo === "piso"; });
    var tienePatrimonio = App.estado.cuentas.some(function (c) {
      return c.owner === App.estado.usuario.id && (c.tipo === "ahorro" || c.tipo === "inversion");
    });
    return [{ id: "comun", nombre: "Común" }, { id: "mia", nombre: "Mía" }]
      .filter(function (g) { return cuentasDelGrupo(g.id).length > 0; })
      .concat(tienePiso ? [{ id: "piso", nombre: "Piso" }] : [])
      .concat(tienePatrimonio ? [{ id: "patrimonio", nombre: "Patrimonio" }] : []);
  }

  function arrancar() {
    $("demo").hidden = !demo;
    D.usuario().then(function (u) {
      if (u) return entrarEnApp(u);
      $("login").hidden = false;
    }).catch(errorFatal);
  }

  $("login-form").addEventListener("submit", function (ev) {
    ev.preventDefault();
    $("login-error").hidden = true;
    D.entrar($("login-email").value.trim(), $("login-pass").value)
      .then(function () { return D.usuario(); })
      .then(entrarEnApp)
      .catch(function () { $("login-error").hidden = false; });
  });

  function entrarEnApp(u) {
    var e = App.estado;
    e.usuario = u;
    return Promise.all([D.cuentas(), D.categorias()]).then(function (r) {
      e.cuentas = r[0];
      e.catsLista = r[1];
      e.cats = {};
      r[1].forEach(function (c) { e.cats[c.id] = c; });
      var grupos = gruposVisibles();
      e.grupo = grupos.length ? grupos[0].id : null;
      $("login").hidden = true;
      $("app").hidden = false;
      pintarPestanas();
      return recargar();
    }).catch(errorFatal);
  }

  function pintarPestanas() {
    var nav = $("pestanas");
    nav.innerHTML = "";
    gruposVisibles().forEach(function (g) {
      var b = document.createElement("button");
      b.type = "button";
      b.className = "pestana" + (g.id === App.estado.grupo ? " activa" : "");
      b.textContent = g.nombre;
      b.addEventListener("click", function () { App.estado.grupo = g.id; pintarPestanas(); recargar(); });
      nav.appendChild(b);
    });
  }

  // Carga el mes elegido y los 6 anteriores (gráfico, comparación y variación por categoría).
  // En "Mía" también el saldo de efectivo (todos sus movimientos). Piso y Patrimonio tienen su propia carga.
  function recargar() {
    var e = App.estado;
    var esta = ++peticion;
    var propia = e.grupo === "piso" || e.grupo === "patrimonio";   // pestañas con carga y selector propios
    $("selector-mes").hidden = propia;
    $("vista-piso").hidden = e.grupo !== "piso";
    $("vista-patrimonio").hidden = e.grupo !== "patrimonio";
    if (propia) {
      $("vista-mes").hidden = true;
      $("vista-movs").hidden = true;
      return e.grupo === "piso" ? window.UiPiso.cargar() : window.UiPatrimonio.cargar();
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

  function pintar() {
    $("mes-nombre").textContent = C.nombreMes(App.estado.mes);
    window.UiMes.pintar();
    window.UiMovs.pintarSiVisible();
  }

  // Botones de categoría: se marca uno; el elegido se lee con contenedor.querySelector(".elegida").dataset.id
  function chips(cont, seleccionada, lista, alElegir) {
    cont.innerHTML = "";
    (lista || App.estado.catsLista).forEach(function (c) {
      var b = document.createElement("button");
      b.type = "button";
      b.className = "chip" + (c.id === seleccionada ? " elegida" : "");
      b.dataset.id = c.id;
      b.textContent = c.icono + " " + c.nombre;
      b.addEventListener("click", function () {
        var antes = cont.querySelector(".elegida");
        if (antes) antes.classList.remove("elegida");
        b.classList.add("elegida");
        if (alElegir) alElegir(c.id);
      });
      cont.appendChild(b);
    });
  }

  function aviso(texto) {
    var a = $("aviso");
    a.textContent = texto;
    a.hidden = false;
    clearTimeout(aviso.t);
    aviso.t = setTimeout(function () { a.hidden = true; }, 4000);
  }
  function errorFatal(err) { aviso("Error: " + err.message); }

  $("mes-ant").addEventListener("click", function () { App.estado.mes = C.moverMes(App.estado.mes, -1); recargar(); });
  $("mes-sig").addEventListener("click", function () { App.estado.mes = C.moverMes(App.estado.mes, 1); recargar(); });
  $("salir").addEventListener("click", function () { D.salir().then(function () { location.reload(); }); });

  if ("serviceWorker" in navigator && !demo) navigator.serviceWorker.register("sw.js");
  arrancar();
})();
