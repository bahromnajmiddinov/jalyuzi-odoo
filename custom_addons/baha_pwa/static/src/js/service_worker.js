// Service Worker for Odoo Mobile PWA
const CACHE_NAME = 'odoo-mobile-v1.0.0';
const RUNTIME_CACHE = 'odoo-mobile-runtime';

// Files to cache on install
const STATIC_CACHE_URLS = [
  '/mobile',
  '/baha_pwa/static/src/css/mobile_app.css',
  '/baha_pwa/static/src/js/mobile_app.js',
  '/web/static/lib/jquery/jquery.js',
  '/web/static/src/css/bootstrap.css',
];

// API endpoints to cache dynamically
const API_CACHE_URLS = [
  '/mobile/api/menu',
  '/mobile/api/records',
];

// Install event - cache static assets
self.addEventListener('install', (event) => {
  console.log('[Service Worker] Installing...');
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => {
        console.log('[Service Worker] Caching static assets');
        return cache.addAll(STATIC_CACHE_URLS);
      })
      .then(() => self.skipWaiting())
  );
});

// Activate event - clean up old caches
self.addEventListener('activate', (event) => {
  console.log('[Service Worker] Activating...');
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cacheName) => {
          if (cacheName !== CACHE_NAME && cacheName !== RUNTIME_CACHE) {
            console.log('[Service Worker] Deleting old cache:', cacheName);
            return caches.delete(cacheName);
          }
        })
      );
    })
    .then(() => self.clients.claim())
  );
});

// Fetch event - serve from cache, fallback to network
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Skip cross-origin requests
  if (url.origin !== location.origin) {
    return;
  }

  // Handle API requests differently
  if (url.pathname.startsWith('/mobile/api/')) {
    event.respondWith(networkFirstStrategy(request));
  } 
  // Handle static assets
  else if (url.pathname.includes('/static/')) {
    event.respondWith(cacheFirstStrategy(request));
  }
  // Handle navigation requests
  else if (request.mode === 'navigate') {
    event.respondWith(networkFirstStrategy(request));
  }
  // Default strategy
  else {
    event.respondWith(cacheFirstStrategy(request));
  }
});

// Cache first, fallback to network
async function cacheFirstStrategy(request) {
  const cache = await caches.open(CACHE_NAME);
  const cachedResponse = await cache.match(request);
  
  if (cachedResponse) {
    console.log('[Service Worker] Serving from cache:', request.url);
    return cachedResponse;
  }
  
  try {
    console.log('[Service Worker] Fetching from network:', request.url);
    const networkResponse = await fetch(request);
    
    // Cache successful responses
    if (networkResponse.ok) {
      cache.put(request, networkResponse.clone());
    }
    
    return networkResponse;
  } catch (error) {
    console.error('[Service Worker] Fetch failed:', error);
    
    // Return offline page if available
    const offlinePage = await cache.match('/mobile/offline');
    if (offlinePage) {
      return offlinePage;
    }
    
    // Return a basic offline response
    return new Response('Offline - Content not available', {
      status: 503,
      statusText: 'Service Unavailable',
      headers: new Headers({
        'Content-Type': 'text/plain',
      }),
    });
  }
}

// Network first, fallback to cache
async function networkFirstStrategy(request) {
  const cache = await caches.open(RUNTIME_CACHE);
  
  try {
    console.log('[Service Worker] Fetching from network:', request.url);
    const networkResponse = await fetch(request);
    
    // Cache successful responses
    if (networkResponse.ok) {
      cache.put(request, networkResponse.clone());
    }
    
    return networkResponse;
  } catch (error) {
    console.log('[Service Worker] Network failed, trying cache:', request.url);
    const cachedResponse = await cache.match(request);
    
    if (cachedResponse) {
      return cachedResponse;
    }
    
    // Return error response
    return new Response(JSON.stringify({
      error: 'Offline',
      message: 'No network connection and no cached data available'
    }), {
      status: 503,
      statusText: 'Service Unavailable',
      headers: new Headers({
        'Content-Type': 'application/json',
      }),
    });
  }
}

// Background sync for offline actions
self.addEventListener('sync', (event) => {
  console.log('[Service Worker] Background sync:', event.tag);
  
  if (event.tag === 'sync-offline-data') {
    event.waitUntil(syncOfflineData());
  }
});

async function syncOfflineData() {
  // Get offline data from IndexedDB and sync to server
  console.log('[Service Worker] Syncing offline data...');
  // Implementation depends on your offline data storage strategy
}

// Push notification handler
self.addEventListener('push', (event) => {
  console.log('[Service Worker] Push notification received');
  
  const options = {
    body: event.data ? event.data.text() : 'New notification from Odoo',
    icon: '/baha_pwa/static/icons/icon-192x192.png',
    badge: '/baha_pwa/static/icons/badge-72x72.png',
    vibrate: [200, 100, 200],
    tag: 'odoo-notification',
    requireInteraction: false,
    actions: [
      {
        action: 'open',
        title: 'Open',
        icon: '/baha_pwa/static/icons/open-icon.png'
      },
      {
        action: 'close',
        title: 'Close',
        icon: '/baha_pwa/static/icons/close-icon.png'
      }
    ]
  };
  
  event.waitUntil(
    self.registration.showNotification('Odoo Mobile', options)
  );
});

// Notification click handler
self.addEventListener('notificationclick', (event) => {
  console.log('[Service Worker] Notification clicked:', event.action);
  
  event.notification.close();
  
  if (event.action === 'open') {
    event.waitUntil(
      clients.openWindow('/mobile')
    );
  }
});

// Message handler for communication with main app
self.addEventListener('message', (event) => {
  console.log('[Service Worker] Message received:', event.data);
  
  if (event.data.action === 'skipWaiting') {
    self.skipWaiting();
  }
  
  if (event.data.action === 'clearCache') {
    event.waitUntil(
      caches.keys().then((cacheNames) => {
        return Promise.all(
          cacheNames.map((cacheName) => caches.delete(cacheName))
        );
      })
    );
  }
});