<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'

import CredentialCard from '../../components/CredentialCard.vue'
import { ApiError } from '../../lib/api'
import { fetchProfile, type Profile, signOff } from '../../lib/profile'
import { useAuthStore } from '../../stores/auth'

const { t } = useI18n()
const route = useRoute()
const auth = useAuthStore()
const id = Number(route.params.id)
const profile = ref<Profile | null>(null)
const error = ref('')

const decision = ref<string>('partial')
const justification = ref('')
const confirmed = ref(false)
const password = ref('')
const busy = ref(false)
const signOffError = ref('')

async function load() {
  try {
    profile.value = await fetchProfile(id)
    decision.value = profile.value.recommendation
  } catch (e) {
    error.value = String(e)
  }
}
onMounted(load)

async function submitSignOff() {
  busy.value = true
  signOffError.value = ''
  try {
    await signOff(id, {
      password: password.value,
      decision: decision.value,
      justification: justification.value || undefined,
      confirm: confirmed.value,
    })
    password.value = ''
    await load()
  } catch (e) {
    signOffError.value = e instanceof ApiError ? String(e.detail) : String(e)
  } finally {
    busy.value = false
  }
}

const STATUS: Record<string, string> = {
  competent: 'bg-green-india-100 text-green-india-700',
  partial: 'bg-saffron-100 text-navy-950',
  gap: 'bg-red-100 text-red-800',
}
const BAR: Record<string, string> = { competent: 'bg-green-india-600', partial: 'bg-saffron-500', gap: 'bg-red-500' }
</script>

