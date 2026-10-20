import { readFileSync } from 'node:fs'

import { expect, test } from '@playwright/test'

import { API, apiToken, createAssessmentViaApi, GOLDEN, loginAs } from './helpers'

const qpFile = JSON.parse(
  readFileSync(new URL('../../data/qp_corpus/welding_QG-4.5-AU-01811-2024-V1-ASDC.json', import.meta.url), 'utf8'),
) as { nos: { id: string; pcs: { code: string }[] }[] }

test('competency profile: a GTAW gap gives Partial with a GTAW bridge module', async ({ page, request }) => {
  const { assessmentId, assessorUsername } = await createAssessmentViaApi(request, 'worker1', GOLDEN, [])
  const h = { Authorization: `Bearer ${await apiToken(request, assessorUsername)}` }
  await request.post(`${API}/assessments/${assessmentId}/start`, { headers: h })
  for (const nos of qpFile.nos) {
    for (const pc of nos.pcs) {
      const pcId = `${nos.id.replace('/', '-')}.${pc.code}`
      const score = nos.id === 'ASC/N3124' ? 0 : 2
      await request.post(`${API}/assessments/${assessmentId}/scores`, { headers: h, data: { pc_id: pcId, score } })
    }
  }

  await loginAs(page, assessorUsername)
  await page.goto(`/assessor/assessment/${assessmentId}`)
  await page.getByTestId('go-profile').click()
  await expect(page.getByTestId('recommendation')).toHaveAttribute('data-rec', 'partial')
  await expect(page.getByTestId('nos-row-ASC/N3124')).toHaveAttribute('data-status', 'gap')
  await expect(page.getByTestId('bridge-ASC/N3124')).toContainText('GTAW')
  await expect(page.getByTestId('nos-row-ASC/N3122')).toHaveAttribute('data-status', 'competent')

  // human gate: sign off with password -> credential with QR -> public verify page
  await page.getByTestId('signoff-confirm').check()
  await page.getByTestId('signoff-password').fill('wrong-password')
  await page.getByTestId('signoff-submit').click()
  await expect(page.getByTestId('signoff-error')).toBeVisible()
  await page.getByTestId('signoff-password').fill('assessor123')
  await page.getByTestId('signoff-submit').click()
  await expect(page.getByTestId('signed-off')).toBeVisible()
  await expect(page.getByTestId('credential-qr')).toBeVisible()
  await page.getByTestId('verify-link').click()
  await expect(page.getByTestId('verify-status')).toHaveAttribute('data-valid', 'true')
  await expect(page.getByTestId('verify-view')).toContainText('Ramesh Kumar')

  // anyone can verify without logging in; the worker sees the certificate at home
  await page.getByTestId('logout').click()
  await page.goBack()
  await expect(page.getByTestId('verify-status')).toHaveAttribute('data-valid', 'true')
  await loginAs(page, 'worker1')
  await expect(page.getByTestId('my-credentials')).toBeVisible()
})
