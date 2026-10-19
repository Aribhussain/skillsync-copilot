<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { type EvidenceItem, evidenceImageUrl, fetchEvidence } from '../lib/assessor'

const props = defineProps<{ assessmentId: number }>()
const { t } = useI18n()
const items = ref<EvidenceItem[]>([])
const urls = ref<Record<number, string>>({})

const SEVERITY_CLASS: Record<string, string> = {
  high: 'bg-red-100 text-red-800 border border-red-300',
  medium: 'bg-saffron-100 text-navy-950',
  low: 'bg-navy-100 text-navy-900',
  info: 'bg-navy-50 text-navy-700',
}

async function load() {
  try {
    items.value = (await fetchEvidence(props.assessmentId)).data
    for (const e of items.value) {
      if (!urls.value[e.id]) evidenceImageUrl(e).then((u) => (urls.value = { ...urls.value, [e.id]: u })).catch(() => undefined)
    }
  } catch {
    items.value = []
  }
}
onMounted(load)
onBeforeUnmount(() => Object.values(urls.value).forEach((u) => URL.revokeObjectURL(u)))
defineExpose({ load })
</script>

<template>
  <section class="card" data-testid="evidence-panel">
    <div class="mb-2 flex items-center justify-between">
      <h2 class="text-lg font-bold">{{ t('evidence.title') }}</h2>
      <button class="chip bg-navy-100 px-3 py-1.5" @click="load">↻</button>
    </div>
    <p v-if="!items.length" class="text-sm text-navy-700">{{ t('evidence.none') }}</p>
    <ul class="grid gap-3 sm:grid-cols-3">
      <li v-for="e in items" :key="e.id" class="rounded-xl border border-navy-100 p-2" :data-testid="`evidence-${e.shot}`">
        <img v-if="urls[e.id]" :src="urls[e.id]" alt="" class="aspect-square w-full rounded-lg object-cover" />
        <div v-else class="aspect-square w-full rounded-lg bg-navy-50" />
        <div class="mt-1 flex flex-wrap items-center gap-1 text-xs">
          <b>{{ t(`capture.shot.${e.shot}`) }}</b>
          <span class="chip" :class="e.signature_valid ? 'bg-green-india-100 text-green-india-700' : 'bg-red-100 text-red-800'">
            {{ e.signature_valid ? '🔏 ' + t('evidence.sigOk') : t('evidence.sigBad') }}
          </span>
          <span v-if="e.source === 'simulated'" class="chip bg-saffron-100">{{ t('capture.simulatedTag') }}</span>
        </div>
        <div class="mt-1 font-mono text-[10px] text-navy-700">sha256 {{ e.sha256.slice(0, 16) }}… · pHash {{ e.phash }}</div>
        <ul class="mt-1 grid gap-1">
          <li
            v-for="f in e.integrity_flags ?? []"
            :key="f.code"
            class="rounded-md px-2 py-1 text-xs"
            :class="SEVERITY_CLASS[f.severity]"
            :data-testid="`flag-${f.code}`"
            :data-severity="f.severity"
          >
            <b>{{ t(`evidence.flag.${f.code}`, f.code) }}</b> — {{ f.detail }}
          </li>
        </ul>
      </li>
    </ul>
    <p class="mt-2 text-xs text-navy-700">{{ t('evidence.reviewNote') }}</p>
  </section>
</template>
