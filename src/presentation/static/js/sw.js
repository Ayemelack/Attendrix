/* Attendrix Service Worker — Offline-First Networking Layer
 *
 * This service worker enables:
 *   1. Offline page access (cached app shell)
 *   2. Network-first API with cache fallback
 *   3. Background sync for queued offline operations
 *   4. Graceful degradation during network outages
 *
 * Networking concepts demonstrated:
 *   - Cache-first vs network-first strategies
 *   - Offline fallback with stale-while-revalidate
 *   - Background sync events (SyncManager API)
 *   - Request queuing for unreliable networks
 */

const CACHE_VERSION = 'v1';
const STATIC_CACHE = `attendrix-static-${CACHE_VERSION}`;
const PAGE_CACHE = `attendrix-pages-${CACHE_VERSION}`;
const API_CACHE = `attendrix-api-${CACHE_VERSION}`;

const STATIC_ASSETS = [
  '/static/js/landing.js',
  '/static/js/i18n.js',
  '/static/js/responsive.js',
  '/static/js/device-fingerprint.js',
  '/static/js/network-monitor.js',
  '/static/js/network-topology.js',
  '/static/css/responsive.css',
  '/static/images/favicon.svg',
  '/static/images/icon-192.png',
  '/static/images/icon-512.png',
];

const APP_SHELL_PAGES = [
  '/',
  '/login',
  '/signup',
  '/signup-voucher',
  '/offline',
  '/product-overview',
  '/legal/privacy',
];

const API_CACHE_PREFIX = '/api/';

const OFFLINE_FALLBACK = '/offline';

/* ── INSTALL: Pre-cache the app shell ── */
self.addEventListener('install', function(event) {
  event.waitUntil(
    caches.open(STATIC_CACHE).then(function(cache) {
      return cache.addAll(STATIC_ASSETS).catch(function(err) {
        console.warn('SW: Static asset pre-cache warning:', err);
      });
    }).then(function() {
      return caches.open(PAGE_CACHE).then(function(cache) {
        return cache.addAll(APP_SHELL_PAGES).catch(function(err) {
          console.warn('SW: Page pre-cache warning:', err);
        });
      });
    }).then(function() {
      return self.skipWaiting();
    })
  );
});

/* ── ACTIVATE: Clean old caches ── */
self.addEventListener('activate', function(event) {
  const expectedCaches = [STATIC_CACHE, PAGE_CACHE, API_CACHE];
  event.waitUntil(
    caches.keys().then(function(cacheNames) {
      return Promise.all(
        cacheNames.map(function(cacheName) {
          if (expectedCaches.indexOf(cacheName) === -1) {
            console.log('SW: Clearing old cache:', cacheName);
            return caches.delete(cacheName);
          }
        })
      );
    }).then(function() {
      return self.clients.claim();
    })
  );
});

/* ── FETCH: Intelligent request handling ── */
self.addEventListener('fetch', function(event) {
  const request = event.request;
  const url = new URL(request.url);

  /* Skip non-GET, browser extensions, and CDN requests */
  if (request.method !== 'GET') {
    return;
  }
  if (url.origin !== self.location.origin && !url.href.includes('cdn.') && !url.href.includes('fonts.')) {
    return;
  }

  /* API requests: pass through without interception (auth headers must go direct) */
  if (url.pathname.startsWith(API_CACHE_PREFIX)) {
    return;
  }

  /* Static assets: cache-first */
  if (url.pathname.startsWith('/static/')) {
    event.respondWith(cacheFirstWithNetworkRefresh(request, STATIC_CACHE));
    return;
  }

  /* Pages: network-first with cache fallback */
  if (request.mode === 'navigate') {
    event.respondWith(networkFirstWithCacheFallback(request, PAGE_CACHE));
    return;
  }

  /* Everything else: network-first */
  event.respondWith(networkFirstWithCacheFallback(request, PAGE_CACHE));
});

/* ── BACKGROUND SYNC: Process offline queue when online ── */
self.addEventListener('sync', function(event) {
  if (event.tag === 'attendrix-sync') {
    event.waitUntil(processOfflineQueue());
  }
});

