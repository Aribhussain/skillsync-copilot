<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { createStudy, listStudies, type Study, studyResults, type StudyResults } from '../lib/studies'

const { t } = useI18n()
const studies = ref<Study[]>([])
const results = ref<Record<number, StudyResults>>({})
const name = ref('')
const busy = ref(false)

async function load() {
  studies.value = await listStudies()
  for (const s of studies.value) results.value = { ...results.value, [s.id]: await studyResults(s.id) }
}
onMounted(() => void load().catch(() => undefined))

async function create() {
  busy.value = true
  try {
    await createStudy(name.value.trim() || 'Consistency study')
    name.value = ''
    await load()
  } finally {
    busy.value = false
  }
}
const fmt = (x: number | null) => (x === null ? '—' : x.toFixed(2))
</script>

<template>
  <section class="card" data-testid="studies-panel">
    <h2 class="font-bold">{{ t('study.panelTitle') }}</h2>
    <p class="text-xs text-navy-700">{{ t('study.panelLead') }}</p>
    <div class="mt-2 flex flex-wrap gap-2">
      <input v-model="name" class="input min-h-10 max-w-xs" :placeholder="t('study.namePlaceholder')" data-testid="study-name" />
      <button class="btn-primary min-h-10" :disabled="busy" data-testid="study-create" @click="create">{{ t('study.create') }}</button>
    </div>
    <div v-if="studies.length" class="mt-3 overflow-x-auto">
      <table class="w-full min-w-[520px] text-left text-sm">
        <thead>
          <tr class="border-b-2 border-navy-900">
            <th class="py-1">{{ t('study.name') }}</th>
            <th>{{ t('study.scores') }}</th>
            <th>α OFF</th>
            <th>α ON ({{ t('qa.blind') }})</th>
            <th>α ON ({{ t('qa.final') }})</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="s in studies" :key="s.id" class="border-b border-navy-100" :data-testid="`study-row-${s.id}`">
            <td class="py-1 font-semibold">{{ s.name }}</td>
            <td>{{ results[s.id]?.scores.off ?? 0 }} / {{ results[s.id]?.scores.on ?? 0 }}</td>
            <td>{{ fmt(results[s.id]?.alpha_off ?? null) }}</td>
            <td>{{ fmt(results[s.id]?.alpha_on_blind ?? null) }}</td>
            <td>{{ fmt(results[s.id]?.alpha_on_final ?? null) }}</td>
          </tr>
        </tbody>
      </table>
      <p class="mt-1 text-xs text-navy-700">{{ t('study.realNote') }}</p>
    </div>
  </section>
</template>
