import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { db } from './db'
import { pendingScore, refreshAi, submitBlindScore } from './scoring'
import { flush } from './sync'

beforeEach(async () => {
  await db.outbox.clear()
  await db.kv.clear()
})
afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals() // stubbed fetch must not leak into the next test
})

describe('blind score client', () => {
  it('online: returns the server reveal', async () => {
    const reveal = { status: 'ok', level: 1, confidence: 0.9, explanation: 'pores', gap: 2, reason_required: true }
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ score: { id: 1, blind_score: 3 }, ai: reveal }), { status: 201 })))
    const r = await submitBlindScore(5, 'ASC-N3125.PC1', 3)
    expect(r.queued).toBe(false)
    if (!r.queued) expect(r.ai.reason_required).toBe(true)
  })

  it('offline: queues the blind score (no reveal) and sends it on reconnect', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => Promise.reject(new TypeError('Failed to fetch'))))
    const r = await submitBlindScore(5, 'ASC-N3125.PC1', 2)
    expect(r.queued).toBe(true)
    expect(await pendingScore(5, 'ASC-N3125.PC1')).toBe(2)

    const bodies: unknown[] = []
    vi.stubGlobal(
      'fetch',
      vi.fn(async (_url: string, init?: RequestInit) => {
        if (init?.body) bodies.push(JSON.parse(String(init.body)))
        return new Response('[]', { status: 201 })
      }),
    )
    await flush()
    expect(bodies[0]).toMatchObject({ pc_id: 'ASC-N3125.PC1', score: 2 })
    expect(await pendingScore(5, 'ASC-N3125.PC1')).toBeUndefined()
  })

  it('refreshAi: POSTs to the per-PC ai-refresh route (PC id URL-encoded)', async () => {
    const calls: [string, string | undefined][] = []
    const reveal = { status: 'ok', level: 1, confidence: 0.8, explanation: 'pores', gap: 2, reason_required: true }
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string, init?: RequestInit) => {
        calls.push([url, init?.method])
        return new Response(JSON.stringify({ score: { id: 1, blind_score: 3, final_score: 3 }, ai: reveal }), { status: 200 })
      }),
    )
    const r = await refreshAi(7, 'ASC/N3125.PC1')
    expect(r.ai.status).toBe('ok')
    expect(calls[0][0].endsWith('/assessments/7/scores/ASC%2FN3125.PC1/ai-refresh')).toBe(true)
    expect(calls[0][1]).toBe('POST')
  })
})
