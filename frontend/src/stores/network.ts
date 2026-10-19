import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { API_BASE } from '../lib/api'
import { pendingOutboxCount } from '../lib/db'

/** navigator.onLine only says "a network interface is up", so we also ping /health. */
export const useNetworkStore = defineStore('network', () => {
  const browserOnline = ref(typeof navigator === 'undefined' ? true : navigator.onLine)
  const serverReachable = ref(true)
  const outboxCount = ref(0)
  const lastCheckedAt = ref<number | null>(null)
  const online = computed(() => browserOnline.value && serverReachable.value)

  async function checkServer(): Promise<boolean> {
    if (!browserOnline.value) {
      serverReachable.value = false
      return false
    }
    try {
      const ctrl = new AbortController()
      const timer = setTimeout(() => ctrl.abort(), 4000)
      const res = await fetch(`${API_BASE}/health`, { signal: ctrl.signal, cache: 'no-store' })
      clearTimeout(timer)
      serverReachable.value = res.ok
    } catch {
      serverReachable.value = false
    }
    lastCheckedAt.value = Date.now()
    return serverReachable.value
  }

  async function refreshOutbox(): Promise<void> {
    outboxCount.value = await pendingOutboxCount()
  }

  let started = false
  function start(): void {
    if (started) return
    started = true
    window.addEventListener('online', () => {
      browserOnline.value = true
      void checkServer()
    })
    window.addEventListener('offline', () => {
      browserOnline.value = false
      serverReachable.value = false
    })
    void checkServer()
    void refreshOutbox()
    setInterval(() => void checkServer(), 15000)
  }

  return { browserOnline, serverReachable, online, outboxCount, lastCheckedAt, checkServer, refreshOutbox, start }
})
