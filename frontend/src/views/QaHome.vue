<script setup lang="ts">
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
</script>

<template>
  <section class="card">
    <h1 class="text-2xl font-bold">{{ t('home.qaTitle') }}</h1>
    <p class="mt-2 text-sm text-navy-700">{{ t('home.comingSoon') }}</p>
  </section>
</template>