/* ── MESSAGE HANDLING: Queue offline operations from the page ── */
self.addEventListener('message', function(event) {
  if (event.data && event.data.type === 'QUEUE_OFFLINE_OPERATION') {
    queueOfflineOperation(event.data.payload).then(function() {
      /* Register a sync if supported */
      if ('sync' in self.registration) {
        self.registration.sync.register('attendrix-sync').catch(function() {});
      }
    });
  }
});

/* ── CACHE STRATEGIES ── */

/* Network-first: try network, fall back to cache, save fresh response */
async function networkFirstWithCacheFallback(request, cacheName) {
  var networkResponse;
  try {
    networkResponse = await fetch(request);
  } catch (err) {
    const cachedResponse = await caches.match(request);
    if (cachedResponse) {
      console.log('SW: Serving from cache (network failed):', request.url);
      return cachedResponse;
    }
    if (request.mode === 'navigate') {
      const fallback = await caches.match(OFFLINE_FALLBACK);
      if (fallback) return fallback;
    }
    return new Response(JSON.stringify({
      error: 'You are offline. This data will sync when connection is restored.',
      offline: true
    }), {
      status: 503,
      headers: { 'Content-Type': 'application/json' }
    });
  }
  /* Cache in background — never replace a good response with 503 */
  if (networkResponse && networkResponse.ok) {
    try {
      const cache = await caches.open(cacheName);
      cache.put(request, networkResponse.clone());
    } catch (_) {}
  }
  return networkResponse;
}

/* Cache-first: serve from cache, refresh in background */
async function cacheFirstWithNetworkRefresh(request, cacheName) {
  const cachedResponse = await caches.match(request);
  if (cachedResponse) {
    fetch(request).then(function(networkResponse) {
      if (networkResponse && networkResponse.ok) {
        caches.open(cacheName).then(function(cache) {
          cache.put(request, networkResponse);
        });
      }
    }).catch(function() {});
    return cachedResponse;
  }
  try {
    const networkResponse = await fetch(request);
    if (networkResponse && networkResponse.ok) {
      const cache = await caches.open(cacheName);
      cache.put(request, networkResponse.clone());
    }
    return networkResponse;
  } catch (err) {
    return new Response('Resource unavailable offline', { status: 503 });
  }
}

/* ── OFFLINE QUEUE OPERATIONS ── */

async function queueOfflineOperation(payload) {
  const db = await openOfflineDB();
  const tx = db.transaction('offline_queue', 'readwrite');
  const store = tx.objectStore('offline_queue');
  store.add({
    id: generateId(),
    payload: payload,
    timestamp: new Date().toISOString(),
    retries: 0
  });
  await tx.done;
}

async function processOfflineQueue() {
  const db = await openOfflineDB();
  const tx = db.transaction('offline_queue', 'readonly');
  const store = tx.objectStore('offline_queue');
  const allItems = await store.getAll();
  await tx.done;

  for (const item of allItems) {
    try {
      const response = await fetch(item.payload.url, {
        method: item.payload.method || 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: item.payload.body ? JSON.stringify(item.payload.body) : undefined
      });
      if (response.ok) {
        const deleteTx = db.transaction('offline_queue', 'readwrite');
        const deleteStore = deleteTx.objectStore('offline_queue');
        deleteStore.delete(item.id);
        await deleteTx.done;
      }
    } catch (err) {
      console.warn('SW: Background sync failed for', item.id, err);
    }
  }
}

/* ── INDEXEDDB HELPERS ── */

function openOfflineDB() {
  return new Promise(function(resolve, reject) {
    const request = indexedDB.open('AttendrixOffline', 1);
    request.onupgradeneeded = function(event) {
      const db = event.target.result;
      if (!db.objectStoreNames.contains('offline_queue')) {
        db.createObjectStore('offline_queue', { keyPath: 'id' });
      }
    };
    request.onsuccess = function() { resolve(request.result); };
    request.onerror = function() { reject(request.error); };
  });
}

function generateId() {
  return 'offline_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
}
