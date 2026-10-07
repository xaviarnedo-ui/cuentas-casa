var CACHE = "cuentas-v8";
// Esqueleto de la app. Mantener en sync con los <script>/<link> de index.html (incluido ?v=N).
var ASSETS = [
  "./", "./index.html", "./styles.css?v=8", "./manifest.json",
  "./icons/icon-192.png", "./icons/icon-512.png",
  "./supabase-js.min.js?v=8", "./supabase-client.js?v=8", "./calculos.js?v=8", "./datos.js?v=8",
  "./datos-demo.js?v=8", "./tickets.js?v=8", "./ui-mes.js?v=8", "./ui-movs.js?v=8", "./ui-nuevo.js?v=8", "./ui-piso.js?v=8", "./ui-patrimonio.js?v=8", "./app.js?v=8"
];

self.addEventListener("install", function (e) {
  e.waitUntil(caches.open(CACHE).then(function (c) {
    return Promise.all(ASSETS.map(function (u) { return c.add(new Request(u, { cache: "reload" })).catch(function () {}); }));
  }).then(function () { return self.skipWaiting(); }));
});

self.addEventListener("activate", function (e) {
  e.waitUntil(caches.keys().then(function (keys) {
    return Promise.all(keys.filter(function (k) { return k !== CACHE; }).map(function (k) { return caches.delete(k); }));
  }).then(function () { return self.clients.claim(); }));
});

// Solo se cachea el esqueleto propio; las peticiones a Supabase (otro origen) van siempre a la red.
self.addEventListener("fetch", function (e) {
  if (e.request.method !== "GET") return;
  if (new URL(e.request.url).origin !== self.location.origin) return;
  e.respondWith(caches.match(e.request).then(function (r) { return r || fetch(e.request); }));
});
