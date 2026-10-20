<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'

import { verifyCredential, type VerifyResult } from '../lib/profile'

const { t } = useI18n()
const route = useRoute()
const result = ref<VerifyResult | null>(null)
const error = ref('')

onMounted(async () => {
  try {
    result.value = await verifyCredential(String(route.params.id))
  } catch (e) {
    error.value = String(e)
  }
})
</script>

<template>
  <section class="card mx-auto max-w-xl" data-testid="verify-view">
    <h1 class="text-2xl font-bold">{{ t('credential.verifyTitle') }}</h1>
    <div v-if="result" class="mt-3 grid gap-3">
      <div
        class="rounded-xl p-4 text-center"
        :class="result.valid ? 'bg-green-india-100 text-green-india-700' : 'bg-red-100 text-red-800'"
        data-testid="verify-status"
        :data-valid="result.valid"
      >
        <div class="text-4xl">{{ result.valid ? '✓' : '✗' }}</div>
        <div class="text-lg font-bold">{{ result.valid ? t('credential.valid') : t('credential.invalid') }}</div>
        <div v-if="!result.valid && result.reason" class="text-sm">{{ result.reason }}</div>
      </div>
      <dl class="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
        <dt class="font-semibold">{{ t('credential.holder') }}</dt><dd>{{ result.holder }}</dd>
        <dt class="font-semibold">{{ t('credential.qualification') }}</dt><dd>{{ result.qualification }}</dd>
        <dt class="font-semibold">{{ t('credential.result') }}</dt><dd class="font-bold">{{ t(`profile.rec.${result.result}`) }}</dd>
        <dt class="font-semibold">{{ t('credential.issuedOn') }}</dt><dd>{{ result.issued.slice(0, 10) }}</dd>
        <dt class="font-semibold">{{ t('credential.signature') }}</dt><dd>{{ result.signature_valid ? 'Ed25519 ✓' : '✗' }}</dd>
        <dt class="font-semibold">{{ t('credential.issuer') }}</dt><dd class="break-all font-mono text-xs">{{ result.issuer.id }}</dd>
        <dt class="font-semibold">{{ t('credential.status') }}</dt><dd>{{ result.status }}</dd>
      </dl>
      <p class="rounded-lg bg-saffron-100 p-2 text-xs">⚠ {{ result.note }}</p>
    </div>
    <p v-else-if="error" class="mt-3 rounded-lg bg-red-100 p-3 text-sm text-red-800" role="alert" data-testid="verify-error">{{ t('credential.notFound') }}</p>
    <p v-else class="mt-3 text-navy-700">{{ t('common.loading') }}</p>
  </section>
</template>
