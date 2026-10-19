import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { api, getToken, setToken } from '../lib/api'

export type Role = 'worker' | 'assessor' | 'qa_lead' | 'admin'

export interface User {
  id: number
  username: string
  full_name: string
  role: Role
  centre: string | null
  preferred_language: string
}

const USER_KEY = 'skillsync.user'

function loadUser(): User | null {
  try {
    const raw = localStorage.getItem(USER_KEY)
    return raw ? (JSON.parse(raw) as User) : null
  } catch {
    return null
  }
}

export const homeFor: Record<Role, string> = {
  worker: '/worker',
  assessor: '/assessor',
  qa_lead: '/qa',
  admin: '/qa',
}

export const useAuthStore = defineStore('auth', () => {
  // The session survives offline restarts: token + user are cached locally.
  const token = ref<string | null>(getToken())
  const user = ref<User | null>(loadUser())
  const isAuthenticated = computed(() => !!token.value && !!user.value)

  async function login(username: string, password: string): Promise<User> {
    const res = await api<{ access_token: string; user: User }>('/auth/login', {
      body: { username, password },
    })
    token.value = res.access_token
    user.value = res.user
    setToken(res.access_token)
    localStorage.setItem(USER_KEY, JSON.stringify(res.user))
    return res.user
  }

  function logout(): void {
    token.value = null
    user.value = null
    setToken(null)
    localStorage.removeItem(USER_KEY)
  }

  return { token, user, isAuthenticated, login, logout }
})
