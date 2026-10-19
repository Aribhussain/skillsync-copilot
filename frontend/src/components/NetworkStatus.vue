<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { useNetworkStore } from '../stores/network'

const net = useNetworkStore()
const { t } = useI18n()

const label = computed(() => {
  if (!net.browserOnline) return t('net.offline')
  if (!net.serverReachable) return t('net.serverDown')
  return t('net.online')
})
</script>

<template>
  <div class="flex items-center gap-2" data-testid="network-status">
    <span
      class="chip"
      :class="net.online ? 'bg-green-india-100 text-green-india-700' : 'bg-saffron-100 text-navy-950'"
      :data-online="net.online"
      role="status"
      aria-live="polite"
    >
      <span class="h-2.5 w-2.5 rounded-full" :class="net.online ? 'bg-green-india-600' : 'bg-saffron-600'" />
      {{ label }}
    </span>
    <span
      class="chip bg-navy-100 text-navy-900"
      data-testid="outbox-count"
      :data-count="net.outboxCount"
      :title="net.outboxCount ? t('net.outbox', { n: net.outboxCount }, net.outboxCount) : t('net.outboxEmpty')"
    >
      <svg aria-hidden="true" viewBox="0 0 20 20" class="h-3.5 w-3.5 fill-current">
        <path d="M3 4h14v2H3zm0 5h14v2H3zm0 5h9v2H3z" />
      </svg>
      {{ net.outboxCount }}
    </span>
  </div>
</template>
