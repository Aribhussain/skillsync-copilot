/**
 * Worker-side flow: consent -> declaration -> mapping -> confirm (assessment request).
 * Local-first: every action is saved in IndexedDB, mapped instantly on-device by
 * mapper-lite, and queued in the outbox. The sync engine pushes it to the server, and the
 * server's mapping replaces the provisional one when it arrives.
 */
import { api } from './api'
import { cardText } from './cards'
import { db, type LocalDeclaration, newClientId } from './db'
import type { ConsentNotice, MappingResult } from './mapper/types'
import { loadPack } from './pack'
import { enqueue, flush, registerHandler } from './sync'

export const CONSENT_PURPOSES = ['rpl_assessment', 'evidence_capture', 'voice_processing'] as const

// ------------------------------------------------------------------ consent

export async function fetchNotice(lang: 'en' | 'hi'): Promise<ConsentNotice> {
  try {
    const notice = await api<ConsentNotice>(`/consents/notice?lang=${lang}`)
    await db.kv.put({ key: `notice.${lang}`, value: notice })
    return notice
  } catch {
    const cachedNotice = (await db.kv.get(`notice.${lang}`))?.value as ConsentNotice | undefined
    if (cachedNotice) return cachedNotice
    return (await loadPack()).pack.consent_notices[lang]
  }
}

// Per user: a shared field device may be used by several workers.
const consentKey = (username: string) => `consent.${username}.rpl_assessment`

export async function giveConsent(
  username: string,
  purposes: string[],
  lang: 'en' | 'hi',
  noticeSha: string,
): Promise<void> {
  await db.kv.put({ key: consentKey(username), value: purposes.includes('rpl_assessment') })
  await enqueue(
    'consent',
    { purposes: [...purposes], language: lang, granted: true, notice_sha256: noticeSha },
    newClientId('consent'),
  )
  void flush()
}

export async function hasConsent(username: string): Promise<boolean> {
  if ((await db.kv.get(consentKey(username)))?.value) return true
  try {
    const me = await api<{ state: Record<string, boolean> }>('/consents/me')
    await db.kv.put({ key: consentKey(username), value: !!me.state.rpl_assessment })
    return !!me.state.rpl_assessment
  } catch {
    return false
  }
}

// ------------------------------------------------------------------ declarations

export interface DeclarationInput {
  username: string
  narrative: string
  language: string
  inputMode: 'voice' | 'typed' | 'cards'
  cards: string[]
}

export function mappingText(d: Pick<LocalDeclaration, 'narrative' | 'cards'>): string {
  return [d.narrative, ...cardText(d.cards)].join(' ').trim()
}

/** Save locally, map on-device (instant, works offline), queue for the server. */
export async function submitDeclaration(input: DeclarationInput): Promise<LocalDeclaration> {
  // Plain copies only: IndexedDB cannot structured-clone Vue reactive proxies.
  const local: LocalDeclaration = {
    clientId: newClientId('decl'),
    username: input.username,
    narrative: input.narrative,
    language: input.language,
    inputMode: input.inputMode,
    cards: [...input.cards],
    createdAt: Date.now(),
    status: 'local',
  }
  try {
    const { mapper } = await loadPack()
    local.provisional = mapper.map(mappingText(local))
  } catch {
    // no pack available at all: the server mapping will fill this in
  }
  await db.declarations.put(local)
  await enqueue('declaration', { clientId: local.clientId }, local.clientId)
  void flush()
  return local
}

registerHandler('declaration', async (item) => {
  const d = await db.declarations.get(String(item.payload.clientId))
  if (!d) return
  if (!d.serverId) {
    const created = await api<{ id: number }>('/declarations', {
      body: {
        narrative: d.narrative || cardText(d.cards).join(', '),
        language: d.language,
        input_mode: d.inputMode,
        selected_cards: cardText(d.cards),
        client_id: d.clientId,
        captured_at: new Date(d.createdAt).toISOString(),
        provisional_mapping: d.provisional
          ? { engine: d.provisional.engine, top: d.provisional.top.map((t) => [t.qp_id, t.confidence]) }
          : null,
      },
    })
    d.serverId = created.id
    d.status = d.status === 'local' ? 'submitted' : d.status
    await db.declarations.put(d)
  }
  const mapping = await api<MappingResult>(`/declarations/${d.serverId}/map`, { method: 'POST' })
  const fresh = (await db.declarations.get(d.clientId)) ?? d
  fresh.serverId = d.serverId
  fresh.serverMapping = mapping
  if (fresh.status !== 'confirmed') fresh.status = 'mapped'
  await db.declarations.put(fresh)
})

registerHandler('consent', async (item) => {
  await api('/consents', { body: item.payload })
})

// ------------------------------------------------------------------ confirm

export async function confirmQualification(
  clientId: string,
  qpId: string,
  claimedPcIds: string[],
): Promise<LocalDeclaration> {
  const d = await db.declarations.get(clientId)
  if (!d) throw new Error('Declaration not found')
  d.assessmentClientId = d.assessmentClientId ?? newClientId('asmt')
  d.confirmedQpId = qpId
  d.claimedPcIds = [...claimedPcIds]
  d.status = 'confirmed'
  await db.declarations.put(d)
  await enqueue(
    'assessment_request',
    { declarationClientId: d.clientId, qpId, claimedPcIds: [...claimedPcIds], clientId: d.assessmentClientId },
    d.assessmentClientId,
  )
  void flush()
  return d
}

registerHandler('assessment_request', async (item) => {
  const p = item.payload as { declarationClientId: string; qpId: string; claimedPcIds: string[]; clientId: string }
  const a = await api<{ id: number }>('/assessments', {
    body: {
      qp_id: p.qpId,
      declaration_client_id: p.declarationClientId,
      claimed_pc_ids: p.claimedPcIds,
      client_id: p.clientId,
    },
  })
  const d = await db.declarations.get(p.declarationClientId)
  if (d) {
    d.assessmentId = a.id
    await db.declarations.put(d)
  }
})

export async function myDeclarations(username: string): Promise<LocalDeclaration[]> {
  const rows = await db.declarations.where('username').equals(username).toArray()
  return rows.sort((a, b) => b.createdAt - a.createdAt)
}
