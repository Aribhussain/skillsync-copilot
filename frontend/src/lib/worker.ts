/** Worker-side flow: consent -> declaration -> mapping -> confirm (assessment request). */
import { api } from './api'
import { cardText } from './cards'
import { db, type LocalDeclaration, newClientId } from './db'
import type { ConsentNotice, MappingResult } from './mapper/types'

export const CONSENT_PURPOSES = ['rpl_assessment', 'evidence_capture', 'voice_processing'] as const

export async function fetchNotice(lang: 'en' | 'hi'): Promise<ConsentNotice> {
  const notice = await api<ConsentNotice>(`/consents/notice?lang=${lang}`)
  await db.kv.put({ key: `notice.${lang}`, value: notice })
  return notice
}

export async function giveConsent(purposes: string[], lang: 'en' | 'hi', noticeSha: string): Promise<void> {
  await api('/consents', { body: { purposes, language: lang, granted: true, notice_sha256: noticeSha } })
  await db.kv.put({ key: 'consent.rpl_assessment', value: true })
}

export async function hasConsent(): Promise<boolean> {
  try {
    const me = await api<{ state: Record<string, boolean> }>('/consents/me')
    await db.kv.put({ key: 'consent.rpl_assessment', value: !!me.state.rpl_assessment })
    return !!me.state.rpl_assessment
  } catch {
    return !!(await db.kv.get('consent.rpl_assessment'))?.value
  }
}

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

/** Save locally first, then submit and map on the server. */
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
  await db.declarations.put(local)
  const created = await api<{ id: number }>('/declarations', {
    body: {
      narrative: local.narrative || cardText(local.cards).join(', '),
      language: local.language,
      input_mode: local.inputMode,
      selected_cards: cardText(local.cards),
      client_id: local.clientId,
      captured_at: new Date(local.createdAt).toISOString(),
    },
  })
  local.serverId = created.id
  local.status = 'submitted'
  local.serverMapping = await api<MappingResult>(`/declarations/${created.id}/map`, { method: 'POST' })
  local.status = 'mapped'
  await db.declarations.put(local)
  return local
}

export async function confirmQualification(
  clientId: string,
  qpId: string,
  claimedPcIds: string[],
): Promise<LocalDeclaration> {
  const d = await db.declarations.get(clientId)
  if (!d) throw new Error('Declaration not found')
  d.assessmentClientId = d.assessmentClientId ?? newClientId('asmt')
  const a = await api<{ id: number }>('/assessments', {
    body: {
      qp_id: qpId,
      declaration_client_id: d.clientId,
      claimed_pc_ids: claimedPcIds,
      client_id: d.assessmentClientId,
    },
  })
  d.assessmentId = a.id
  d.confirmedQpId = qpId
  d.claimedPcIds = claimedPcIds
  d.status = 'confirmed'
  await db.declarations.put(d)
  return d
}

export async function myDeclarations(username: string): Promise<LocalDeclaration[]> {
  const rows = await db.declarations.where('username').equals(username).toArray()
  return rows.sort((a, b) => b.createdAt - a.createdAt)
}
