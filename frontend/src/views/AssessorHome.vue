<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { type AssessmentCard, fetchQueue } from '../lib/assessor'

const { t } = useI18n()
const queue = ref<AssessmentCard[]>([])
const fromCache = ref(false)
const error = ref('')

onMounted(async () => {
  try {
    const r = await fetchQueue()
    queue.value = r.data
    fromCache.value = r.fromCache
  } catch (e) {
    error.value = String(e)
  }
})
</script>

<template>
  <section class="card">
    <div class="mb-3 flex flex-wrap items-center justify-between gap-2">
      <h1 class="text-2xl font-bold">{{ t('home.assessorTitle') }}</h1>
      <span v-if="fromCache" class="chip bg-saffron-100">{{ t('assessor.offlineCopy') }}</span>
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
