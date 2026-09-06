/* TERRA NOVA SW v4 — estratégias por tipo + Safari iOS
 *
 * cache-first          estáticos versionados
 * stale-while-revalidate  páginas de catálogo + JSON
 * network-only         carrinho, checkout, pedido, push
 * stale-if-error       se a rede falhar, usa cache mesmo vencido
 *
 * iOS: addAll atômico falha inteiro; quota ~50MB; sem Background Sync;
 * Cache.match precisa ignoreSearch no start_url ?source=pwa;
 * só cacheia Response.status === 200 (redirect quebra no WebKit).
 */
const VERSION = 'v6';
const SHELL = 'tn-shell-' + VERSION;
const PAGES = 'tn-pages-' + VERSION;
const DATA = 'tn-data-' + VERSION;
const IMAGES = 'tn-img-' + VERSION;

const PRECACHE = [
  '/m/',
  '/m/offline/',
  '/m/produtos/',
  '/m/relevantes/',
  '/m/conta/',
  '/m/compat/',
  '/m/catalogo.json',
  '/static/css/app.css',
  '/static/app/app.js',
  '/static/img/logo.svg',
  '/static/img/icon-120.png',
  '/static/img/icon-180.png',
  '/static/img/icon-192.png',
  '/static/img/icon-192.webp',
  '/static/img/icon-512.png',
  '/static/img/splash-1170x2532.png',
  '/static/app/manifest.webmanifest'
];

const LIMITS = { [SHELL]: 24, [PAGES]: 20, [DATA]: 10, [IMAGES]: 24 };
const TTL = {
  [SHELL]: 7 * 24 * 3600 * 1000,
  [PAGES]: 60 * 60 * 1000,
  [DATA]: 5 * 60 * 1000,
  [IMAGES]: 7 * 24 * 3600 * 1000
};

self.addEventListener('install', (event) => {
  event.waitUntil((async () => {
    const cache = await caches.open(SHELL);
    // iOS: um 404 derruba addAll inteiro — gravamos um a um
    await Promise.all(PRECACHE.map(async (url) => {
      try {
        const res = await fetch(url, { credentials: 'same-origin' });
        if (isCacheableResponse(res)) await cache.put(url, stamp(res));
      } catch (err) { /* segue o install */ }
    }));
    await self.skipWaiting();
  })());
});

self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    const keep = new Set([SHELL, PAGES, DATA, IMAGES]);
    const keys = await caches.keys();
    await Promise.all(keys.filter((k) => k.startsWith('tn-') && !keep.has(k)).map((k) => caches.delete(k)));
    if (self.registration.navigationPreload) {
      try { await self.registration.navigationPreload.enable(); } catch (e) {}
    }
    await self.clients.claim();
  })());
});

function isCacheableResponse(res) {
  return res && res.status === 200 && res.type === 'basic';
}

function stamp(res) {
  const headers = new Headers(res.headers);
  headers.set('X-TN-Cached-At', String(Date.now()));
  headers.set('X-TN-SW', VERSION);
  return new Response(res.body, { status: res.status, statusText: res.statusText, headers });
}

function cachedAt(res) {
  const raw = res && res.headers.get('X-TN-Cached-At');
  return raw ? Number(raw) : 0;
}

function isFresh(res, bucket) {
  const t = cachedAt(res);
  if (!t) return true;
  return (Date.now() - t) < (TTL[bucket] || 0);
}

async function trim(bucket) {
  const max = LIMITS[bucket];
  if (!max) return;
  const cache = await caches.open(bucket);
  const keys = await cache.keys();
  if (keys.length <= max) return;
  await Promise.all(keys.slice(0, keys.length - max).map((k) => cache.delete(k)));
}

const MAX_IMAGE_BYTES = 180 * 1024; // iOS: não estourar cota com splash/foto

async function put(bucket, req, res) {
  if (!isCacheableResponse(res)) return;
  const len = Number(res.headers.get('content-length') || 0);
  if (bucket === IMAGES && len > MAX_IMAGE_BYTES) return;
  const cache = await caches.open(bucket);
  await cache.put(req, stamp(res.clone()));
  await trim(bucket);
}

async function matchLoose(req) {
  return caches.match(req, { ignoreSearch: true, ignoreVary: true });
}

async function cacheFirst(req, bucket) {
  const cached = await matchLoose(req);
  if (cached) {
    if (!isFresh(cached, bucket)) revalidate(req, bucket);
    return cached;
  }
  const res = await fetch(req);
  await put(bucket, req, res);
  return res;
}

