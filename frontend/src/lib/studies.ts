import { api, API_BASE, getToken } from './api'
import type { Rubric } from './assessor'
import type { Reveal } from './scoring'

export interface Study {
  id: number
  name: string
  packet_ids: string[]
  pc_ids: string[]
  rater_ids: number[]
  status: string
  progress: { off: number; on: number; per_arm: number }
}

export interface StudyTask {
  study_id: number
  arm: 'off' | 'on'
  packet_id: string | null
  image_url?: string
  pcs?: { pc_id: string; code: string; text: string; nos_id: string; ai_signal: string | null; done: boolean }[]
  rubric?: Rubric | null
  progress: { off: number; on: number; per_arm: number }
}

export interface StudyResults {
  scores: { off: number; on: number }
  raters_with_scores: { off: number; on: number }
  alpha_off: number | null
  alpha_on_blind: number | null
  alpha_on_final: number | null
  ai_changed_scores: number
  note: string
}

export const listStudies = () => api<Study[]>('/studies')
export const createStudy = (name: string) => api<Study>('/studies', { body: { name } })
export const studyTask = (id: number, arm: 'off' | 'on') => api<StudyTask>(`/studies/${id}/task?arm=${arm}`)
export const studyResults = (id: number) => api<StudyResults>(`/studies/${id}/results`)
export const submitStudyScore = (id: number, body: { packet_id: string; pc_id: string; arm: string; score: number }) =>
  api<{ ai: Reveal | null }>(`/studies/${id}/scores`, { body })
export const reviseStudyScore = (id: number, body: { packet_id: string; pc_id: string; final_score: number }) =>
  api(`/studies/${id}/scores/final`, { body })

export async function studyImageUrl(path: string): Promise<string> {
  const res = await fetch(`${API_BASE}${path}`, { headers: { Authorization: `Bearer ${getToken()}` } })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return URL.createObjectURL(await res.blob())
}
