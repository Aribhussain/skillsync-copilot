<script setup lang="ts">
import QRCode from 'qrcode'
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { openCredentialPdf, verifyPageUrl } from '../lib/profile'

const props = defineProps<{ credentialId: string; title?: string; result?: string }>()
const { t } = useI18n()
const qr = ref('')
const url = verifyPageUrl(props.credentialId)

onMounted(async () => {
  qr.value = await QRCode.toDataURL(url, { margin: 1, width: 180 })
})
</script>

<template>
  <div class="flex flex-wrap items-center gap-4 rounded-xl border-2 border-green-india-600 bg-green-india-100/40 p-3" data-testid="credential-card">
    <img v-if="qr" :src="qr" :alt="t('credential.qrAlt')" class="h-32 w-32 rounded-lg bg-white" data-testid="credential-qr" />
    <div class="min-w-0 flex-1 text-sm">
      <div class="text-base font-bold">🏅 {{ t('credential.issued') }}</div>
      <div v-if="title">{{ title }} · {{ result }}</div>
      <div class="truncate font-mono text-xs text-navy-700">{{ credentialId }}</div>
      <div class="mt-2 flex flex-wrap gap-2">
        <RouterLink :to="`/verify/${credentialId}`" class="btn-green min-h-10" data-testid="verify-link">✓ {{ t('credential.verify') }}</RouterLink>
        <button class="btn-ghost min-h-10" @click="openCredentialPdf(credentialId)">📄 {{ t('credential.pdf') }}</button>
      </div>
    </div>
  </div>
</template>
