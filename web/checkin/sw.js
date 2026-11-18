// Service worker van de gast-app: de pagina zelf (HTML, stijl, scripts) blijft op de gsm bewaard, zodat ze ook
// zonder netwerk opent (bv. aan de deur). De gegevens (en de pincode) bewaart app.js zelf; de API gaat nooit via
// deze cache. Eerst het netwerk, de bewaarde versie alleen als het netwerk niet antwoordt.
const CACHE = "gastapp-v1";
const FILES = ["./", "index.html", "style.css", "app.js", "i18n.js", "countries.js", "config.js", "favicon.svg"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(FILES)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
    .then(() => self.clients.claim()));
});

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.origin !== location.origin || url.pathname.startsWith("/api/")) return;
  e.respondWith(
    fetch(e.request).then((res) => {
      if (res.ok) { const copy = res.clone(); caches.open(CACHE).then((c) => c.put(e.request, copy)); }
      return res;
    }).catch(() => caches.match(e.request, { ignoreSearch: true })
      .then((hit) => hit || (e.request.mode === "navigate" ? caches.match("index.html") : undefined)))
  );
});
