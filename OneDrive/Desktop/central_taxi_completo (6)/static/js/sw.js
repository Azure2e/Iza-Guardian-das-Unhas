const CACHE = "conesul-pwa-v3";
const PRECACHE = [
  "/",
  "/static/css/style.css",
  "/static/css/admin.css",
  "/static/css/themes.css",
  "/static/css/responsive.css",
  "/static/css/animations.css",
  "/static/js/theme-auto.js",
  "/static/js/mapa_vivo.js",
  "/static/js/pwa.js",
  "/static/img/pwa-192.png",
  "/static/img/pwa-512.png",
  "/static/vendor/leaflet.js",
  "/static/vendor/leaflet.css"
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE).then((cache) => cache.addAll(PRECACHE).catch(() => null))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== location.origin) return;
  if (url.pathname.startsWith("/api/") || url.pathname.startsWith("/admin/tema")) return;
  event.respondWith(
    caches.match(req).then((hit) => {
      const fresh = fetch(req)
        .then((res) => {
          if (res && res.ok && url.pathname.startsWith("/static/")) {
            const copy = res.clone();
            caches.open(CACHE).then((c) => c.put(req, copy));
          }
          return res;
        })
        .catch(() => hit);
      return hit || fresh;
    })
  );
});

self.addEventListener("push", (event) => {
  var data = {};
  try { data = event.data ? event.data.json() : {}; } catch (e) { data = { title: "Central Táxi", body: event.data && event.data.text() }; }
  event.waitUntil(
    self.registration.showNotification(data.title || "Central Táxi Cone Sul", {
      body: data.body || "Nova atualização",
      icon: "/static/img/pwa-192.png",
      badge: "/static/img/pwa-192.png",
      data: { url: data.url || "/" }
    })
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  var url = (event.notification.data && event.notification.data.url) || "/";
  event.waitUntil(clients.openWindow(url));
});
