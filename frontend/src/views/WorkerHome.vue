<script setup lang="ts">
import { useI18n } from 'vue-i18n'

import { useAuthStore } from '../stores/auth'

const { t } = useI18n()
const auth = useAuthStore()
</script>

<template>
  <section class="card">
    <h1 class="text-2xl font-bold">{{ t('home.workerTitle', { name: auth.user?.full_name ?? '' }) }}</h1>
    <p class="text-navy-700">{{ t('home.workerLead') }}</p>
    <p class="mt-4 text-sm text-navy-700">{{ t('home.comingSoon') }}</p>
  </section>
</template>
