/** Assessor-side data access. Server first; cached in IndexedDB so the checklist and
 *  rubric stay usable offline (e.g. during capture in a workshop without signal). */
import { api, NetworkError } from './api'
import { db } from './db'
import type { Route, Rule } from './evidencePlan'
import type { PCMarks } from './mapper/types'

export interface AssessmentCard {
  id: number
  qp_id: string
  qp_title: string
  nsqf_level: number | null
  candidate: string
  status: 'requested' | 'in_progress' | 'scored' | 'signed_off'
  claimed_pc_ids: string[]
  challenge_code: string | null
  centre: string | null
  created_at: string
}

export interface PlanPC {
  pc_id: string
  code: string
  text: string
  marks: PCMarks
  critical: boolean
  safety: boolean
  claimed: boolean
  ai_signal: string | null
  route: Route
  locked: boolean
  rule: Rule
  reason: string
  default_route?: Route
}

export interface PlanNOS {
  nos_id: string
  title: string
  marks: PCMarks
  pcs: PlanPC[]
}

export interface RubricLevel {
  level: number
  en: string
  hi: string
  fraction: number
}

export interface Rubric {
  scale: RubricLevel[]
  examples: Record<string, { good: string; poor: string; poor_label: string }>
  note: string
}

export interface PlanResponse {
  assessment: AssessmentCard
  qp: { id: string; title: string; title_hi?: string; nsqf_level: number }
  plan: PlanNOS[]
  summary: Record<string, number>
  rubric: Rubric
}

async function cached<T>(key: string, fetcher: () => Promise<T>): Promise<{ data: T; fromCache: boolean }> {
  try {
    const data = await fetcher()
    await db.kv.put({ key, value: data })
    return { data, fromCache: false }
  } catch (err) {
    const hit = (await db.kv.get(key))?.value as T | undefined
    if (hit !== undefined && err instanceof NetworkError) return { data: hit, fromCache: true }
    throw err
  }
}

export function fetchQueue() {
  return cached('assessor.queue', () => api<AssessmentCard[]>('/assessor/queue'))
}

export function fetchPlan(id: number) {
  return cached(`assessment.${id}.plan`, () => api<PlanResponse>(`/assessments/${id}/plan`))
}

export async function startAssessment(id: number): Promise<AssessmentCard> {
  const card = await api<AssessmentCard>(`/assessments/${id}/start`, { method: 'POST' })
  // keep the offline copy's challenge code in step
  const key = `assessment.${id}.plan`
  const plan = (await db.kv.get(key))?.value as PlanResponse | undefined
  if (plan) await db.kv.put({ key, value: { ...plan, assessment: card } })
  return card
}

export async function overrideRoute(id: number, pcId: string, route: Route, reason: string): Promise<void> {
  await api(`/assessments/${id}/plan`, { method: 'PATCH', body: { pc_id: pcId, route, reason } })
}
