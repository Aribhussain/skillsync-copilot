<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import CredentialCard from '../components/CredentialCard.vue'
import type { LocalDeclaration } from '../lib/db'
import { myCredentials } from '../lib/profile'
import { hasConsent, myDeclarations } from '../lib/worker'
import { useAuthStore } from '../stores/auth'

const { t, locale } = useI18n()
const auth = useAuthStore()
const consented = ref<boolean | null>(null)
const items = ref<LocalDeclaration[]>([])

const creds = ref<Awaited<ReturnType<typeof myCredentials>>>([])

onMounted(async () => {
  consented.value = await hasConsent(auth.user!.username)
  items.value = await myDeclarations(auth.user!.username)
  myCredentials()
    .then((c) => (creds.value = c))
    .catch(() => undefined)
})

function topTitle(d: LocalDeclaration): string {
  const m = d.serverMapping ?? d.provisional
  const top = m?.top.find((q) => q.qp_id === d.confirmedQpId) ?? m?.top[0]
  if (!top || m?.no_match) return '—'
  return locale.value === 'hi' && top.title_hi ? top.title_hi : top.title
}
</script>

<template>
  <div class="grid gap-4">
    <section class="card">
      <h1 class="text-2xl font-bold">{{ t('home.workerTitle', { name: auth.user?.full_name ?? '' }) }}</h1>
      <p class="mb-4 text-navy-700">{{ t('home.workerLead') }}</p>
      <template v-if="consented === false">
        <p class="mb-2 rounded-lg bg-saffron-100 p-2 text-sm">{{ t('worker.consentFirst') }}</p>
        <RouterLink to="/worker/consent" class="btn-green w-full sm:w-auto" data-testid="go-consent">
          {{ t('worker.giveConsent') }}
        </RouterLink>
      </template>
      <RouterLink v-else-if="consented" to="/worker/declare" class="btn-saffron w-full text-lg sm:w-auto" data-testid="go-declare">
        🎤 {{ t('worker.declareCta') }}
      </RouterLink>
    </section>

    <section v-if="creds.length" class="card" data-testid="my-credentials">
      <h2 class="mb-2 text-lg font-bold">{{ t('credential.mine') }}</h2>
      <div class="grid gap-2">
        <CredentialCard v-for="c in creds" :key="c.credential_id" :credential-id="c.credential_id" :title="c.title" :result="t(`profile.rec.${c.result}`)" />
      </div>
    </section>

    <section class="card">
      <h2 class="mb-2 text-lg font-bold">{{ t('worker.myRequests') }}</h2>
      <p v-if="!items.length" class="text-sm text-navy-700">{{ t('worker.none') }}</p>
      <ul class="grid gap-2">
        <li v-for="d in items" :key="d.clientId" class="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-navy-100 p-3">
          <div class="min-w-0 flex-1">
            <div class="font-semibold">{{ topTitle(d) }}</div>
            <div class="truncate text-xs text-navy-700">{{ d.narrative || d.cards.join(', ') }}</div>
          </div>
          <span class="chip bg-navy-100" :data-testid="`decl-status-${d.status}`">{{ t(`worker.status.${d.status}`) }}</span>
          <RouterLink :to="`/worker/results/${d.clientId}`" class="chip bg-navy-900 px-3 py-2 text-white">
            {{ t('worker.viewResult') }}
          </RouterLink>
        </li>
      </ul>
    </section>
  </div>
</template>
