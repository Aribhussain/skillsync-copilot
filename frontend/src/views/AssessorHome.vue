<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { type AssessmentCard, fetchQueue } from '../lib/assessor'
import { fetchMyIndex } from '../lib/calibration'
import { listStudies, type Study } from '../lib/studies'

const { t } = useI18n()
const queue = ref<AssessmentCard[]>([])
const fromCache = ref(false)
const error = ref('')

const myIndex = ref<{ index: number | null; bias: number | null; n: number } | null>(null)

onMounted(async () => {
  try {
    const r = await fetchQueue()
    queue.value = r.data
    fromCache.value = r.fromCache
  } catch (e) {
    error.value = String(e)
  }
  fetchMyIndex()
    .then((m) => (myIndex.value = m))
    .catch(() => undefined)
  listStudies()
    .then((s) => (studies.value = s))
    .catch(() => undefined)
})

const studies = ref<Study[]>([])
</script>

<template>
  <section class="card">
    <div class="mb-3 flex flex-wrap items-center justify-between gap-2">
      <h1 class="text-2xl font-bold">{{ t('home.assessorTitle') }}</h1>
      <span v-if="fromCache" class="chip bg-saffron-100">{{ t('assessor.offlineCopy') }}</span>
    </div>
    <div v-if="myIndex && myIndex.n" class="mb-3 rounded-xl bg-navy-50 p-3 text-sm" data-testid="my-index">
      <b>{{ t('qa.myIndex') }}: {{ myIndex.index }}</b>
      <span class="ml-2 text-navy-700">{{ t('qa.bias') }} {{ myIndex.bias! > 0 ? '+' : '' }}{{ myIndex.bias }} · n={{ myIndex.n }}</span>
      <div class="text-xs text-navy-700">{{ t('qa.myIndexNote') }}</div>
    </div>
    <div v-if="studies.length" class="mb-3 rounded-xl border-2 border-dashed border-navy-700 p-3" data-testid="my-studies">
      <div class="text-sm font-bold">🧪 {{ t('study.invited') }}</div>
      <RouterLink
        v-for="s in studies"
        :key="s.id"
        :to="`/assessor/studies/${s.id}`"
        class="mt-1 flex justify-between text-sm underline"
        :data-testid="`study-link-${s.id}`"
      >
        <span>{{ s.name }}</span>
        <span>OFF {{ s.progress.off }}/{{ s.progress.per_arm }} · ON {{ s.progress.on }}/{{ s.progress.per_arm }}</span>
      </RouterLink>
    </div>
    <p v-if="error" class="rounded-lg bg-saffron-100 p-2 text-sm" role="alert">{{ error }}</p>
    <p v-if="!queue.length && !error" class="text-navy-700">{{ t('assessor.emptyQueue') }}</p>
    <ul class="grid gap-2" data-testid="assessor-queue">
      <li v-for="a in queue" :key="a.id">
        <RouterLink
          :to="`/assessor/assessment/${a.id}`"
          class="flex flex-wrap items-center justify-between gap-2 rounded-xl border-2 border-navy-100 p-3 hover:border-navy-700"
          :data-testid="`queue-item-${a.id}`"
        >
          <div class="min-w-0 flex-1">
            <div class="font-bold">{{ a.candidate }}</div>
            <div class="text-sm text-navy-700">{{ a.qp_title }} · NSQF {{ a.nsqf_level }} · #{{ a.id }}</div>
          </div>
          <span class="chip bg-navy-100">{{ t('assessor.claimed', { n: a.claimed_pc_ids.length }) }}</span>
          <span class="chip" :class="a.status === 'requested' ? 'bg-saffron-100' : 'bg-green-india-100 text-green-india-700'">
            {{ t(`assessor.status.${a.status}`) }}
          </span>
        </RouterLink>
      </li>
    </ul>
  </section>
</template>
