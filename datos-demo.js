/* Cuentas de casa — datos de ejemplo en memoria para ver la app sin Supabase: index.html?demo=1 */
(function () {
  "use strict";
  var C = window.Calculos;
  var YO = { id: "demo-xavi", email: "demo@ejemplo.com" };
  var cuentas = [
    { id: "comun", nombre: "Común", banco: "Revolut", tipo: "corriente", owner: null, orden: 1 },
    { id: "xavi", nombre: "Xavi", banco: "CaixaBank", tipo: "corriente", owner: "demo-xavi", orden: 2 },
    { id: "efectivo", nombre: "Efectivo", banco: "Efectivo", tipo: "efectivo", owner: "demo-xavi", orden: 3 },
    { id: "myinvestor", nombre: "MyInvestor", banco: "MyInvestor", tipo: "inversion", owner: "demo-xavi", orden: 4 },
    { id: "traderepublic", nombre: "Trade Republic", banco: "Trade Republic", tipo: "inversion", owner: "demo-xavi", orden: 5 },
    { id: "myaxa", nombre: "MyAXA", banco: "AXA", tipo: "ahorro", owner: "demo-xavi", orden: 6 },
    { id: "deuda-padres", nombre: "Deuda con mis padres", banco: "Familia", tipo: "deuda", owner: "demo-xavi", orden: 7 },
    { id: "piso", nombre: "Piso", banco: "Inmueble", tipo: "inmueble", owner: "demo-xavi", orden: 8 },
    { id: "hipoteca", nombre: "Hipoteca del piso", banco: "Banco", tipo: "deuda", owner: "demo-xavi", orden: 9 },
    { id: "coche", nombre: "Coche", banco: "Vehículo", tipo: "vehiculo", owner: "demo-xavi", orden: 10 }
  ];
  var categorias = [
    ["super", "Súper", "🛒", true], ["casa", "Casa", "🏠", true], ["restaurantes", "Restaurantes", "🍽️", true],
    ["ocio", "Ocio", "🎉", true], ["transporte", "Transporte", "🚗", true], ["salud", "Salud", "💊", true],
    ["compras", "Compras", "🛍️", true], ["suscripciones", "Suscripciones", "📺", true],
    ["viajes", "Viajes", "✈️", true], ["formacion", "Formación", "📚", true], ["entrenamiento", "Entrenamiento", "🏃", true], ["otros", "Otros", "📦", true],
    ["ingresos", "Ingresos", "💶", false], ["ahorro-inversion", "Ahorro e inversión", "📈", false], ["transferencias", "Transferencias / Aportaciones", "🔁", false]
  ].map(function (c, i) {
    return { id: c[0], nombre: c[1], icono: c[2], cuenta_como_gasto: c[3], orden: i + 1, grupo: null, owner: null };
  }).concat([
    ["piso-alquiler", "Piso · Alquiler", "🔑"], ["piso-luz-gas", "Piso · Luz y gas", "💡"],
    ["piso-agua", "Piso · Agua", "🚰"], ["piso-comunidad", "Piso · Comunidad", "🏢"], ["piso-ibi", "Piso · IBI", "🧾"],
    ["piso-seguro", "Piso · Seguro", "🛡️"], ["piso-reparaciones", "Piso · Reparaciones", "🔧"],
    ["piso-otros", "Piso · Otros", "📎"], ["piso-hipoteca", "Piso · Hipoteca", "🏦"]
  ].map(function (c, i) {
    return { id: c[0], nombre: c[1], icono: c[2], cuenta_como_gasto: false, orden: 20 + i, grupo: "piso", owner: YO.id };
  }));
  var plantilla = [
    ["Mercadona", "super", -6237], ["Mercadona", "super", -4706], ["Netflix", "suscripciones", -1499],
    ["Galp", "transporte", -2000], ["Don Pedro Cafe Bistro", "restaurantes", -4730], ["H&M", "compras", -2297],
    ["Farmacia Magdalena", "salud", -320], ["Bar nuevo", null, -850], ["Pago de Xavi", "transferencias", 50000]
  ];
  var movs = [], n = 0, fotos = {};
  var mesActual = C.mesDe(C.fechaISO(new Date()));
  var anio = mesActual.slice(0, 4), mesNum = Number(mesActual.slice(5, 7));

  function apunte(cuenta, fecha, importe, comercio, cat) {
    n++;
    var manual = cuenta === "efectivo";
    movs.push({ id: "m" + n, cuenta_id: cuenta, fecha: fecha, importe_cent: importe, comercio: comercio,
      descripcion: comercio, categoria_id: cat, nota: "", no_es_gasto: false, origen: manual ? "manual" : "import",
      creado_por: manual ? YO.id : null, ticket_path: null });
  }

  [3, 2, 1, 0].forEach(function (atras, i) {
    var mes = C.moverMes(mesActual, -atras);
    plantilla.forEach(function (p, j) {
      ["comun", "xavi"].forEach(function (cuenta, k) {
        apunte(cuenta, mes + "-" + String(1 + (j * 3) % 27).padStart(2, "0"),
          Math.round(p[2] * (1 + 0.1 * i) * (k ? 0.5 : 1)), p[0], p[1]);
        movs[movs.length - 1].descripcion = p[0] + " · Palma";
      });
    });
  });

  // Un año de piso: alquiler en efectivo, cuota de Iberdrola + Bizum de la factura real,
  // agua cada dos meses con su Bizum (el último aún pendiente), comunidad e IBI.
  apunte("efectivo", anio + "-01-01", 120000, "Saldo inicial", "transferencias");
  for (var mes = 1; mes <= mesNum; mes++) {
    var m = anio + "-" + String(mes).padStart(2, "0");
    apunte("efectivo", m + "-02", 95000, "Alquiler", "piso-alquiler");
    apunte("xavi", m + "-05", -6000, "Iberdrola", "piso-luz-gas");
    if (mes < mesNum) apunte("xavi", m + "-12", 5000 + mes * 150, "Bizum inquilina", "piso-luz-gas");
    apunte("xavi", m + "-10", -4500, "Comunidad", "piso-comunidad");
    if (mes % 2 === 0) {
      apunte("xavi", m + "-20", -3540, "Agua", "piso-agua");
      if (mes < mesNum) apunte("xavi", m + "-25", 3540, "Bizum inquilina", "piso-agua");
    }
  }
  apunte("xavi", anio + "-06-15", -32000, "IBI", "piso-ibi");
  apunte("efectivo", mesActual + "-03", -1250, "Ferretería", "casa");
  apunte("deuda-padres", mesActual + "-01", -500000, "Préstamo de mis padres", "transferencias");
  apunte("hipoteca", anio + "-01-01", -12000000, "Capital pendiente", "transferencias");
  for (var mh = 2; mh <= mesNum; mh++) apunte("hipoteca", anio + "-" + String(mh).padStart(2, "0") + "-01", 32000, "Amortización", "transferencias");

  // Saldos de fin de mes de los últimos 6 meses (el más antiguo primero) para la pestaña Patrimonio.
  var saldos = [];
  for (var i = 0; i < 6; i++) {
    var mesSaldo = C.moverMes(mesActual, i - 6);
    var finDeMes = C.sumarDias(C.moverMes(mesSaldo, 1) + "-01", -1);
    [["myinvestor", 1200000 + 35000 * i], ["traderepublic", 500000 + 8000 * i], ["myaxa", 300000 + 5000 * i],
      ["xavi", 250000 - 3000 * i], ["comun", 70000 + 1000 * i], ["piso", 18000000], ["coche", 1500000]].forEach(function (s) {
      saldos.push({ cuenta_id: s[0], fecha: finDeMes, saldo_cent: s[1] });
    });
  }

  function ok(v) { return Promise.resolve(v === undefined ? null : JSON.parse(JSON.stringify(v))); }
  function porFechaDesc(lista) {
    return lista.sort(function (a, b) { return a.fecha < b.fecha ? 1 : a.fecha > b.fecha ? -1 : 0; });
  }

  window.DatosDemo = {
    usuario: function () { return ok(YO); },
    entrar: function () { return ok(YO); },
    salir: function () { return ok(); },
    cuentas: function () { return ok(cuentas); },
    categorias: function () { return ok(categorias); },
    saldos: function (ids) {
      return ok(saldos.filter(function (s) { return ids.indexOf(s.cuenta_id) >= 0; }));
    },
    movimientos: function (ids, desde, hasta) {
      return ok(porFechaDesc(movs.filter(function (m) {
        return ids.indexOf(m.cuenta_id) >= 0 && m.fecha >= desde && m.fecha < hasta;
      })));
    },
    movimientosDeCategorias: function (catIds, desde, hasta) {
      return ok(porFechaDesc(movs.filter(function (m) {
        return catIds.indexOf(m.categoria_id) >= 0 && m.fecha >= desde && m.fecha < hasta;
      })));
    },
    actualizarMovimiento: function (id, cambios) {
      Object.assign(movs.find(function (m) { return m.id === id; }), cambios);
      return ok();
    },
    recategorizarComercio: function (cuentaId, comercio, categoriaId) {
      movs.forEach(function (m) { if (m.cuenta_id === cuentaId && m.comercio === comercio) m.categoria_id = categoriaId; });
      return ok();
    },
    guardarRegla: function () { return ok(); },
    crearMovimiento: function (fila) {
      n++;
      movs.push(Object.assign({ id: "m" + n, descripcion: "", nota: "", no_es_gasto: false, ticket_path: null }, fila));
      return ok();
    },
    borrarMovimiento: function (id) {
      movs = movs.filter(function (m) { return m.id !== id; });
      return ok();
    },
    subirTicket: function (cuentaId, blob) {
      var ruta = cuentaId + "/demo-" + (++n) + ".jpg";
      fotos[ruta] = URL.createObjectURL(blob);
      return ok(ruta);
    },
    urlTicket: function (ruta) { return Promise.resolve(fotos[ruta] || null); }
  };
})();
