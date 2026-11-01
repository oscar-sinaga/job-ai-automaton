// Minimal service worker. Some platforms require an active SW with a fetch
// handler as part of PWA installability / Web Share Target eligibility
// criteria. Deliberately does no offline caching -- that's not a V1 goal
// (docs/09_MOBILE_CAPTURE_DESIGN.md §7).
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (event) => event.waitUntil(self.clients.claim()));
self.addEventListener('fetch', () => {
	// No-op: not calling event.respondWith() lets the browser handle every
	// request with its normal network fetch.
});
