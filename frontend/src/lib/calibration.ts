import { api } from './api'

export interface AssessorIndex {
  n: number
  index: number | null
  bias: number | null
  drift: number | null
  centre?: string | null
}

export interface CalibrationSummary {
  synthetic_note: string
  units: number
  scores: number
  alpha_blind: number | null
  alpha_final: number | null
  alpha_decision: number | null
  alpha_per_pc: Record<string, number | null>
  trend: { week: string; alpha_blind: number | null; alpha_final: number | null; n: number }[]
  heatmap: { assessors: string[]; nos: string[]; values: (number | null)[][] }
  assessors: Record<string, AssessorIndex>
  centres: Record<string, number>
  reason_codes: Record<string, number>
  ai_agreement_within_1: number | null
}

export const fetchSummary = () => api<CalibrationSummary>('/calibration/summary')
export const fetchMyIndex = () => api<AssessorIndex & { assessor: string; note: string }>('/calibration/me')
export const fetchAuditVerify = () =>
  api<{ valid: boolean; entries: number; broken_at: number | null; reason: string | null }>('/audit/verify')
export const seedGolden = (perAssessor = 4) =>
  api<{ created: number }>('/calibration/golden/seed', { body: { per_assessor: perAssessor } })
