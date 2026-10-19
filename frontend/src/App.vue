<script setup lang="ts">
import { onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import AppHeader from './components/AppHeader.vue'
import { loadPack, refreshPack } from './lib/pack'
import { flush, onSyncChange, wakeAll } from './lib/sync'
import './lib/worker' // registers the worker outbox handlers at start-up
import { useAuthStore } from './stores/auth'
import { useNetworkStore } from './stores/network'

const { t } = useI18n()
const net = useNetworkStore()
const auth = useAuthStore()

async function syncNow() {
  if (!net.online || !auth.isAuthenticated) return
  await flush()
  refreshPack().catch(() => undefined)
}

onMounted(() => {
  net.start()
  onSyncChange(() => void net.refreshOutbox())
  loadPack().catch(() => undefined) // warm the offline mapper
  void syncNow()
  setInterval(() => void syncNow(), 15_000)
})

// Connectivity is back: retry everything immediately instead of waiting for backoff.
watch(
  () => net.online,
  async (online) => {
    if (online) {
      await wakeAll()
      await syncNow()
    }
  },
)
watch(() => auth.isAuthenticated, (ok) => ok && void syncNow())
</script>

<template>
  <div class="flex min-h-screen flex-col">
    <AppHeader />
    <main class="mx-auto w-full max-w-5xl flex-1 px-3 py-4 sm:px-4 sm:py-6">
      <RouterView />
    </main>
    <footer class="border-t border-navy-100 bg-white">
      <div class="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-2 px-3 py-3 text-xs sm:px-4">
        <span class="chip bg-saffron-100 text-navy-950" data-testid="synthetic-badge" :title="t('app.syntheticNote')">
          ⚠ {{ t('app.syntheticBadge') }}
        </span>
        <span class="text-navy-700">SIH 2026 · PS 26242 ·
          <RouterLink to="/about" class="underline">{{ t('about.title') }}</RouterLink>
        </span>
      </div>
    </footer>
  </div>
</template>
