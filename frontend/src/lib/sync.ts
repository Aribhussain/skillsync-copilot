/**
 * Outbox sync engine.
 *  - Items are processed in creation order (so a declaration syncs before the
 *    assessment request that depends on it).
 *  - Every request carries an idempotency key (client_id) and the server deduplicates,
 *    so retries are always safe.
 *  - Network failure: stop and wait for the next trigger (online event / timer).
 *  - 5xx, 404 (dependency not synced yet), 408/429: exponential backoff, retried.
 *  - 401: stop (the user has to log in again). Other 4xx: marked failed (needs attention).
 */
import { ApiError, NetworkError } from './api'
import { db, type OutboxItem } from './db'

export type Handler = (item: OutboxItem) => Promise<void>

const handlers = new Map<string, Handler>()
const listeners = new Set<() => void>()
let flushing: Promise<FlushResult> | null = null

export interface FlushResult {
  sent: number
  failed: number
  remaining: number
  stoppedBy?: 'offline' | 'auth'
}

export function registerHandler(kind: string, handler: Handler): void {
  handlers.set(kind, handler)
}

/** Called after every flush and enqueue (e.g. to refresh the outbox counter or a view). */
export function onSyncChange(fn: () => void): () => void {
  listeners.add(fn)
  return () => listeners.delete(fn)
}

function notify() {
  for (const fn of listeners) fn()
}

export const MAX_BACKOFF_MS = 5 * 60_000

export function backoffMs(attempts: number): number {
  const base = Math.min(MAX_BACKOFF_MS, 2000 * 2 ** Math.max(0, attempts - 1))
  return Math.round(base * (0.8 + Math.random() * 0.4))
}

export async function enqueue(kind: string, payload: Record<string, unknown>, idempotencyKey: string): Promise<number> {
  const existing = await db.outbox.where('idempotencyKey').equals(idempotencyKey).first()
  if (existing?.id) return existing.id
  const id = await db.outbox.add({
    kind,
    idempotencyKey,
    payload,
    status: 'pending',
    attempts: 0,
    nextAttemptAt: 0,
    createdAt: Date.now(),
  })
  notify()
  return id
}

function retryable(err: unknown): boolean {
  if (err instanceof ApiError) return err.status >= 500 || [404, 408, 425, 429].includes(err.status)
  return false
}

async function runFlush(): Promise<FlushResult> {
  const result: FlushResult = { sent: 0, failed: 0, remaining: 0 }
  const attempted = new Set<number>()
  // Keep going while new due items appear (e.g. enqueued while this run was in flight).
  for (;;) {
    const due = (await db.outbox.where('status').anyOf('pending', 'sending').toArray())
      .filter((i) => !attempted.has(i.id!) && i.nextAttemptAt <= Date.now())
      .sort((a, b) => a.id! - b.id!)
    if (!due.length || result.stoppedBy) break
    await processBatch(due, attempted, result)
  }
  result.remaining = await db.outbox.where('status').anyOf('pending', 'sending').count()
  return result
}

async function processBatch(items: OutboxItem[], attempted: Set<number>, result: FlushResult): Promise<void> {
  for (const item of items) {
    attempted.add(item.id!)
    const handler = handlers.get(item.kind)
    if (!handler) continue
    await db.outbox.update(item.id!, { status: 'sending' })
    try {
      await handler(item)
      await db.outbox.update(item.id!, { status: 'done', lastError: undefined })
      result.sent++
    } catch (err) {
      const attempts = item.attempts + 1
      if (err instanceof NetworkError) {
        await db.outbox.update(item.id!, { status: 'pending' })
        result.stoppedBy = 'offline'
        break
      }
      if (err instanceof ApiError && err.status === 401) {
        await db.outbox.update(item.id!, { status: 'pending' })
        result.stoppedBy = 'auth'
        break
      }
      if (retryable(err)) {
        await db.outbox.update(item.id!, {
          status: 'pending',
          attempts,
          nextAttemptAt: Date.now() + backoffMs(attempts),
          lastError: String(err),
        })
      } else {
        await db.outbox.update(item.id!, { status: 'failed', attempts, lastError: String(err) })
        result.failed++
      }
    }
  }
}

/** Process due outbox items. Concurrent calls share one run. */
export function flush(): Promise<FlushResult> {
  if (!flushing) {
    flushing = runFlush().finally(() => {
      flushing = null
      notify()
    })
  }
  return flushing
}

/** Make items in backoff due now (used when connectivity returns). */
export async function wakeAll(): Promise<void> {
  await db.outbox.where('status').equals('pending').modify({ nextAttemptAt: 0 })
}
