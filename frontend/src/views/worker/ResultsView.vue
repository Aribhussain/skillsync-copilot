<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'

import { db, type LocalDeclaration } from '../../lib/db'
import type { MappingResult, PCClaim, QP } from '../../lib/mapper/types'
import { loadQp } from '../../lib/qps'
import { onSyncChange } from '../../lib/sync'
import { confirmQualification } from '../../lib/worker'

const { t, locale } = useI18n()
const route = useRoute()

const decl = ref<LocalDeclaration | null>(null)
const selectedQp = ref<string>('')
const qp = ref<QP | null>(null)
const ticked = ref<Set<string>>(new Set())
const busy = ref(false)
const error = ref('')

// The server result replaces the on-device provisional result as soon as it exists.
const mapping = computed<MappingResult | undefined>(() => decl.value?.serverMapping ?? decl.value?.provisional)
const isProvisional = computed(() => !decl.value?.serverMapping && !!decl.value?.provisional)
const claims = computed<PCClaim[]>(() => (mapping.value?.claims[selectedQp.value] ?? []) as PCClaim[])

const userPicked = ref(false)

async function refresh() {
  const hadServer = !!decl.value?.serverMapping
  decl.value = (await db.declarations.get(String(route.params.clientId))) ?? null
  if (!decl.value) return
  const serverArrived = !hadServer && !!decl.value.serverMapping
  if (decl.value.confirmedQpId) {
    selectedQp.value = decl.value.confirmedQpId
  } else if (!selectedQp.value || (serverArrived && !userPicked.value)) {
    // follow the server's top-1 when it replaces the provisional result
    selectedQp.value = mapping.value?.top[0]?.qp_id ?? ''
    if (serverArrived) applyClaims(selectedQp.value)
  }
}

function applyClaims(id: string) {
  const claimed =
    decl.value?.confirmedQpId === id && decl.value.claimedPcIds
      ? decl.value.claimedPcIds
      : (mapping.value?.claims[id] ?? []).filter((c) => c.claimed).map((c) => c.pc_id)
  ticked.value = new Set(claimed)
}

watch(selectedQp, async (id) => {
  if (!id) return
  qp.value = await loadQp(id)
  applyClaims(id)
})

let unsubscribe: (() => void) | null = null
onMounted(() => {
  void refresh()
  unsubscribe = onSyncChange(() => void refresh())
})
onBeforeUnmount(() => unsubscribe?.())

function toggle(pcId: string) {
  const next = new Set(ticked.value)
  if (next.has(pcId)) next.delete(pcId)
  else next.add(pcId)
  ticked.value = next
}

async function confirm() {
  if (!decl.value || !selectedQp.value) return
  busy.value = true
  error.value = ''
  try {
    decl.value = await confirmQualification(decl.value.clientId, selectedQp.value, [...ticked.value])
  } catch (e) {
    error.value = String(e)
  } finally {
    busy.value = false
  }
}

function claimFor(pcId: string): PCClaim | undefined {
  return claims.value.find((c) => c.pc_id === pcId)
}
const pct = (x: number) => `${Math.round(x * 100)}%`
</script>

