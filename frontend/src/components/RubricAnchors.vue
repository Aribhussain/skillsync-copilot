<script setup lang="ts">
import { useI18n } from 'vue-i18n'

import type { Rubric } from '../lib/assessor'

defineProps<{ rubric: Rubric; signal: string | null }>()
const { t, locale } = useI18n()
</script>

<template>
  <div class="rounded-xl bg-navy-50 p-3 text-sm" data-testid="rubric-anchors">
    <div class="mb-2 font-semibold">{{ t('assessor.rubricTitle') }}</div>
    <ol class="grid gap-1">
      <li v-for="lvl in rubric.scale" :key="lvl.level" class="flex gap-2">
        <span class="chip h-6 min-w-6 justify-center bg-navy-900 text-white">{{ lvl.level }}</span>
        <span>{{ locale === 'hi' ? lvl.hi : lvl.en }}</span>
      </li>
    </ol>
    <div v-if="signal && rubric.examples[signal]" class="mt-3 grid grid-cols-2 gap-2">
      <figure>
        <img :src="rubric.examples[signal].good" alt="" class="w-full rounded-lg border-2 border-green-india-600" loading="lazy" />
        <figcaption class="mt-1 text-xs font-semibold text-green-india-700">✓ {{ t('assessor.anchorGood') }}</figcaption>
      </figure>
      <figure>
        <img :src="rubric.examples[signal].poor" alt="" class="w-full rounded-lg border-2 border-saffron-500" loading="lazy" />
        <figcaption class="mt-1 text-xs font-semibold">✗ {{ rubric.examples[signal].poor_label }}</figcaption>
      </figure>
      <p class="col-span-2 text-xs text-navy-700">{{ rubric.note }}</p>
    </div>
  </div>
</template>
