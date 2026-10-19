/** Local-first storage (IndexedDB via Dexie). Everything is written here first,
 *  then queued in the outbox; the sync engine pushes it when online. */
import Dexie, { type Table } from 'dexie'

import type { MappingResult } from './mapper/types'

export type OutboxStatus = 'pending' | 'sending' | 'failed' | 'done'

export interface OutboxItem {
  id?: number
  kind: string // e.g. 'consent', 'declaration', 'assessment_request', 'evidence', 'score'
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

export type DeclarationStatus = 'local' | 'submitted' | 'mapped' | 'confirmed'

export interface LocalDeclaration {
  clientId: string
  username: string
  narrative: string
  language: string
  inputMode: 'voice' | 'typed' | 'cards'
  cards: string[]
  createdAt: number
  status: DeclarationStatus
  serverId?: number
  provisional?: MappingResult // from on-device mapper-lite
  serverMapping?: MappingResult // replaces the provisional result once online
  confirmedQpId?: string
  claimedPcIds?: string[]
  assessmentClientId?: string
  assessmentId?: number
}

export class SkillSyncDB extends Dexie {
  outbox!: Table<OutboxItem, number>
  kv!: Table<KeyValue, string>
  declarations!: Table<LocalDeclaration, string>

  constructor(name = 'skillsync') {
    super(name)
    this.version(1).stores({
      outbox: '++id, kind, status, idempotencyKey, nextAttemptAt',
      kv: 'key',
    })
    this.version(2).stores({
      declarations: 'clientId, username, status, createdAt',
    })
  }
}

export const db = new SkillSyncDB()

export async function pendingOutboxCount(): Promise<number> {
  return db.outbox.where('status').anyOf('pending', 'sending', 'failed').count()
}

export function newClientId(prefix: string): string {
  const rnd = crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(36).slice(2)}`
  return `${prefix}-${rnd}`
}
