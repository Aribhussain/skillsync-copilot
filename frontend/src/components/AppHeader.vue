<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'

import { setLocale } from '../i18n'
import { useAuthStore } from '../stores/auth'
import NetworkStatus from './NetworkStatus.vue'

const auth = useAuthStore()
const router = useRouter()
const { t, locale } = useI18n()

function toggleLocale() {
  setLocale(locale.value === 'hi' ? 'en' : 'hi')
}

async function logout() {
  auth.logout()
  await router.push('/login')
}
</script>

<template>
  <header class="sticky top-0 z-20 border-b-4 border-saffron-500 bg-navy-900 text-white">
    <div class="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-2 px-3 py-2 sm:px-4">
      <RouterLink to="/" class="flex items-center gap-2 font-bold">
        <img src="/favicon.svg" alt="" class="h-8 w-8" />
        <span class="text-base sm:text-lg">{{ t('app.name') }}</span>
      </RouterLink>
      <div class="flex flex-wrap items-center gap-2">
        <NetworkStatus />
        <button
          class="chip min-h-9 bg-white/10 px-3 text-white hover:bg-white/20"
          data-testid="lang-toggle"
          @click="toggleLocale"
        >
          {{ t('app.language') }}
        </button>
        <template v-if="auth.user">
          <span class="hidden text-sm text-navy-100 sm:inline" data-testid="current-user">
            {{ auth.user.full_name }} · {{ t(`roles.${auth.user.role}`) }}
          </span>
          <button class="chip min-h-9 bg-white px-3 text-navy-900" data-testid="logout" @click="logout">
            {{ t('app.logout') }}
          </button>
        </template>
      </div>
    </div>
  </header>
</template>
