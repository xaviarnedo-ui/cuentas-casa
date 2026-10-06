/* Cuentas de casa — acceso a Supabase. Todo devuelve promesas; los errores se lanzan como Error. */
(function () {
  "use strict";
  var db = window.CUENTAS_DB;
  function ok(r) { if (r.error) throw new Error(r.error.message); return r.data; }

  // Pide de 1000 en 1000 con un orden total (fecha, created_at, id) para no saltar ni repetir filas.
  function paginado(consulta) {
    var filas = [];
    function pagina(inicio) {
      return consulta()
        .order("fecha", { ascending: false }).order("created_at", { ascending: false }).order("id", { ascending: false })
        .range(inicio, inicio + 999).then(ok).then(function (d) {
          filas = filas.concat(d);
          return d.length === 1000 ? pagina(inicio + 1000) : filas;
        });
    }
    return pagina(0);
  }

  window.Datos = {
    usuario: function () {
      return db.auth.getSession().then(function (r) { return r.data.session ? r.data.session.user : null; });
    },
    entrar: function (email, pass) { return db.auth.signInWithPassword({ email: email, password: pass }).then(ok); },
    salir: function () { return db.auth.signOut(); },
    cuentas: function () { return db.from("cuentas").select("*").order("orden").then(ok); },
    categorias: function () { return db.from("categorias").select("*").order("orden").then(ok); },
    saldos: function (cuentaIds) {
      var filas = [];
      function pagina(inicio) {
        return db.from("saldos").select("*").in("cuenta_id", cuentaIds)
          .order("fecha").order("cuenta_id").range(inicio, inicio + 999).then(ok).then(function (d) {
            filas = filas.concat(d);
            return d.length === 1000 ? pagina(inicio + 1000) : filas;
          });
      }
      return pagina(0);
    },
    movimientos: function (cuentaIds, desde, hasta) {
      return paginado(function () {
        return db.from("movimientos").select("*").in("cuenta_id", cuentaIds).gte("fecha", desde).lt("fecha", hasta);
      });
    },
    movimientosDeCategorias: function (catIds, desde, hasta) {
      return paginado(function () {
        return db.from("movimientos").select("*").in("categoria_id", catIds).gte("fecha", desde).lt("fecha", hasta);
      });
    },
    actualizarMovimiento: function (id, cambios) {
      return db.from("movimientos").update(cambios).eq("id", id).then(ok);
    },
    recategorizarComercio: function (cuentaId, comercio, categoriaId) {
      return db.from("movimientos").update({ categoria_id: categoriaId })
        .eq("cuenta_id", cuentaId).eq("comercio", comercio).then(ok);
    },
    guardarRegla: function (patron, categoriaId, owner) {
      return db.from("reglas").upsert({ patron: patron, categoria_id: categoriaId, owner: owner },
        { onConflict: "patron,owner" }).then(ok);
    },
    crearMovimiento: function (fila) { return db.from("movimientos").insert(fila).then(ok); },
    borrarMovimiento: function (id) { return db.from("movimientos").delete().eq("id", id).then(ok); },
    subirTicket: function (cuentaId, blob) {
      var ruta = cuentaId + "/" + crypto.randomUUID() + ".jpg";
      return db.storage.from("tickets").upload(ruta, blob, { contentType: "image/jpeg" })
        .then(ok).then(function () { return ruta; });
    },
    urlTicket: function (ruta) {
      return db.storage.from("tickets").createSignedUrl(ruta, 3600).then(ok)
        .then(function (d) { return d.signedUrl; });
    }
  };
})();
