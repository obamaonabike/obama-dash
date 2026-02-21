// Angles @ Time — Service Worker
// Caches the dashboard shell for offline use
// Live Binance data always fetches fresh from network

const CACHE_NAME    = 'angles-v1';
const SHELL_ASSETS  = [
  '/angles_dashboard.html',
  '/manifest.json',
  'https://cdn.jsdelivr.net/npm/lightweight-charts@3.8.0/dist/lightweight-charts.standalone.production.js',
  'https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=VT323&display=swap',
];

// Install — cache shell assets
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => {
      return cache.addAll(SHELL_ASSETS).catch(err => {
        console.warn('SW: Some assets failed to cache:', err);
      });
    })
  );
  self.skipWaiting();
});

// Activate — clean up old caches
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(
        keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k))
      )
    )
  );
  self.clients.claim();
});

// Fetch strategy:
// - Binance API calls → network only (always live data)
// - Everything else → cache first, fallback to network
self.addEventListener('fetch', event => {
  const url = event.request.url;

  // Always fetch live data from Binance/APIs from network
  if (url.includes('binance.com') || url.includes('fapi.binance')) {
    event.respondWith(fetch(event.request));
    return;
  }

  // Shell assets — cache first
  event.respondWith(
    caches.match(event.request).then(cached => {
      return cached || fetch(event.request).then(response => {
        // Cache new assets as we encounter them
        if (response && response.status === 200) {
          const clone = response.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
        }
        return response;
      });
    }).catch(() => {
      // Offline fallback for navigation requests
      if (event.request.mode === 'navigate') {
        return caches.match('/angles_dashboard.html');
      }
    })
  );
});
