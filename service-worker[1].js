// Service Worker for Economics News PWA
// Enables offline mode, caching, and background sync

const CACHE_NAME = 'economics-news-v1';
const DATA_CACHE_NAME = 'economics-news-data-v1';

// Files to cache for offline use
const FILES_TO_CACHE = [
  '/',
  '/index.html',
  '/economics_news.json',
  '/manifest.json'
];

// Install event - cache essential files
self.addEventListener('install', (event) => {
  console.log('[ServiceWorker] Installing...');
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      console.log('[ServiceWorker] Caching app shell');
      return cache.addAll(FILES_TO_CACHE);
    })
  );
  self.skipWaiting();
});

// Activate event - clean up old caches
self.addEventListener('activate', (event) => {
  console.log('[ServiceWorker] Activating...');
  event.waitUntil(
    caches.keys().then((keyList) => {
      return Promise.all(keyList.map((key) => {
        if (key !== CACHE_NAME && key !== DATA_CACHE_NAME) {
          console.log('[ServiceWorker] Removing old cache', key);
          return caches.delete(key);
        }
      }));
    })
  );
  self.clients.claim();
});

// Fetch event - serve from cache, fallback to network
self.addEventListener('fetch', (event) => {
  // Handle JSON data requests
  if (event.request.url.includes('.json')) {
    event.respondWith(
      caches.open(DATA_CACHE_NAME).then((cache) => {
        return fetch(event.request)
          .then((response) => {
            // Cache the fresh data
            cache.put(event.request.url, response.clone());
            return response;
          })
          .catch(() => {
            // Return cached data if offline
            return cache.match(event.request);
          });
      })
    );
    return;
  }

  // Handle other requests (HTML, CSS, JS)
  event.respondWith(
    caches.match(event.request).then((response) => {
      return response || fetch(event.request);
    })
  );
});

// Background sync for updating news when connection is restored
self.addEventListener('sync', (event) => {
  console.log('[ServiceWorker] Background sync', event.tag);
  if (event.tag === 'update-news') {
    event.waitUntil(updateNewsData());
  }
});

// Push notification handler (for future updates)
self.addEventListener('push', (event) => {
  console.log('[ServiceWorker] Push received');
  const data = event.data ? event.data.json() : {};
  
  const title = data.title || 'Economics News Update';
  const options = {
    body: data.body || 'New economics news available',
    icon: '/icon-192.png',
    badge: '/badge-72.png',
    tag: 'economics-news',
    requireInteraction: false,
    data: {
      url: data.url || '/'
    }
  };

  event.waitUntil(
    self.registration.showNotification(title, options)
  );
});

// Notification click handler
self.addEventListener('notificationclick', (event) => {
  console.log('[ServiceWorker] Notification clicked');
  event.notification.close();

  event.waitUntil(
    clients.openWindow(event.notification.data.url || '/')
  );
});

// Helper function to update news data
async function updateNewsData() {
  try {
    const response = await fetch('/economics_news.json');
    const cache = await caches.open(DATA_CACHE_NAME);
    await cache.put('/economics_news.json', response);
    console.log('[ServiceWorker] News data updated');
    return true;
  } catch (error) {
    console.error('[ServiceWorker] Failed to update news:', error);
    return false;
  }
}

// Periodic background sync (if supported)
self.addEventListener('periodicsync', (event) => {
  if (event.tag === 'update-news-periodic') {
    event.waitUntil(updateNewsData());
  }
});
