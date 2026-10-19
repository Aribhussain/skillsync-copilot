import { beforeEach, describe, expect, it } from 'vitest'

import { ApiError, NetworkError } from './api'
import { db } from './db'
import { enqueue, flush, registerHandler } from './sync'

beforeEach(async () => {
  await db.outbox.clear()
})

describe('outbox sync engine', () => {
  it('processes items in creation order', async () => {
    const seen: string[] = []
    registerHandler('t-order', async (item) => {
      seen.push(String(item.payload.n))
    })
    await enqueue('t-order', { n: 'a' }, 'k-a')
    await enqueue('t-order', { n: 'b' }, 'k-b')
    await enqueue('t-order', { n: 'c' }, 'k-c')
    const r = await flush()
    expect(seen).toEqual(['a', 'b', 'c'])
    expect(r.sent).toBe(3)
    expect(r.remaining).toBe(0)
  })

  it('enqueue is idempotent on the idempotency key', async () => {
    const a = await enqueue('t-idem', {}, 'same-key')
    const b = await enqueue('t-idem', {}, 'same-key')
    expect(a).toBe(b)
    expect(await db.outbox.count()).toBe(1)
  })

  it('stops on network failure and keeps items pending', async () => {
    registerHandler('t-offline', async () => {
      throw new NetworkError('Failed to fetch')
    })
    await enqueue('t-offline', {}, 'k-off-1')
    await enqueue('t-offline', {}, 'k-off-2')
    const r = await flush()
    expect(r.stoppedBy).toBe('offline')
    expect(r.remaining).toBe(2)
    const items = await db.outbox.toArray()
    expect(items.every((i) => i.status === 'pending' && i.attempts === 0)).toBe(true)
  })

  it('backs off on 404 (dependency not synced yet) and retries later', async () => {
    let calls = 0
    registerHandler('t-404', async () => {
      calls++
      if (calls === 1) throw new ApiError(404, 'Declaration not found')
    })
    await enqueue('t-404', {}, 'k-404')
    await flush()
    let item = (await db.outbox.toArray())[0]
    expect(item.status).toBe('pending')
    expect(item.attempts).toBe(1)
    expect(item.nextAttemptAt).toBeGreaterThan(Date.now())
    await flush() // still in backoff: not retried yet
    expect(calls).toBe(1)
    await db.outbox.update(item.id!, { nextAttemptAt: 0 })
    await flush()
    item = (await db.outbox.toArray())[0]
    expect(item.status).toBe('done')
  })

  it('marks a 422 as permanently failed', async () => {
    registerHandler('t-422', async () => {
      throw new ApiError(422, 'Unknown QP')
    })
    await enqueue('t-422', {}, 'k-422')
    const r = await flush()
    expect(r.failed).toBe(1)
    expect((await db.outbox.toArray())[0].status).toBe('failed')
  })
})
