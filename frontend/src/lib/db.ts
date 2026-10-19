/** Local-first storage (IndexedDB via Dexie). Everything is written here first,
 *  then queued in the outbox; the sync engine pushes it when online. */
import Dexie, { type Table } from 'dexie'

export type OutboxStatus = 'pending' | 'sending' | 'failed' | 'done'

export interface OutboxItem {
  id?: number
  kind: string // e.g. 'declaration', 'evidence', 'score'
  idempotencyKey: string
  payload: Record<string, unknown>
  status: OutboxStatus
  attempts: number
  nextAttemptAt: number
  lastError?: string
  createdAt: number
}

export interface KeyValue {
  key: string
  value: unknown
}

export class SkillSyncDB extends Dexie {
  outbox!: Table<OutboxItem, number>
  kv!: Table<KeyValue, string>

  constructor(name = 'skillsync') {
    super(name)
    this.version(1).stores({
      outbox: '++id, kind, status, idempotencyKey, nextAttemptAt',
      kv: 'key',
    })
  }
}

export const db = new SkillSyncDB()

export async function pendingOutboxCount(): Promise<number> {
  return db.outbox.where('status').anyOf('pending', 'sending', 'failed').count()
}
