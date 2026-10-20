import { api } from './api'
import type { AssessmentCard } from './assessor'

export interface NosProfile {
  nos_id: string
  title: string
  marks: { theory: number; practical: number; viva: number }
  earned: { theory: number; practical: number; viva: number }
  earned_total: number
  max_total: number
  percent: number
  status: 'competent' | 'partial' | 'gap'
  explanation: string
  bridge_module: { title: string; hours: number } | null
  pcs: { pc_id: string; code: string; level: number | null; critical: boolean; marks: number; earned: number }[]
}

export interface Profile {
  assessment: AssessmentCard
  qp_id: string
  qp_title: string
  nsqf_level: number
  aggregate_percent: number
  earned_total: number
  max_total: number
  recommendation: 'full' | 'partial' | 'gap'
  recommendation_reason: string
  competent_nos: string[]
  critical_below_standard: string[]
  unassessed_pcs: number
  bridge_modules: { nos_id: string; title: string; hours: number }[]
  bridge_hours: number
  nos: NosProfile[]
  note: string
  readiness: { scored: number; total: number; pending_reasons: string[]; can_sign_off: boolean }
}

export const fetchProfile = (id: number) => api<Profile>(`/assessments/${id}/profile`)
