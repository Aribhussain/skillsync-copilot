/** Blind-first scoring client. The server only ever reveals an AI suggestion in the response
 *  to (or after) the assessor's own blind score; this module just carries that through,
 *  queueing blind scores in the outbox when offline. */
import { api, NetworkError } from './api'
import { db, newClientId } from './db'
import { enqueue, registerHandler } from './sync'

export interface Reveal {
  status: 'ok' | 'pending' | 'awaiting_photo' | 'none' | null
  level: number | null
  confidence: number | null
  explanation: string | null
  model_version?: string | null
  model_label?: string
  gap: number | null
  reason_required: boolean
}

export interface ScoreRow {
  id: number
  assessment_id: number
  pc_id: string
  blind_score: number
  final_score: number
  ai_status: Reveal['status']
  ai_level: number | null
  ai_confidence: number | null
  ai_explanation: string | null
  ai_model_version: string | null
  gap: number | null
  reason_required: boolean
  reason_code: string | null
  note: string | null
  revised_at: string | null
}

export const REASON_CODES = [
  'evidence_unclear',
  'ai_misread_image',
  'observed_live_differently',
  'rubric_ambiguity',
  'other',
] as const

export function revealFromRow(s: ScoreRow): Reveal {
  return {
    status: s.ai_status,
    level: s.ai_level,
    confidence: s.ai_confidence,
    explanation: s.ai_explanation,
    model_version: s.ai_model_version,
    gap: s.gap,
    reason_required: s.reason_required,
  }
}

export async function fetchMyScores(assessmentId: number): Promise<ScoreRow[]> {
  const key = `scores.${assessmentId}`
  try {
    const rows = await api<ScoreRow[]>(`/assessments/${assessmentId}/scores`)
    await db.kv.put({ key, value: rows })
    return rows
  } catch (err) {
    if (err instanceof NetworkError) return ((await db.kv.get(key))?.value as ScoreRow[] | undefined) ?? []
    throw err
  }
}

export type SubmitResult = { queued: true } | { queued: false; score: ScoreRow; ai: Reveal }

export async function submitBlindScore(assessmentId: number, pcId: string, score: number): Promise<SubmitResult> {
  const clientId = newClientId('score')
  try {
    const r = await api<{ score: ScoreRow; ai: Reveal }>(`/assessments/${assessmentId}/scores`, {
      body: { pc_id: pcId, score, client_id: clientId },
    })
    return { queued: false, ...r }
  } catch (err) {
    if (!(err instanceof NetworkError)) throw err
    await db.kv.put({ key: `pending-score.${assessmentId}.${pcId}`, value: score })
    await enqueue('score', { assessmentId, pcId, score, clientId }, clientId)
    return { queued: true }
  }
}

registerHandler('score', async (item) => {
  const p = item.payload as { assessmentId: number; pcId: string; score: number; clientId: string }
  await api(`/assessments/${p.assessmentId}/scores`, { body: { pc_id: p.pcId, score: p.score, client_id: p.clientId } })
  await db.kv.delete(`pending-score.${p.assessmentId}.${p.pcId}`)
  void fetchMyScores(p.assessmentId).catch(() => undefined)
})

export async function pendingScore(assessmentId: number, pcId: string): Promise<number | undefined> {
  return (await db.kv.get(`pending-score.${assessmentId}.${pcId}`))?.value as number | undefined
}

/** Re-check the AI opinion for an already blind-scored PC whose analysis was still running
 *  (full mode: Celery) or whose photo had not synced. The server keeps blind-first. */
export async function refreshAi(assessmentId: number, pcId: string): Promise<{ score: ScoreRow; ai: Reveal }> {
  return api<{ score: ScoreRow; ai: Reveal }>(`/assessments/${assessmentId}/scores/${encodeURIComponent(pcId)}/ai-refresh`, {
    method: 'POST',
  })
}

export async function reviseScore(
  assessmentId: number,
  pcId: string,
  body: { final_score?: number; reason_code?: string; note?: string },
): Promise<ScoreRow> {
  return api<ScoreRow>(`/assessments/${assessmentId}/scores/${encodeURIComponent(pcId)}`, { method: 'PATCH', body })
}
