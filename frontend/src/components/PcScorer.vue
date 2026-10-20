<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import type { PlanPC, Rubric } from '../lib/assessor'
import { ROUTE_ICON } from '../lib/evidencePlan'
import { REASON_CODES, refreshAi, type Reveal, reviseScore, type ScoreRow, submitBlindScore } from '../lib/scoring'
import RubricAnchors from './RubricAnchors.vue'

const props = defineProps<{
  assessmentId: number
  pc: PlanPC
  rubric: Rubric
  row?: ScoreRow
  pending?: number
}>()
const emit = defineEmits<{ scored: [] }>()
const { t, locale } = useI18n()

const picked = ref<number | null>(null)
const busy = ref(false)
const error = ref('')
const showRubric = ref(false)
const reveal = ref<Reveal | null>(null)
const blind = ref<number | null>(null)
const finalScore = ref<number | null>(null)
const reason = ref<string>('')
const note = ref('')
const saved = ref(false)
const queued = ref(false)

watch(
  () => props.row,
  (row) => {
    if (!row) return
    blind.value = row.blind_score
    finalScore.value = row.final_score
    reason.value = row.reason_code ?? ''
    note.value = row.note ?? ''
    reveal.value = {
      status: row.ai_status,
      level: row.ai_level,
      confidence: row.ai_confidence,
      explanation: row.ai_explanation,
      model_version: row.ai_model_version,
      gap: row.gap,
      reason_required: row.reason_required,
    }
    saved.value = !row.reason_required || !!row.reason_code
    queued.value = false
  },
  { immediate: true },
)
watch(
  () => props.pending,
  (p) => {
    if (p !== undefined && !props.row) {
      blind.value = p
      queued.value = true
    }
  },
  { immediate: true },
)

const gapClass = computed(() => {
  const g = Math.abs(reveal.value?.gap ?? 0)
  return g >= 2 ? 'border-red-400 bg-red-50' : g === 1 ? 'border-saffron-500 bg-saffron-100/50' : 'border-green-india-600 bg-green-india-100/50'
})
async function lockBlind() {
  if (picked.value === null) return
  busy.value = true
  error.value = ''
  try {
    const r = await submitBlindScore(props.assessmentId, props.pc.pc_id, picked.value)
    blind.value = picked.value
    if (r.queued) {
      queued.value = true
    } else {
      finalScore.value = r.score.final_score
      reveal.value = r.ai
      saved.value = !r.ai.reason_required
    }
    emit('scored')
  } catch (e) {
    error.value = String(e)
  } finally {
    busy.value = false
  }
}

async function saveReview() {
  busy.value = true
  error.value = ''
  try {
    await reviseScore(props.assessmentId, props.pc.pc_id, {
      final_score: finalScore.value ?? undefined,
      reason_code: reason.value || undefined,
      note: note.value || undefined,
    })
    saved.value = true
    emit('scored')
  } catch (e) {
    error.value = String(e)
  } finally {
    busy.value = false
  }
}

// Full mode analyses photos on a worker, so the AI opinion can arrive a moment after the lock.
const POLL_MS = 1500
const POLL_MAX = 40
let pollTimer: ReturnType<typeof setTimeout> | undefined
const polls = ref(0)
async function recheckAi() {
  try {
    const r = await refreshAi(props.assessmentId, props.pc.pc_id)
    reveal.value = r.ai
    if (r.ai.status === 'ok') {
      finalScore.value = r.score.final_score
      saved.value = !r.ai.reason_required
      emit('scored')
    }
  } catch {
    // offline or transient: the next poll (or a manual re-check) tries again
  }
}
function schedulePoll() {
  clearTimeout(pollTimer)
  if (reveal.value?.status !== 'pending' || polls.value >= POLL_MAX) return
  pollTimer = setTimeout(async () => {
    polls.value += 1
    await recheckAi()
    schedulePoll()
  }, POLL_MS)
}
watch(() => reveal.value?.status, schedulePoll, { immediate: true })
onBeforeUnmount(() => clearTimeout(pollTimer))

const levelText = (lvl: number) => {
  const d = props.rubric.scale.find((s) => s.level === lvl)
  return d ? (locale.value === 'hi' ? d.hi : d.en) : ''
}
</script>

