/// <reference lib="webworker" />
/**
 * SkillSync service worker (vite-plugin-pwa injectManifest).
 *  - precaches the app shell, the seed QP pack, rubric images and demo samples
 *  - SPA navigation fallback, so deep links open offline
 *  - runtime caching: QP pack / lexicon / QP details (network-first, fall back to cache)
 *    and golden-packet images (cache-first)
 *  - Background Sync: on a 'skillsync-outbox' sync event it asks open tabs to flush the
 *    outbox. The outbox logic runs in the page (it needs the session token and IndexedDB
 *    keys), so if no tab is open the queue simply waits for the next visit / online event.
 */
import { clientsClaim } from 'workbox-core'
import { ExpirationPlugin } from 'workbox-expiration'
import { cleanupOutdatedCaches, createHandlerBoundToURL, precacheAndRoute } from 'workbox-precaching'
import { NavigationRoute, registerRoute } from 'workbox-routing'
import { CacheFirst, NetworkFirst } from 'workbox-strategies'

declare let self: ServiceWorkerGlobalScope

precacheAndRoute(self.__WB_MANIFEST)
cleanupOutdatedCaches()
void self.skipWaiting()
clientsClaim()

registerRoute(new NavigationRoute(createHandlerBoundToURL('/index.html')))

registerRoute(
  ({ url, request }) => request.method === 'GET' && /\/(packs\/(latest|version)|lexicon|qps(\/[^/]+)?)$/.test(url.pathname),
  new NetworkFirst({ cacheName: 'skillsync-api-packs', networkTimeoutSeconds: 4 }),
)
registerRoute(
  ({ url, request }) => request.method === 'GET' && /\/studies\/\d+\/packets\/[^/]+\/image$/.test(url.pathname),
  new CacheFirst({ cacheName: 'skillsync-golden-images', plugins: [new ExpirationPlugin({ maxEntries: 60 })] }),
)

interface SyncEventLike extends ExtendableEvent {
  tag: string
}

self.addEventListener('sync', (event) => {
  const e = event as SyncEventLike
  if (e.tag !== 'skillsync-outbox') return
  e.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clients) => {
      for (const c of clients) c.postMessage({ type: 'skillsync:flush' })
    }),
  )
})
