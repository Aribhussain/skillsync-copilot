import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { db } from '../lib/db'
import { useAuthStore } from './auth'
import { useNetworkStore } from './network'

beforeEach(() => {
  setActivePinia(createPinia())
  localStorage.clear()
})
afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals() // stubbed fetch must not leak into the next test
})

describe('auth store', () => {
  it('logs in, persists the session and logs out', async () => {
    const user = { id: 1, username: 'worker1', full_name: 'Ramesh', role: 'worker', centre: null, preferred_language: 'hi' }
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response(JSON.stringify({ access_token: 'tok', user }), { status: 200 })),
    )
    const auth = useAuthStore()
    await auth.login('worker1', 'worker123')
    expect(auth.isAuthenticated).toBe(true)
    expect(localStorage.getItem('skillsync.token')).toBe('tok')

    // a fresh store (e.g. after an offline restart) restores the session
    setActivePinia(createPinia())
    expect(useAuthStore().user?.username).toBe('worker1')

    useAuthStore().logout()
    expect(localStorage.getItem('skillsync.token')).toBeNull()
  })

  it('surfaces wrong credentials as an ApiError', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ detail: 'bad' }), { status: 401 })))
    await expect(useAuthStore().login('x', 'y')).rejects.toMatchObject({ status: 401 })
  })
})

describe('network store', () => {
  it('is offline when /health cannot be reached', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => Promise.reject(new TypeError('Failed to fetch'))))
    const net = useNetworkStore()
    await net.checkServer()
    expect(net.online).toBe(false)
  })

  it('counts pending outbox items', async () => {
    await db.outbox.clear()
    await db.outbox.add({
      kind: 'declaration',
      idempotencyKey: 'k1',
      payload: {},
      status: 'pending',
      attempts: 0,
      nextAttemptAt: 0,
      createdAt: Date.now(),
    })
    const net = useNetworkStore()
    await net.refreshOutbox()
    expect(net.outboxCount).toBe(1)
  })
})
