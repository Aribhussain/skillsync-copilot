<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'

import PcScorer from '../../components/PcScorer.vue'
import { fetchPlan, type PlanResponse } from '../../lib/assessor'
import { fetchMyScores, pendingScore, type ScoreRow } from '../../lib/scoring'
import { onSyncChange } from '../../lib/sync'

const { t } = useI18n()
const route = useRoute()
const id = Number(route.params.id)

const plan = ref<PlanResponse | null>(null)
const rows = ref<Record<string, ScoreRow>>({})
const pending = ref<Record<string, number>>({})
const nosFilter = ref<string>('')
const error = ref('')

const total = computed(() => plan.value?.plan.reduce((n, nos) => n + nos.pcs.length, 0) ?? 0)
const scored = computed(() => Object.keys(rows.value).length + Object.keys(pending.value).filter((k) => !rows.value[k]).length)
const visible = computed(() => (plan.value?.plan ?? []).filter((n) => !nosFilter.value || n.nos_id === nosFilter.value))

async function load() {
  try {
    plan.value = (await fetchPlan(id)).data
    const list = await fetchMyScores(id)
    rows.value = Object.fromEntries(list.map((r) => [r.pc_id, r]))
    const p: Record<string, number> = {}
    for (const nos of plan.value.plan)
      for (const pc of nos.pcs) {
        const v = await pendingScore(id, pc.pc_id)
        if (v !== undefined) p[pc.pc_id] = v
      }
    pending.value = p
  } catch (e) {
    error.value = String(e)
  }
}

let unsubscribe: (() => void) | null = null
onMounted(() => {
  void load()
  unsubscribe = onSyncChange(() => void load())
})
onBeforeUnmount(() => unsubscribe?.())
</script>

<template>
  <div v-if="plan" class="grid grid-cols-1 gap-4" data-testid="scoring-view">
    <section class="card">
      <div class="flex flex-wrap items-center justify-between gap-2">
        <h1 class="text-2xl font-bold">{{ t('scoring.title') }}</h1>
        <RouterLink :to="`/assessor/assessment/${id}`" class="chip bg-navy-100 px-3 py-2">{{ t('common.back') }}</RouterLink>
      </div>
      <p class="text-sm text-navy-700">{{ plan.assessment.candidate }} · {{ plan.qp.title }}</p>
      <div class="mt-2 h-3 overflow-hidden rounded-full bg-navy-100">
        <div class="h-full bg-green-india-600" :style="{ width: `${total ? (100 * scored) / total : 0}%` }" />
      </div>
      <p class="mt-1 text-xs" data-testid="scoring-progress">{{ t('scoring.progress', { n: scored, total }) }}</p>
      <p class="mt-2 rounded-lg bg-navy-50 p-2 text-xs">🛡 {{ t('scoring.blindFirstExplainer') }}</p>
      <div class="mt-2 flex gap-1 overflow-x-auto pb-1 text-xs">
        <button class="chip shrink-0 px-3 py-1.5" :class="!nosFilter ? 'bg-navy-900 text-white' : 'bg-navy-100'" @click="nosFilter = ''">
          {{ t('scoring.allNos') }}
        </button>
        <button
          v-for="n in plan.plan"
          :key="n.nos_id"
          class="chip shrink-0 px-3 py-1.5"
          :class="nosFilter === n.nos_id ? 'bg-navy-900 text-white' : 'bg-navy-100'"
          :data-testid="`nos-filter-${n.nos_id.replace('ASC/', '')}`"
          @click="nosFilter = n.nos_id"
        >
          {{ n.nos_id.replace('ASC/', '') }}
        </button>
      </div>
    </section>
    <p v-if="error" class="rounded-lg bg-saffron-100 p-2 text-sm" role="alert">{{ error }}</p>
    <section v-for="nos in visible" :key="nos.nos_id" class="card">
      <h2 class="mb-2 text-lg font-bold">{{ nos.nos_id }} · {{ nos.title }}</h2>
      <div class="grid gap-2">
        <PcScorer
          v-for="pc in nos.pcs"
          :key="pc.pc_id"
          :assessment-id="id"
          :pc="pc"
          :rubric="plan.rubric"
          :row="rows[pc.pc_id]"
          :pending="pending[pc.pc_id]"
          @scored="load"
        />
      </div>
    </section>
  </div>
  <p v-else-if="error" class="rounded-lg bg-saffron-100 p-2 text-sm" role="alert">{{ error }}</p>
  <p v-else class="text-navy-700">{{ t('common.loading') }}</p>
</template>