<template>
  <div v-if="profile" class="grid gap-4" data-testid="profile-view">
    <section class="card">
      <div class="flex flex-wrap items-center justify-between gap-2">
        <h1 class="text-2xl font-bold">{{ t('profile.title') }}</h1>
        <RouterLink :to="`/assessor/assessment/${id}`" class="chip bg-navy-100 px-3 py-2">{{ t('common.back') }}</RouterLink>
      </div>
      <p class="text-navy-700">{{ profile.assessment.candidate }} · {{ profile.qp_title }} · NSQF {{ profile.nsqf_level }}</p>

      <div class="mt-3 grid gap-3 sm:grid-cols-3">
        <div class="rounded-xl p-3" :class="STATUS[profile.recommendation === 'full' ? 'competent' : profile.recommendation]" data-testid="recommendation" :data-rec="profile.recommendation">
          <div class="text-xs font-semibold">{{ t('profile.recommendation') }}</div>
          <div class="text-2xl font-bold">{{ t(`profile.rec.${profile.recommendation}`) }}</div>
        </div>
        <div class="rounded-xl bg-navy-50 p-3">
          <div class="text-xs font-semibold">{{ t('profile.aggregate') }}</div>
          <div class="text-2xl font-bold" data-testid="aggregate">{{ profile.aggregate_percent }}%</div>
          <div class="text-xs text-navy-700">{{ profile.earned_total }} / {{ profile.max_total }} · {{ t('profile.passRule') }}</div>
        </div>
        <div class="rounded-xl bg-navy-50 p-3">
          <div class="text-xs font-semibold">{{ t('profile.bridge') }}</div>
          <div class="text-2xl font-bold">{{ profile.bridge_modules.length }} · {{ profile.bridge_hours }} h</div>
        </div>
      </div>
      <p class="mt-2 text-sm">{{ profile.recommendation_reason }}</p>
      <p class="mt-1 text-xs text-navy-700">⚖ {{ profile.note }}</p>
    </section>

    <section class="card">
      <h2 class="mb-2 text-lg font-bold">{{ t('profile.byNos') }}</h2>
      <ul class="grid gap-3">
        <li v-for="n in profile.nos" :key="n.nos_id" :data-testid="`nos-row-${n.nos_id}`" :data-status="n.status">
          <div class="flex flex-wrap items-center justify-between gap-2">
            <span class="font-semibold">{{ n.nos_id }} · {{ n.title }}</span>
            <span class="chip" :class="STATUS[n.status]">{{ t(`profile.status.${n.status}`) }} · {{ n.percent }}%</span>
          </div>
          <div class="relative mt-1 h-3 overflow-hidden rounded-full bg-navy-100" role="img" :aria-label="`${n.percent}%`">
            <div class="h-full rounded-full" :class="BAR[n.status]" :style="{ width: `${Math.min(100, n.percent)}%` }" />
            <div class="absolute inset-y-0 w-0.5 bg-navy-900" style="left: 70%" :title="t('profile.passRule')" />
          </div>
          <p class="mt-1 text-xs text-navy-700">
            T {{ n.earned.theory }}/{{ n.marks.theory }} · P {{ n.earned.practical }}/{{ n.marks.practical }} · V {{ n.earned.viva }}/{{ n.marks.viva }} — {{ n.explanation }}
          </p>
          <p v-if="n.bridge_module" class="mt-1 rounded-lg bg-saffron-100 p-2 text-xs" :data-testid="`bridge-${n.nos_id}`">
            🎓 {{ t('profile.bridgeModule') }}: <b>{{ n.bridge_module.title }}</b> ({{ n.bridge_module.hours }} h)
          </p>
        </li>
      </ul>
    </section>

    <!-- Human gate: the only way to a decision -->
    <section v-if="profile.assessment.status === 'signed_off'" class="card" data-testid="signed-off">
      <h2 class="text-lg font-bold">✍ {{ t('signoff.done', { d: t(`profile.rec.${profile.decision}`) }) }}</h2>
      <p v-if="profile.decision_justification" class="text-sm text-navy-700">{{ profile.decision_justification }}</p>
      <CredentialCard v-if="profile.credential_id" class="mt-2" :credential-id="profile.credential_id" />
      <p v-else class="mt-2 text-sm text-navy-700">{{ t('signoff.noCredential') }}</p>
    </section>
    <section v-else-if="auth.user?.role === 'assessor'" class="card" data-testid="signoff-panel">
      <h2 class="text-lg font-bold">{{ t('signoff.title') }}</h2>
      <p class="text-sm text-navy-700">{{ t('signoff.lead') }}</p>
      <ul v-if="!profile.readiness.can_sign_off || profile.readiness.scored < profile.readiness.total" class="mt-2 list-disc pl-5 text-sm text-red-800">
        <li v-if="profile.readiness.scored < profile.readiness.total">{{ t('signoff.notScored', { n: profile.readiness.total - profile.readiness.scored }) }}</li>
        <li v-if="profile.readiness.pending_reasons.length">{{ t('signoff.pendingReasons', { n: profile.readiness.pending_reasons.length }) }}</li>
      </ul>
      <div class="mt-3 grid gap-3 sm:max-w-md">
        <label class="grid gap-1 text-sm font-semibold">
          {{ t('signoff.decision') }}
          <select v-model="decision" class="input" data-testid="signoff-decision">
            <option v-for="d in ['full', 'partial', 'gap']" :key="d" :value="d">
              {{ t(`profile.rec.${d}`) }}{{ d === profile.recommendation ? ` (${t('signoff.recommended')})` : '' }}
            </option>
          </select>
        </label>
        <label v-if="decision !== profile.recommendation" class="grid gap-1 text-sm font-semibold">
          {{ t('signoff.justification') }}
          <textarea v-model="justification" class="input py-2" rows="2" data-testid="signoff-justification" />
        </label>
        <label class="flex items-start gap-2 text-sm">
          <input v-model="confirmed" type="checkbox" class="mt-1 h-5 w-5" data-testid="signoff-confirm" />
          {{ t('signoff.confirm') }}
        </label>
        <label class="grid gap-1 text-sm font-semibold">
          {{ t('signoff.password') }}
          <input v-model="password" type="password" class="input" autocomplete="current-password" data-testid="signoff-password" />
        </label>
        <button class="btn-green" :disabled="busy || !confirmed || !password" data-testid="signoff-submit" @click="submitSignOff">
          ✍ {{ t('signoff.submit') }}
        </button>
        <p v-if="signOffError" class="rounded-lg bg-saffron-100 p-2 text-sm" role="alert" data-testid="signoff-error">{{ signOffError }}</p>
      </div>
    </section>
  </div>
  <p v-else-if="error" class="rounded-lg bg-saffron-100 p-2 text-sm" role="alert">{{ error }}</p>
  <p v-else class="text-navy-700">{{ t('common.loading') }}</p>
</template>