<template>
  <div class="rounded-xl border border-navy-100 p-3" :data-testid="`scorer-${pc.pc_id}`" :data-state="reveal ? 'revealed' : queued ? 'queued' : 'blind'">
    <div class="flex flex-wrap items-start gap-2">
      <span class="chip mt-0.5 bg-navy-900 text-white">{{ pc.code }}</span>
      <p class="min-w-0 flex-1 text-sm">{{ pc.text }}</p>
      <span class="chip bg-navy-100">{{ ROUTE_ICON[pc.route] }} {{ t(`route.${pc.route}`) }}</span>
      <span v-if="pc.locked" class="chip bg-saffron-100">🔒</span>
    </div>

    <!-- 1) blind score -->
    <div v-if="blind === null" class="mt-2">
      <div class="grid grid-cols-4 gap-1.5" role="radiogroup">
        <button
          v-for="lvl in [0, 1, 2, 3]"
          :key="lvl"
          class="min-h-12 rounded-lg border-2 text-lg font-bold"
          :class="picked === lvl ? 'border-navy-900 bg-navy-900 text-white' : 'border-navy-100 bg-white'"
          :title="levelText(lvl)"
          :aria-pressed="picked === lvl"
          :data-testid="`pick-${pc.pc_id}-${lvl}`"
          @click="picked = lvl"
        >
          {{ lvl }}
        </button>
      </div>
      <p v-if="picked !== null" class="mt-1 text-xs text-navy-700">{{ levelText(picked) }}</p>
      <div class="mt-2 flex flex-wrap gap-2">
        <button class="btn-primary min-h-10 flex-1" :disabled="picked === null || busy" :data-testid="`lock-${pc.pc_id}`" @click="lockBlind">
          🔒 {{ t('scoring.lockBlind') }}
        </button>
        <button class="chip bg-white px-3 text-navy-900 underline" @click="showRubric = !showRubric">{{ t('assessor.rubric') }}</button>
      </div>
      <p class="mt-1 text-[11px] text-navy-700">{{ t('scoring.blindNote') }}</p>
    </div>

    <!-- 2) queued offline -->
    <div v-else-if="queued" class="mt-2 rounded-lg bg-saffron-100 p-2 text-sm" :data-testid="`queued-${pc.pc_id}`">
      {{ t('scoring.yourBlind') }}: <b>{{ blind }}</b> · {{ t('scoring.queued') }}
    </div>

    <!-- 3) reveal -->
    <div v-else-if="reveal" class="reveal mt-2 rounded-lg border-2 p-2 text-sm" :class="gapClass" :data-testid="`reveal-${pc.pc_id}`">
      <div class="flex flex-wrap items-center gap-2">
        <span>{{ t('scoring.yourBlind') }}: <b :data-testid="`blind-${pc.pc_id}`">{{ blind }}</b></span>
        <template v-if="reveal.status === 'ok'">
          <span>· {{ t('scoring.aiSays') }}: <b :data-testid="`ai-level-${pc.pc_id}`">{{ reveal.level }}</b></span>
          <span class="text-xs">({{ Math.round((reveal.confidence ?? 0) * 100) }}%)</span>
          <span v-if="reveal.gap" class="chip bg-white" :data-testid="`gap-${pc.pc_id}`">{{ t('scoring.gap') }} {{ reveal.gap > 0 ? '+' : '' }}{{ reveal.gap }}</span>
        </template>
      </div>
      <p v-if="reveal.status === 'pending'" class="mt-1 text-xs" :data-testid="`ai-pending-${pc.pc_id}`">⏳ {{ t('scoring.aiPending') }}</p>
      <p v-else class="mt-1 text-xs">{{ reveal.explanation }}</p>
      <button
        v-if="reveal.status === 'awaiting_photo' || (reveal.status === 'pending' && polls >= POLL_MAX)"
        class="chip mt-1 bg-white px-3 text-navy-900 underline"
        :data-testid="`ai-recheck-${pc.pc_id}`"
        @click="recheckAi"
      >
        {{ t('scoring.recheck') }}
      </button>
      <p v-if="reveal.model_label" class="text-[10px] text-navy-700">{{ reveal.model_label }}</p>

      <div v-if="reveal.reason_required" class="mt-2 grid gap-2 rounded-lg bg-white p-2" :data-testid="`reason-box-${pc.pc_id}`">
        <span class="text-xs font-semibold">{{ t('scoring.reasonRequired') }}</span>
        <select v-model="reason" class="input min-h-10" :disabled="saved" :data-testid="`reason-${pc.pc_id}`">
          <option value="" disabled>{{ t('scoring.pickReason') }}</option>
          <option v-for="r in REASON_CODES" :key="r" :value="r">{{ t(`scoring.reason.${r}`) }}</option>
        </select>
        <input v-if="reason === 'other'" v-model="note" class="input min-h-10" :disabled="saved" :placeholder="t('scoring.note')" />
        <div class="flex flex-wrap items-center gap-1 text-xs">
          <span>{{ t('scoring.finalScore') }}:</span>
          <button
            v-for="lvl in [0, 1, 2, 3]"
            :key="lvl"
            class="h-8 w-8 rounded-md border-2 font-bold"
            :class="finalScore === lvl ? 'border-navy-900 bg-navy-900 text-white' : 'border-navy-100 bg-white'"
            :disabled="saved"
            :data-testid="`final-${pc.pc_id}-${lvl}`"
            @click="finalScore = lvl"
          >
            {{ lvl }}
          </button>
        </div>
        <button v-if="!saved" class="btn-green min-h-10" :disabled="!reason || busy || (reason === 'other' && !note)" :data-testid="`save-reason-${pc.pc_id}`" @click="saveReview">
          {{ t('common.save') }}
        </button>
        <p v-else class="text-xs font-semibold text-green-india-700" :data-testid="`reason-saved-${pc.pc_id}`">✓ {{ t('scoring.saved') }}</p>
        <p class="text-[11px] text-navy-700">{{ t('scoring.keptInLedger') }}</p>
      </div>
    </div>

    <RubricAnchors v-if="showRubric && blind === null" class="mt-2" :rubric="rubric" :signal="pc.ai_signal" />
    <p v-if="error" class="mt-1 text-xs text-red-700" role="alert">{{ error }}</p>
  </div>
</template>

<style scoped>
.reveal {
  animation: fade-in 0.6s ease-out;
}
@keyframes fade-in {
  from {
    opacity: 0;
    transform: translateY(-4px);
  }
  to {
    opacity: 1;
    transform: none;
  }
}
</style>