async function staleWhileRevalidate(req, bucket, fallback) {
  const cached = await matchLoose(req);
  const network = revalidate(req, bucket);
  if (cached) return cached;
  try {
    return await network;
  } catch (err) {
    if (fallback) {
      const off = await caches.match(fallback);
      if (off) return off;
    }
    throw err;
  }
}

function revalidate(req, bucket) {
  return fetch(req).then((res) => {
    put(bucket, req, res);
    return res;
  });
}

async function networkOnly(req) {
  return fetch(req);
}

function isStatic(url) {
  return url.pathname.startsWith('/static/');
}
function isImage(url, dest) {
  return dest === 'image' || /\.(png|jpg|jpeg|svg|webp|gif)$/i.test(url.pathname);
}
function isCatalog(url) {
  return url.pathname.endsWith('/catalogo.json') || url.pathname.endsWith('/buscar.json');
}
function isSensitive(url) {
  const p = url.pathname;
  return p.includes('/carrinho')
    || p.includes('/checkout')
    || p.includes('/pedido')
    || p.includes('/push/')
    || p.includes('/webhooks/')
    || p.includes('/painel/')
    || p.includes('/entrar')
    || p.includes('/django-admin');
}
function isAppPage(url) {
  return url.pathname === '/m/' || url.pathname.startsWith('/m/');
}
function isSplash(url) {
  return /splash-\d+x\d+\.png$/i.test(url.pathname);
}
function isProductPage(url) {
  return url.pathname.startsWith('/m/produto/');
}

/* Roteador dinâmico: a estratégia nasce do URL, não de uma lista fixa. */
function routeFor(req) {
  const url = new URL(req.url);
  if (isSensitive(url)) return { strategy: 'network-only' };
  if (isCatalog(url)) return { strategy: 'swr', bucket: DATA, fallback: '/m/catalogo.json' };
  if (isSplash(url) || (isImage(url, req.destination) && !isStatic(url))) {
    return { strategy: 'cache-first', bucket: IMAGES };
  }
  if (isStatic(url)) return { strategy: 'cache-first', bucket: SHELL };
  if (isProductPage(url)) return { strategy: 'swr', bucket: PAGES, fallback: '/m/offline/' };
  if (isAppPage(url)) return { strategy: 'swr', bucket: PAGES, fallback: '/m/offline/' };
  return { strategy: 'network-only' };
}

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;
  if (req.headers.has('range')) return;
  const url = new URL(req.url);
  if (url.origin !== location.origin) return;
  const route = routeFor(req);
  if (route.strategy === 'network-only') return;
  if (route.strategy === 'cache-first') {
    event.respondWith(cacheFirst(req, route.bucket));
    return;
  }
  if (route.strategy === 'swr') {
    event.respondWith(staleWhileRevalidate(req, route.bucket, route.fallback));
  }
});

async function warm(urls) {
  const slice = (urls || []).slice(0, 12);
  await Promise.all(slice.map(async (raw) => {
    try {
      const req = new Request(raw, { credentials: 'same-origin' });
      const route = routeFor(req);
      if (route.strategy === 'network-only') return;
      const res = await fetch(req);
      const bucket = route.bucket || PAGES;
      await put(bucket, req, res);
    } catch (err) {}
  }));
}

self.addEventListener('push', (event) => {
  let data = { title: 'TERRA NOVA', body: 'Você tem uma novidade na clínica.', url: '/m/' };
  if (event.data) {
    try { data = Object.assign(data, event.data.json()); }
    catch (e) { data.body = event.data.text(); }
  }
  const options = {
    body: data.body,
    icon: '/static/img/icon-192.png',
    badge: '/static/img/icon-192.png',
    lang: 'pt-BR',
    data: { url: data.url || '/m/' }
  };
  event.waitUntil(self.registration.showNotification(data.title, options));
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const target = (event.notification.data && event.notification.data.url) || '/m/';
  event.waitUntil((async () => {
    const all = await clients.matchAll({ type: 'window', includeUncontrolled: true });
    for (const client of all) {
      if (client.url.includes('/m/')) {
        if (client.navigate) {
          try { await client.navigate(target); } catch (e) {}
        }
        if (client.focus) return client.focus();
      }
    }
    if (clients.openWindow) return clients.openWindow(target);
  })());
});

self.addEventListener('message', (event) => {
  const data = event.data || {};
  if (data.type === 'TN_SKIP_WAITING') self.skipWaiting();
  if (data.type === 'TN_CLEAR_CACHES') {
    event.waitUntil(caches.keys().then((keys) => Promise.all(keys.filter((k) => k.startsWith('tn-')).map((k) => caches.delete(k)))));
  }
  if (data.type === 'TN_WARM' && data.urls) {
    event.waitUntil(warm(data.urls));
  }
});
