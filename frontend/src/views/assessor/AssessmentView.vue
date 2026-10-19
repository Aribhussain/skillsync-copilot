<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'

import RubricAnchors from '../../components/RubricAnchors.vue'
import { fetchPlan, overrideRoute, type PlanPC, type PlanResponse, startAssessment } from '../../lib/assessor'
import { ROUTE_ICON, type Route } from '../../lib/evidencePlan'

const { t } = useI18n()
const route = useRoute()
const id = Number(route.params.id)

const data = ref<PlanResponse | null>(null)
const fromCache = ref(false)
const error = ref('')
const openRubric = ref<string | null>(null)
const editing = ref<string | null>(null)
const newRoute = ref<Route>('observe')
const reason = ref('')

const routes: Route[] = ['observe', 'photo', 'viva', 'declaration+spot-check']
const card = computed(() => data.value?.assessment)

async function load() {
  error.value = ''
  try {
    const r = await fetchPlan(id)
    data.value = r.data
    fromCache.value = r.fromCache
  } catch (e) {
    error.value = String(e)
  }
}
onMounted(load)

async function start() {
  try {
    const c = await startAssessment(id)
    if (data.value) data.value = { ...data.value, assessment: c }
  } catch (e) {
    error.value = String(e)
  }
}

function beginEdit(pc: PlanPC) {
  editing.value = pc.pc_id
  newRoute.value = pc.route
  reason.value = ''
}

async function saveOverride(pc: PlanPC) {
  try {
    await overrideRoute(id, pc.pc_id, newRoute.value, reason.value)
    editing.value = null
    await load()
  } catch (e) {
    error.value = String(e)
  }
}
</script>

<template>
  <div v-if="data && card" class="grid gap-4" data-testid="assessment-view">
    <section class="card">
      <div class="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h1 class="text-2xl font-bold">{{ card.candidate }}</h1>
          <p class="text-navy-700">{{ data.qp.title }} · {{ data.qp.id }} · NSQF {{ data.qp.nsqf_level }}</p>
        </div>
        <span v-if="fromCache" class="chip bg-saffron-100">{{ t('assessor.offlineCopy') }}</span>
      </div>

      <div class="mt-3 flex flex-wrap items-center gap-2 text-sm" data-testid="plan-summary">
        <span v-for="r in routes" :key="r" class="chip bg-navy-100">{{ ROUTE_ICON[r] }} {{ t(`route.${r}`) }}: {{ data.summary[r] }}</span>
        <span class="chip bg-saffron-100">🔒 {{ t('assessor.lockedCount', { n: data.summary.locked }) }}</span>
      </div>

      <div class="mt-4 flex flex-wrap items-center gap-3">
        <button v-if="!card.challenge_code" class="btn-primary" data-testid="start-assessment" @click="start">
          {{ t('assessor.start') }}
        </button>
        <div v-else class="rounded-xl border-2 border-dashed border-navy-900 px-4 py-2" data-testid="challenge-code">
          <div class="text-xs font-semibold text-navy-700">{{ t('assessor.challengeCode') }}</div>
          <div class="font-mono text-3xl font-bold tracking-widest">{{ card.challenge_code }}</div>
        </div>
        <p class="text-xs text-navy-700">{{ t('assessor.challengeHint') }}</p>
        <RouterLink
          v-if="card.challenge_code"
          :to="`/assessor/assessment/${id}/capture`"
          class="btn-saffron"
          data-testid="go-capture"
        >
          📷 {{ t('capture.goCapture') }}
        </RouterLink>
      </div>
    </section>

    <p v-if="error" class="rounded-lg bg-saffron-100 p-2 text-sm" role="alert">{{ error }}</p>

    <section v-for="nos in data.plan" :key="nos.nos_id" class="card" :data-testid="`nos-${nos.nos_id}`">
      <h2 class="text-lg font-bold">{{ nos.nos_id }} · {{ nos.title }}</h2>
      <p class="mb-2 text-xs text-navy-700">
        {{ t('assessor.marks', { t: nos.marks.theory, p: nos.marks.practical, v: nos.marks.viva }) }}
      </p>
      <ul class="divide-y divide-navy-100">
        <li v-for="pc in nos.pcs" :key="pc.pc_id" class="py-2" :data-testid="`pc-${pc.pc_id}`">
          <div class="flex flex-wrap items-start gap-2">
            <span class="chip mt-0.5 bg-navy-900 text-white">{{ pc.code }}</span>
            <p class="min-w-0 flex-1 text-sm">{{ pc.text }}</p>
          </div>
          <div class="mt-1.5 flex flex-wrap items-center gap-1.5 pl-1">
            <span class="chip bg-navy-100" :data-testid="`route-${pc.pc_id}`" :data-route="pc.route">
              {{ ROUTE_ICON[pc.route] }} {{ t(`route.${pc.route}`) }}
            </span>
            <span
              v-if="pc.locked"
              class="chip bg-saffron-100"
              :title="pc.reason"
              :data-testid="`lock-${pc.pc_id}`"
            >
              🔒 {{ pc.critical ? t('assessor.critical') : t('assessor.safety') }}
            </span>
            <span v-if="pc.claimed" class="chip bg-green-india-100 text-green-india-700">{{ t('assessor.claimedByWorker') }}</span>
            <span v-if="pc.rule === 'override'" class="chip bg-navy-100">✎ {{ t('assessor.overridden') }}</span>
            <button class="chip bg-white text-navy-900 underline" @click="openRubric = openRubric === pc.pc_id ? null : pc.pc_id">
              {{ t('assessor.rubric') }}
            </button>
            <button v-if="!pc.locked" class="chip bg-white text-navy-900 underline" @click="beginEdit(pc)">
              {{ t('assessor.changeRoute') }}
            </button>
          </div>
          <p class="mt-1 pl-1 text-xs text-navy-700" :data-testid="`reason-${pc.pc_id}`">{{ pc.reason }}</p>
          <div v-if="editing === pc.pc_id" class="mt-2 grid gap-2 rounded-xl bg-navy-50 p-2 sm:grid-cols-[auto_1fr_auto]">
            <select v-model="newRoute" class="input min-h-10">
              <option v-for="r in routes" :key="r" :value="r">{{ t(`route.${r}`) }}</option>
            </select>
            <input v-model="reason" class="input min-h-10" :placeholder="t('assessor.reasonPlaceholder')" />
            <button class="btn-primary min-h-10" :disabled="reason.trim().length < 3" @click="saveOverride(pc)">{{ t('common.save') }}</button>
          </div>
          <RubricAnchors v-if="openRubric === pc.pc_id" class="mt-2" :rubric="data.rubric" :signal="pc.ai_signal" />
        </li>
      </ul>
    </section>
  </div>
  <p v-else-if="error" class="rounded-lg bg-saffron-100 p-2 text-sm" role="alert">{{ error }}</p>
  <p v-else class="text-navy-700">{{ t('common.loading') }}</p>
</template>
