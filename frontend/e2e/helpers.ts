import { type APIRequestContext, expect, type Page } from '@playwright/test'

export const API = 'http://localhost:8000'

export const GOLDEN =
  'Main 6 saal se fabrication shop mein kaam karta hoon, CO2 aur argon dono welding karta hoon, plate aur pipe joint banata hoon, grinding karke finishing deta hoon'

export const WELDING = 'QG-4.5-AU-01811-2024-V1-ASDC'

const PASSWORDS: Record<string, string> = { worker: 'worker123', assessor: 'assessor123', qa: 'qa123', admin: 'admin123' }

export function passwordFor(username: string): string {
  return Object.entries(PASSWORDS).find(([prefix]) => username.startsWith(prefix))![1]
}

export async function loginAs(page: Page, username: string) {
  await page.goto('/login')
  await page.getByTestId(`demo-${username}`).click()
  await page.getByTestId('login-submit').click()
  await expect(page).not.toHaveURL(/\/login/)
}

export async function apiToken(request: APIRequestContext, username: string): Promise<string> {
  const r = await request.post(`${API}/auth/login`, { data: { username, password: passwordFor(username) } })
  expect(r.ok()).toBeTruthy()
  return (await r.json()).access_token
}

/** Worker declares + confirms Welding via the API; returns the assessment and its assessor. */
export async function createAssessmentViaApi(
  request: APIRequestContext,
  worker: string,
  narrative: string,
  claimed: string[],
): Promise<{ assessmentId: number; assessorUsername: string }> {
  const h = { Authorization: `Bearer ${await apiToken(request, worker)}` }
  await request.post(`${API}/consents`, { headers: h, data: { purposes: ['rpl_assessment', 'evidence_capture'] } })
  const d = await (await request.post(`${API}/declarations`, { headers: h, data: { narrative } })).json()
  const a = await (
    await request.post(`${API}/assessments`, {
      headers: h,
      data: { qp_id: WELDING, declaration_id: d.id, claimed_pc_ids: claimed },
    })
  ).json()
  const admin = { Authorization: `Bearer ${await apiToken(request, 'admin')}` }
  const users: { id: number; username: string }[] = await (await request.get(`${API}/users?role=assessor`, { headers: admin })).json()
  return { assessmentId: a.id, assessorUsername: users.find((u) => u.id === a.assessor_id)!.username }
}
