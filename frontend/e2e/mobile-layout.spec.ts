import { expect, type Page, test } from '@playwright/test'

import { createAssessmentViaApi, GOLDEN, loginAs } from './helpers'

/** Field devices are phones: no screen may scroll sideways at 390 px. */
test.use({ viewport: { width: 390, height: 844 } })

async function expectNoSideways(page: Page, what: string) {
  await page.waitForLoadState('networkidle')
  const { scrollWidth, clientWidth } = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
  }))
  expect(scrollWidth, `${what} is ${scrollWidth}px wide at ${clientWidth}px`).toBeLessThanOrEqual(clientWidth)
}

test('no horizontal page scroll on phone width (worker, assessor, QA screens)', async ({ page, request }) => {
  await page.goto('/login')
  await expectNoSideways(page, 'login')
  await loginAs(page, 'worker1')
  await expectNoSideways(page, 'worker home')
  await page.goto('/worker/declare')
  await expectNoSideways(page, 'declare')

  const { assessmentId, assessorUsername } = await createAssessmentViaApi(request, 'worker1', GOLDEN, [])
  await page.getByTestId('logout').click()
  await loginAs(page, assessorUsername)
  await expectNoSideways(page, 'assessor home')
  await page.goto(`/assessor/assessment/${assessmentId}`)
  await expectNoSideways(page, 'assessment')
  await page.getByTestId('start-assessment').click()
  await page.getByTestId('go-capture').click()
  await expectNoSideways(page, 'capture')
  await page.goto(`/assessor/assessment/${assessmentId}`)
  await page.getByTestId('go-score').click()
  await expectNoSideways(page, 'scoring')

  await page.getByTestId('logout').click()
  await loginAs(page, 'qa1')
  await expectNoSideways(page, 'QA dashboard')
})
