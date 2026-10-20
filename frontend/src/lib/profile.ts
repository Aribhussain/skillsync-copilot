import { api, API_BASE, getToken } from './api'
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
  decision: 'full' | 'partial' | 'gap' | null
  decision_justification: string | null
  credential_id: string | null
}

export interface VerifyResult {
  credential_id: string
  valid: boolean
  signature_valid: boolean
  issuer_trusted: boolean
  reason: string | null
  status: string
  issuer: { id: string; name: string }
  issued: string
  holder: string
  qualification: string
  result: string
  note: string
}

export const fetchProfile = (id: number) => api<Profile>(`/assessments/${id}/profile`)

export const signOff = (
  id: number,
  body: { password: string; decision: string; justification?: string; confirm: boolean },
) => api<{ decision: string; credential_id: string | null; verify_url: string | null }>(`/assessments/${id}/signoff`, { body })

export const verifyCredential = (credentialId: string) =>
  api<VerifyResult>(`/credentials/${encodeURIComponent(credentialId)}/verify`)

export const myCredentials = () =>
  api<{ credential_id: string; assessment_id: number; title: string; result: string; issued: string }[]>(
    '/credentials/mine/list',
  )

/** The PDF needs the bearer token, so open it from a blob URL. */
export async function openCredentialPdf(credentialId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/credentials/${credentialId}/pdf`, {
    headers: { Authorization: `Bearer ${getToken()}` },
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  window.open(URL.createObjectURL(await res.blob()), '_blank')
}

export function verifyPageUrl(credentialId: string): string {
  return `${window.location.origin}/verify/${credentialId}`
}
