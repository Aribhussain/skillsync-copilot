<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'

import RubricAnchors from '../../components/RubricAnchors.vue'
import { ApiError } from '../../lib/api'
import type { Reveal } from '../../lib/scoring'
import { reviseStudyScore, studyImageUrl, studyTask, type StudyTask, submitStudyScore } from '../../lib/studies'

const { t } = useI18n()
const route = useRoute()
const id = Number(route.params.id)

const arm = ref<'off' | 'on'>('off')
const task = ref<StudyTask | null>(null)
const image = ref('')
const picked = ref<Record<string, number>>({})
const reveals = ref<Record<string, Reveal>>({})
const finals = ref<Record<string, number>>({})
const openRubric = ref<string | null>(null)
const error = ref('')

const finished = computed(() => task.value && task.value.packet_id === null)

async function load() {
  error.value = ''
  try {
    task.value = await studyTask(id, arm.value)
    if (task.value.packet_id === null && arm.value === 'off') {
      arm.value = 'on'
      task.value = await studyTask(id, 'on')
    }
    reveals.value = {}
    picked.value = {}
    if (task.value.image_url) image.value = await studyImageUrl(task.value.image_url)
  } catch (e) {
    error.value = e instanceof ApiError ? String(e.detail) : String(e)
  }
}
onMounted(load)

async function lock(pcId: string) {
  const tk = task.value
  if (!tk?.packet_id || picked.value[pcId] === undefined) return
  const r = await submitStudyScore(id, { packet_id: tk.packet_id, pc_id: pcId, arm: arm.value, score: picked.value[pcId] })
  if (r.ai) reveals.value = { ...reveals.value, [pcId]: r.ai }
  tk.pcs = tk.pcs?.map((p) => (p.pc_id === pcId ? { ...p, done: true } : p))
}

async function revise(pcId: string, level: number) {
  if (!task.value?.packet_id) return
  finals.value = { ...finals.value, [pcId]: level }
  await reviseStudyScore(id, { packet_id: task.value.packet_id, pc_id: pcId, final_score: level })
}

const allDone = computed(() => task.value?.pcs?.every((p) => p.done) ?? false)
</script>

<template>
  <div class="grid gap-4" data-testid="study-view">
    <section class="card">
      <h1 class="text-2xl font-bold">{{ t('study.title') }}</h1>
      <p class="text-sm">
        <span class="chip" :class="arm === 'off' ? 'bg-navy-100' : 'bg-green-india-100 text-green-india-700'" data-testid="study-arm" :data-arm="arm">
          {{ arm === 'off' ? t('study.armOff') : t('study.armOn') }}
        </span>
        <span v-if="task" class="ml-2 text-navy-700">
          OFF {{ task.progress.off }}/{{ task.progress.per_arm }} · ON {{ task.progress.on }}/{{ task.progress.per_arm }}
        </span>
      </p>
      <p class="mt-1 text-xs text-navy-700">{{ arm === 'off' ? t('study.offHint') : t('study.onHint') }}</p>
    </section>
    <p v-if="error" class="rounded-lg bg-saffron-100 p-2 text-sm" role="alert">{{ error }}</p>
    <section v-if="finished" class="card text-green-india-700" data-testid="study-finished">✓ {{ t('study.finished') }}</section>
    <section v-else-if="task?.packet_id" class="card">
      <div class="grid gap-4 md:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]">
        <img v-if="image" :src="image" alt="" class="w-full rounded-xl" />
        <ul class="grid gap-2">
          <li v-for="pc in task.pcs" :key="pc.pc_id" class="rounded-xl border border-navy-100 p-2" :data-testid="`study-pc-${pc.pc_id}`">
            <div class="text-sm"><b>{{ pc.nos_id.replace('ASC/', '') }} {{ pc.code }}</b> {{ pc.text }}</div>
            <div v-if="!pc.done" class="mt-1 flex flex-wrap items-center gap-1">
              <button
                v-for="lvl in [0, 1, 2, 3]"
                :key="lvl"
                class="h-10 w-10 rounded-lg border-2 font-bold"
                :class="picked[pc.pc_id] === lvl ? 'border-navy-900 bg-navy-900 text-white' : 'border-navy-100'"
                :data-testid="`study-pick-${pc.pc_id}-${lvl}`"
                @click="picked = { ...picked, [pc.pc_id]: lvl }"
              >
                {{ lvl }}
              </button>
              <button class="btn-primary min-h-10" :disabled="picked[pc.pc_id] === undefined" :data-testid="`study-lock-${pc.pc_id}`" @click="lock(pc.pc_id)">🔒</button>
              <button v-if="arm === 'on'" class="chip bg-white text-navy-900 underline" @click="openRubric = openRubric === pc.pc_id ? null : pc.pc_id">{{ t('assessor.rubric') }}</button>
            </div>
            <div v-else-if="reveals[pc.pc_id]" class="mt-1 rounded-lg bg-navy-50 p-2 text-xs">
              {{ t('scoring.aiSays') }}: <b>{{ reveals[pc.pc_id].level ?? '—' }}</b> — {{ reveals[pc.pc_id].explanation }}
              <div class="mt-1 flex items-center gap-1">
                {{ t('scoring.finalScore') }}:
                <button v-for="lvl in [0, 1, 2, 3]" :key="lvl" class="h-7 w-7 rounded border font-bold" :class="finals[pc.pc_id] === lvl ? 'bg-navy-900 text-white' : 'bg-white'" @click="revise(pc.pc_id, lvl)">{{ lvl }}</button>
              </div>
            </div>
            <div v-else class="mt-1 text-xs text-green-india-700">✓</div>
            <RubricAnchors v-if="arm === 'on' && openRubric === pc.pc_id && task.rubric" class="mt-2" :rubric="task.rubric" :signal="pc.ai_signal" />
          </li>
        </ul>
      </div>
      <button class="btn-saffron mt-3 w-full" :disabled="!allDone" data-testid="study-next" @click="load">{{ t('study.next') }}</button>
    </section>
  </div>
</template>
