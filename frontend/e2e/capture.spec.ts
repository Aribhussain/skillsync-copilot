import { expect, test } from '@playwright/test'

import { API, apiToken, createAssessmentViaApi, GOLDEN, loginAs } from './helpers'

test('assessor: guided Process -> Product -> Person capture with on-device QC', async ({ page, request }) => {
  const { assessmentId, assessorUsername } = await createAssessmentViaApi(request, 'worker1', GOLDEN, [])
  await loginAs(page, assessorUsername)
  await page.goto(`/assessor/assessment/${assessmentId}`)
  await page.getByTestId('start-assessment').click()
  const code = (await page.getByTestId('challenge-code').locator('div').nth(1).textContent())!.trim()
  await page.getByTestId('go-capture').click()

  // Process (simulated sample on a laptop without camera)
  await page.getByTestId('simulate-shot').click()
  await expect(page.getByTestId('qc-result')).toBeVisible()
  await page.getByTestId('accept-shot').click()
  await expect(page.getByTestId('step-process')).toHaveAttribute('data-done', 'true')

  // Product: synthetic weld sample; QC must pass (sharp, centred)
  await page.getByTestId('sample-0').click()
  await page.getByTestId('simulate-shot').click()
  await expect(page.getByTestId('qc-result')).toHaveAttribute('data-ok', 'true')
  await page.getByTestId('accept-shot').click()

  // Person: the challenge code is shown to be written on the slate
  await expect(page.getByTestId('capture-challenge-code')).toHaveText(code)
  await page.getByTestId('simulate-shot').click()
  await page.getByTestId('accept-shot').click()
  await expect(page.getByTestId('capture-review')).toBeVisible()

  // Seal: browser WebCrypto signs; the Python server must verify every packet.
  await page.getByTestId('seal-all').click()
  await expect(page.getByTestId('sealed-all')).toBeVisible()
  await expect(page.getByTestId('outbox-count')).toHaveAttribute('data-count', '0', { timeout: 20_000 })
  const token = await apiToken(request, assessorUsername)
  const evidence = await (
    await request.get(`${API}/assessments/${assessmentId}/evidence`, { headers: { Authorization: `Bearer ${token}` } })
  ).json()
  expect(evidence.map((e: { shot: string }) => e.shot).sort()).toEqual(['person', 'process', 'product'])
  for (const e of evidence) {
    expect(e.signature_valid).toBe(true)
    expect(e.challenge_code).toBe(code)
    expect(e.source).toBe('simulated')
  }
})

test('QC rejects a blurry upload with "hold steady" feedback', async ({ page, request }) => {
  const { assessmentId, assessorUsername } = await createAssessmentViaApi(request, 'worker2', GOLDEN, [])
  await loginAs(page, assessorUsername)
  await page.goto(`/assessor/assessment/${assessmentId}`)
  await page.getByTestId('start-assessment').click()
  await page.getByTestId('go-capture').click()
  // A flat grey 640x480 image: no detail at all -> blur + framing issues
  const blank = await page.evaluate(() => {
    const c = document.createElement('canvas')
    c.width = 640
    c.height = 480
    const ctx = c.getContext('2d')!
    ctx.fillStyle = '#888'
    ctx.fillRect(0, 0, 640, 480)
    return c.toDataURL('image/png').split(',')[1]
  })
  await page.getByTestId('file-input').setInputFiles({
    name: 'blurry.png',
    mimeType: 'image/png',
    buffer: Buffer.from(blank, 'base64'),
  })
  await expect(page.getByTestId('qc-result')).toHaveAttribute('data-ok', 'false')
  await expect(page.getByTestId('qc-issue-blur')).toBeVisible()
})
