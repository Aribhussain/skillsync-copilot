<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'

import type { ConsentNotice } from '../../lib/mapper/types'
import { fetchNotice, giveConsent } from '../../lib/worker'
import { useAuthStore } from '../../stores/auth'

const { t, locale } = useI18n()
const router = useRouter()
const auth = useAuthStore()

const notice = ref<ConsentNotice | null>(null)
const checked = ref<Record<string, boolean>>({ rpl_assessment: false, evidence_capture: false, voice_processing: false })
const error = ref('')
const busy = ref(false)
const lang = computed<'en' | 'hi'>(() => (locale.value === 'hi' ? 'hi' : 'en'))

async function load() {
  error.value = ''
  try {
    notice.value = await fetchNotice(lang.value)
  } catch (e) {
    error.value = String(e)
  }
}
onMounted(load)
watch(lang, load)

async function submit() {
  if (!checked.value.rpl_assessment || !notice.value) {
    error.value = t('consent.cannotContinue')
    return
  }
  busy.value = true
  try {
    const purposes = Object.entries(checked.value).filter(([, v]) => v).map(([k]) => k)
    await giveConsent(auth.user!.username, purposes, lang.value, notice.value.sha256)
    await router.push('/worker/declare')
  } catch (e) {
    error.value = String(e)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <section class="card mx-auto max-w-2xl" data-testid="consent-view">
    <h1 class="mb-1 text-2xl font-bold">{{ notice?.title ?? t('consent.title') }}</h1>
    <p class="mb-4 text-xs text-navy-700">v{{ notice?.version }} · DPDP Act 2023</p>
    <div v-if="notice" class="grid gap-3">
      <label
        v-for="item in notice.items"
        :key="item.purpose"
        class="flex cursor-pointer gap-3 rounded-xl border-2 p-3"
        :class="checked[item.purpose] ? 'border-green-india-600 bg-green-india-100/40' : 'border-navy-100'"
      >
        <input
          v-model="checked[item.purpose]"
          type="checkbox"
          class="mt-1 h-6 w-6 shrink-0 accent-green-india-600"
          :data-testid="`consent-${item.purpose}`"
        />
        <span>
          <span class="chip mb-1" :class="item.purpose === 'rpl_assessment' ? 'bg-saffron-100' : 'bg-navy-100'">
            {{ item.purpose === 'rpl_assessment' ? t('consent.required') : t('consent.optional') }}
          </span>
          <span class="block text-base leading-relaxed">{{ item.text }}</span>
        </span>
      </label>
      <p class="rounded-xl bg-navy-50 p-3 text-sm">{{ notice.rights }}</p>
    </div>
    <p v-else class="text-navy-700">{{ t('common.loading') }}</p>
    <p v-if="error" class="mt-3 rounded-lg bg-saffron-100 p-2 text-sm" role="alert">{{ error }}</p>
    <button class="btn-green mt-4 w-full" :disabled="busy || !notice" data-testid="consent-submit" @click="submit">
      {{ t('consent.agree') }}
    </button>
  </section>
</template>
