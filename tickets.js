/* Cuentas de casa — reduce la foto de un ticket antes de subirla (lado máximo 1600 px, JPEG 0,7). */
(function () {
  "use strict";
  var LADO_MAX = 1600, CALIDAD = 0.7;

  function reducir(archivo) {
    return createImageBitmap(archivo, { imageOrientation: "from-image" }).then(function (img) {
      var escala = Math.min(1, LADO_MAX / Math.max(img.width, img.height));
      var lienzo = document.createElement("canvas");
      lienzo.width = Math.round(img.width * escala);
      lienzo.height = Math.round(img.height * escala);
      lienzo.getContext("2d").drawImage(img, 0, 0, lienzo.width, lienzo.height);
      img.close();
      return new Promise(function (resolver, rechazar) {
        lienzo.toBlob(function (blob) {
          if (blob) resolver(blob); else rechazar(new Error("No se pudo procesar la foto"));
        }, "image/jpeg", CALIDAD);
      });
    });
  }

  window.Tickets = { reducir: reducir };
})();
