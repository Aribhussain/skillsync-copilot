<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'

import { api, ApiError, NetworkError } from '../lib/api'
import { homeFor, useAuthStore } from '../stores/auth'

interface DemoAccount {
  username: string
  full_name: string
  role: string
  password: string
}

const { t } = useI18n()
const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

const username = ref('')
const password = ref('')
const error = ref('')
const busy = ref(false)
const demo = ref<DemoAccount[]>([])

onMounted(async () => {
  try {
    demo.value = await api<DemoAccount[]>('/auth/demo-accounts')
  } catch {
    demo.value = []
  }
})

function pick(acc: DemoAccount) {
  username.value = acc.username
  password.value = acc.password
}

async function submit() {
  error.value = ''
  busy.value = true
  try {
    const user = await auth.login(username.value.trim(), password.value)
    const next = typeof route.query.next === 'string' ? route.query.next : homeFor[user.role]
    await router.push(next)
  } catch (e) {
    error.value = e instanceof NetworkError ? t('login.offline') : e instanceof ApiError ? t('login.failed') : String(e)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="mx-auto grid max-w-3xl gap-4 md:grid-cols-2">
    <section class="card">
      <h1 class="mb-1 text-2xl font-bold">{{ t('login.title') }}</h1>
      <p class="mb-4 text-sm text-navy-700">{{ t('app.tagline') }}</p>
      <form class="grid gap-3" @submit.prevent="submit">
        <label class="grid gap-1 text-sm font-semibold">
          {{ t('login.username') }}
          <input v-model="username" class="input" name="username" autocomplete="username" required />
        </label>
        <label class="grid gap-1 text-sm font-semibold">
          {{ t('login.password') }}
          <input
            v-model="password"
            class="input"
            name="password"
            type="password"
            autocomplete="current-password"
            required
          />
        </label>
        <p v-if="error" class="rounded-lg bg-saffron-100 p-2 text-sm" role="alert" data-testid="login-error">
          {{ error }}
        </p>
        <button class="btn-primary" type="submit" :disabled="busy" data-testid="login-submit">
          {{ t('login.submit') }}
        </button>
      </form>
    </section>
    <section v-if="demo.length" class="card" data-testid="demo-accounts">
      <h2 class="text-lg font-bold">{{ t('login.demoAccounts') }}</h2>
      <p class="mb-3 text-xs text-navy-700">{{ t('login.demoHint') }}</p>
      <div class="flex flex-wrap gap-2">
        <button
          v-for="acc in demo"
          :key="acc.username"
          type="button"
          class="flex min-h-12 flex-col items-start rounded-xl border-2 border-navy-100 bg-navy-50 px-3 py-1.5 text-left hover:border-saffron-500"
          :data-testid="`demo-${acc.username}`"
          @click="pick(acc)"
        >
          <span class="font-mono text-sm font-bold">{{ acc.username }}</span>
          <span class="text-xs text-navy-700">{{ t(`roles.${acc.role}`) }} · {{ acc.password }}</span>
        </button>
      </div>
    </section>
  </div>
</template>
