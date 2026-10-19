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
  await expect(product.getByTestId('flag-reused_image')).toContainText(`#${first.assessmentId}`)

  // The first candidate's evidence carries no reuse flag.
  await page.goto(`/assessor/assessment/${first.assessmentId}`)
  await expect(page.getByTestId('evidence-product')).toBeVisible()
  await expect(page.getByTestId('evidence-product').getByTestId('flag-reused_image')).toHaveCount(0)
})
