<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'

import { ICON_CARDS } from '../../lib/cards'
import { speech, type SpeechLang } from '../../lib/speech'
import { submitDeclaration } from '../../lib/worker'
import { useAuthStore } from '../../stores/auth'

const { t, locale } = useI18n()
const router = useRouter()
const auth = useAuthStore()

const speechLang = ref<SpeechLang>(locale.value === 'hi' ? 'hi-IN' : 'en-IN')
const narrative = ref('')
const interim = ref('')
const listening = ref(false)
const usedVoice = ref(false)
const selected = ref<string[]>([])
const error = ref('')
const busy = ref(false)
const voiceAvailable = speech.available()
let baseText = ''

const canSubmit = computed(() => narrative.value.trim().length > 0 || selected.value.length > 0)

function toggleMic() {
  error.value = ''
  if (listening.value) {
    speech.stop()
    return
  }
  baseText = narrative.value ? `${narrative.value.trim()} ` : ''
  listening.value = true
  usedVoice.value = true
  speech.start(speechLang.value, {
    onText: (finalText, partial) => {
      narrative.value = baseText + finalText
      interim.value = partial
    },
    onError: (code) => {
      error.value = t('declare.micError', { code })
      listening.value = false
    },
    onEnd: () => {
      listening.value = false
      interim.value = ''
    },
  })
}

function toggleCard(id: string) {
  selected.value = selected.value.includes(id) ? selected.value.filter((c) => c !== id) : [...selected.value, id]
}

async function submit() {
  if (!canSubmit.value) {
    error.value = t('declare.needInput')
    return
  }
  busy.value = true
  error.value = ''
  try {
    const d = await submitDeclaration({
      username: auth.user!.username,
      narrative: narrative.value.trim(),
      language: speechLang.value === 'hi-IN' ? 'hi' : 'en',
      inputMode: usedVoice.value ? 'voice' : narrative.value.trim() ? 'typed' : 'cards',
      cards: selected.value,
    })
    await router.push(`/worker/results/${d.clientId}`)
  } catch (e) {
    error.value = String(e)
  } finally {
    busy.value = false
  }
}

onBeforeUnmount(() => speech.stop())
</script>

<template>
  <div class="mx-auto grid max-w-3xl gap-4" data-testid="declare-view">
    <section class="card">
      <h1 class="text-2xl font-bold">{{ t('declare.title') }}</h1>
      <p class="mb-4 text-navy-700">{{ t('declare.lead') }}</p>

      <div class="mb-3 flex items-center gap-2 text-sm">
        <span class="font-semibold">{{ t('declare.speakLang') }}:</span>
        <button
          v-for="l in (['hi-IN', 'en-IN'] as const)"
          :key="l"
          class="chip min-h-9 px-3"
          :class="speechLang === l ? 'bg-navy-900 text-white' : 'bg-navy-100'"
          @click="speechLang = l"
        >
          {{ l === 'hi-IN' ? 'हिंदी' : 'English' }}
        </button>
      </div>

      <div class="flex flex-col items-center gap-2 py-2">
        <button
          class="flex h-28 w-28 items-center justify-center rounded-full text-5xl shadow-lg transition focus-visible:ring-4 focus-visible:ring-saffron-500/60 disabled:opacity-40"
          :class="listening ? 'animate-pulse bg-saffron-500' : 'bg-navy-900 text-white'"
          :disabled="!voiceAvailable"
          :aria-label="listening ? t('declare.listening') : t('declare.mic')"
          data-testid="mic-button"
          @click="toggleMic"
        >
          🎤
        </button>
        <span class="text-sm font-semibold">{{ listening ? t('declare.listening') : t('declare.mic') }}</span>
        <p v-if="!voiceAvailable" class="rounded-lg bg-saffron-100 p-2 text-center text-sm" data-testid="voice-unavailable">
          {{ t('declare.voiceUnavailable') }}
        </p>
      </div>

      <label class="mt-2 grid gap-1 text-sm font-semibold">
        {{ t('declare.typeHere') }}
        <textarea
          v-model="narrative"
          rows="4"
          class="input py-3 text-base leading-relaxed"
          data-testid="narrative-input"
          :placeholder="'Main 6 saal se fabrication shop mein kaam karta hoon…'"
        />
      </label>
      <p v-if="interim" class="mt-1 text-sm italic text-navy-700">{{ interim }}</p>
    </section>

    <section class="card">
      <h2 class="mb-3 text-lg font-bold">{{ t('declare.cardsTitle') }}</h2>
      <div class="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <button
          v-for="c in ICON_CARDS"
          :key="c.id"
          class="flex min-h-20 flex-col items-center justify-center gap-1 rounded-xl border-2 p-2 text-center"
          :class="selected.includes(c.id) ? 'border-green-india-600 bg-green-india-100' : 'border-navy-100 bg-white'"
          :aria-pressed="selected.includes(c.id)"
          :data-testid="`card-${c.id}`"
          @click="toggleCard(c.id)"
        >
          <span class="text-3xl" aria-hidden="true">{{ c.icon }}</span>
          <span class="text-sm font-semibold leading-tight">{{ locale === 'hi' ? c.hi : c.en }}</span>
        </button>
      </div>
    </section>

    <p v-if="error" class="rounded-lg bg-saffron-100 p-2 text-sm" role="alert">{{ error }}</p>
    <button class="btn-saffron w-full text-lg" :disabled="busy || !canSubmit" data-testid="declare-submit" @click="submit">
      {{ t('declare.submit') }}
    </button>
  </div>
</template>
