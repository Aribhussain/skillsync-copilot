import { expect, type Page, test } from '@playwright/test'

import { createAssessmentViaApi, GOLDEN, loginAs } from './helpers'

/** Capture all three shots with simulated samples (product = sample #sample) and seal them. */
async function captureAndSeal(page: Page, assessmentId: number, sample: number) {
  await page.goto(`/assessor/assessment/${assessmentId}`)
  await page.getByTestId('start-assessment').click()
  await page.getByTestId('go-capture').click()
  await page.getByTestId('simulate-shot').click()
  await page.getByTestId('accept-shot').click()
  await page.getByTestId(`sample-${sample}`).click()
  await page.getByTestId('simulate-shot').click()
  await page.getByTestId('accept-shot').click()
  await page.getByTestId('simulate-shot').click()
  await page.getByTestId('accept-shot').click()
  await page.getByTestId('seal-all').click()
  await expect(page.getByTestId('sealed-all')).toBeVisible()
  await expect(page.getByTestId('outbox-count')).toHaveAttribute('data-count', '0', { timeout: 20_000 })
}

test('reused product photo for another candidate is flagged for the assessor', async ({ page, request }) => {
  // Two candidates who land with the same assessor (least-loaded: create until it repeats).
  const first = await createAssessmentViaApi(request, 'worker1', GOLDEN, [])
  let second = await createAssessmentViaApi(request, 'worker2', GOLDEN, [])
  for (let i = 0; i < 3 && second.assessorUsername !== first.assessorUsername; i++) {
    second = await createAssessmentViaApi(request, 'worker2', GOLDEN, [])
  }
  expect(second.assessorUsername).toBe(first.assessorUsername)

  await loginAs(page, first.assessorUsername)
  await captureAndSeal(page, first.assessmentId, 7)
  await captureAndSeal(page, second.assessmentId, 7) // same synthetic weld photo again

  await page.goto(`/assessor/assessment/${second.assessmentId}`)
  const product = page.getByTestId('evidence-product')
  await expect(product.getByTestId('flag-reused_image')).toBeVisible()
  await expect(product.getByTestId('flag-reused_image')).toHaveAttribute('data-severity', 'high')
  // The flag names the EARLIEST copy: the first candidate's on a fresh database, or an older
  // run's (the simulated sample photo is deterministic), never a later assessment.
  const flagged = await product.getByTestId('flag-reused_image').textContent()
  expect(referencedAssessment(flagged)).toBeLessThanOrEqual(first.assessmentId)

  // The first candidate's evidence is never flagged as a copy of the later one.
  await page.goto(`/assessor/assessment/${first.assessmentId}`)
  await expect(page.getByTestId('evidence-product')).toBeVisible()
  const firstFlag = page.getByTestId('evidence-product').getByTestId('flag-reused_image')
  if ((await firstFlag.count()) > 0) {
    expect(referencedAssessment(await firstFlag.textContent())).toBeLessThan(first.assessmentId)
  }
})

function referencedAssessment(text: string | null): number {
  const m = /#(\d+)/.exec(text ?? '')
  expect(m, `no assessment reference in: ${text}`).not.toBeNull()
  return Number(m![1])
}
