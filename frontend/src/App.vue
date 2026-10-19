<script setup lang="ts">
import { onMounted } from 'vue'
import { useI18n } from 'vue-i18n'

import AppHeader from './components/AppHeader.vue'
import { useNetworkStore } from './stores/network'

const { t } = useI18n()
const net = useNetworkStore()

onMounted(() => net.start())
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
