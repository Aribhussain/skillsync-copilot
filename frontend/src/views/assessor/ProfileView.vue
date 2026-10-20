<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'

import { fetchProfile, type Profile } from '../../lib/profile'

const { t } = useI18n()
const route = useRoute()
const id = Number(route.params.id)
const profile = ref<Profile | null>(null)
const error = ref('')

async function load() {
  try {
    profile.value = await fetchProfile(id)
  } catch (e) {
    error.value = String(e)
  }
}
onMounted(load)

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
  </div>
  <p v-else-if="error" class="rounded-lg bg-saffron-100 p-2 text-sm" role="alert">{{ error }}</p>
  <p v-else class="text-navy-700">{{ t('common.loading') }}</p>
</template>