<template>
  <div v-if="decl && mapping" class="mx-auto grid max-w-3xl gap-4" data-testid="results-view">
    <section class="card">
      <div class="mb-2 flex flex-wrap items-center justify-between gap-2">
        <h1 class="text-2xl font-bold">{{ t('results.title') }}</h1>
        <span
          class="chip"
          :class="isProvisional ? 'bg-saffron-100' : 'bg-green-india-100 text-green-india-700'"
          data-testid="mapping-source"
          :data-provisional="isProvisional"
        >
          {{ isProvisional ? t('results.provisional') : t('results.server') }}
        </span>
      </div>
      <p class="mb-3 text-xs text-navy-700">
        {{ mapping.engine === 'hybrid' ? t('results.engineHybrid') : t('results.engineLite') }} ·
        {{ t('results.supportNote') }}
      </p>

      <p v-if="mapping.no_match" class="rounded-xl bg-saffron-100 p-3" data-testid="no-match">{{ t('results.noMatch') }}</p>

      <div v-if="mapping.lexicon_matches.length" class="mb-3">
        <span class="text-sm font-semibold">{{ t('results.understood') }}:</span>
        <div class="mt-1 flex flex-wrap gap-1.5" data-testid="lexicon-matches">
          <span v-for="m in mapping.lexicon_matches" :key="m.term" class="chip bg-navy-100">
            “{{ m.term }}” → <b>{{ m.canonical }}</b>
          </span>
        </div>
      </div>

      <div class="grid gap-2" role="radiogroup">
        <label
          v-for="q in mapping.top"
          :key="q.qp_id"
          class="block cursor-pointer rounded-xl border-2 p-3"
          :class="selectedQp === q.qp_id ? 'border-navy-900 bg-navy-50' : 'border-navy-100'"
          :data-testid="`qp-option-${q.rank}`"
        >
          <div class="flex items-start gap-3">
            <input
              v-model="selectedQp"
              type="radio"
              :value="q.qp_id"
              class="mt-1 h-5 w-5 accent-navy-900"
              :disabled="decl.status === 'confirmed'"
              @change="userPicked = true"
            />
            <div class="flex-1">
              <div class="flex flex-wrap items-center gap-2">
                <span class="text-lg font-bold">#{{ q.rank }} {{ locale === 'hi' && q.title_hi ? q.title_hi : q.title }}</span>
                <span class="chip bg-navy-100">NSQF {{ q.nsqf_level }}</span>
                <span class="chip" :class="q.source_kind === 'official' ? 'bg-green-india-100 text-green-india-700' : 'bg-saffron-100'">
                  {{ t(`results.source.${q.source_kind}`) }}
                </span>
              </div>
              <div class="mt-1 text-xs text-navy-700">{{ q.qp_id }} · {{ q.sector }}</div>
              <div class="mt-2 flex items-center gap-2">
                <div class="h-3 flex-1 overflow-hidden rounded-full bg-navy-100">
                  <div class="h-full rounded-full bg-green-india-600" :style="{ width: pct(q.confidence) }" />
                </div>
                <span class="w-24 text-right text-sm font-semibold" :data-testid="`qp-confidence-${q.rank}`">
                  {{ t('results.confidence') }} {{ pct(q.confidence) }}
                </span>
              </div>
              <div v-if="q.matched_terms.length" class="mt-2 flex flex-wrap gap-1">
                <span class="text-xs text-navy-700">{{ t('results.matched') }}:</span>
                <span v-for="w in q.matched_terms" :key="w" class="chip bg-saffron-100">{{ w }}</span>
              </div>
            </div>
          </div>
        </label>
      </div>
    </section>

    <section v-if="qp && !mapping.no_match" class="card" data-testid="claims">
      <h2 class="text-lg font-bold">{{ t('results.claimsTitle') }}</h2>
      <p class="mb-3 text-sm text-navy-700">{{ t('results.claimsHint') }}</p>
      <details v-for="nos in qp.nos" :key="nos.id" class="mb-2 rounded-xl border border-navy-100 p-2" :open="nos.pcs.some((p) => ticked.has(p.id))">
        <summary class="cursor-pointer font-semibold">
          {{ nos.title }}
          <span class="chip ml-1 bg-navy-100">{{ nos.pcs.filter((p) => ticked.has(p.id)).length }}/{{ nos.pcs.length }}</span>
        </summary>
        <label v-for="pc in nos.pcs" :key="pc.id" class="flex items-start gap-2 py-1.5 text-sm">
          <input
            type="checkbox"
            class="mt-0.5 h-5 w-5 shrink-0 accent-green-india-600"
            :checked="ticked.has(pc.id)"
            :disabled="decl.status === 'confirmed'"
            :data-testid="`claim-${pc.id}`"
            @change="toggle(pc.id)"
          />
          <span>
            <b>{{ pc.code }}</b> {{ pc.text }}
            <span v-if="claimFor(pc.id)?.claimed" class="chip ml-1 bg-green-india-100 text-green-india-700">
              {{ claimFor(pc.id)?.strength === 'strong' ? t('results.strong') : t('results.weak') }}:
              {{ claimFor(pc.id)?.matched_terms.join(', ') }}
            </span>
          </span>
        </label>
      </details>
    </section>

    <p v-if="error" class="rounded-lg bg-saffron-100 p-2 text-sm" role="alert">{{ error }}</p>
    <p v-if="decl.status === 'confirmed'" class="rounded-xl bg-green-india-100 p-3 font-semibold text-green-india-700" data-testid="confirmed">
      ✓ {{ t('results.confirmed') }}
      <span class="mt-1 block text-sm font-normal" :data-testid="decl.assessmentId ? 'request-synced' : 'request-queued'">
        {{ decl.assessmentId ? t('results.synced', { id: decl.assessmentId }) : t('results.queued') }}
      </span>
    </p>
    <button
      v-else
      class="btn-green w-full text-lg"
      :disabled="busy || mapping.no_match || !selectedQp"
      data-testid="confirm-qp"
      @click="confirm"
    >
      {{ t('results.confirm') }}
    </button>
  </div>
  <p v-else class="text-navy-700">{{ t('common.loading') }}</p>
</template>
