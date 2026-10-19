import { expect, test } from '@playwright/test'

import { createAssessmentViaApi, GOLDEN, loginAs } from './helpers'

test('blind-first: AI appears only after the blind score; a big gap forces a reason code', async ({
  page,
  request,
}) => {
  const { assessmentId, assessorUsername } = await createAssessmentViaApi(request, 'worker1', GOLDEN, [])
  await loginAs(page, assessorUsername)
  await page.goto(`/assessor/assessment/${assessmentId}`)
  await page.getByTestId('start-assessment').click()

  // capture with a porous weld as the product photo (sample 4)
  await page.getByTestId('go-capture').click()
  await page.getByTestId('simulate-shot').click()
  await page.getByTestId('accept-shot').click()
  await page.getByTestId('sample-4').click()
  await page.getByTestId('simulate-shot').click()
  await page.getByTestId('accept-shot').click()
  await page.getByTestId('simulate-shot').click()
  await page.getByTestId('accept-shot').click()
  await page.getByTestId('seal-all').click()
  await expect(page.getByTestId('outbox-count')).toHaveAttribute('data-count', '0', { timeout: 20_000 })

  await page.goto(`/assessor/assessment/${assessmentId}`)
  await page.getByTestId('go-score').click()
  const pc = 'ASC-N3125.PC1' // "welds to specification" - judged from the product photo (porosity)
  const scorer = page.getByTestId(`scorer-${pc}`)
  await expect(scorer).toHaveAttribute('data-state', 'blind')
  await expect(page.getByTestId(`ai-level-${pc}`)).toHaveCount(0) // nothing revealed yet

  await page.getByTestId(`pick-${pc}-3`).click()
  await page.getByTestId(`lock-${pc}`).click()
  await expect(page.getByTestId(`reveal-${pc}`)).toBeVisible()
  await expect(page.getByTestId(`blind-${pc}`)).toHaveText('3')
  const aiLevel = Number(await page.getByTestId(`ai-level-${pc}`).textContent())
  expect(aiLevel).toBeLessThanOrEqual(1) // the demo model sees the pores

  // big gap: a reason is mandatory before saving
  await expect(page.getByTestId(`reason-box-${pc}`)).toBeVisible()
  await expect(page.getByTestId(`save-reason-${pc}`)).toBeDisabled()
  await page.getByTestId(`reason-${pc}`).selectOption('observed_live_differently')
  await page.getByTestId(`final-${pc}-2`).click()
  await page.getByTestId(`save-reason-${pc}`).click()
  await expect(page.getByTestId(`reason-saved-${pc}`)).toBeVisible()

  // a live-observation PC gets no AI opinion at all
  const live = 'ASC-N3124.PC3'
  await page.getByTestId(`pick-${live}-2`).click()
  await page.getByTestId(`lock-${live}`).click()
  await expect(page.getByTestId(`reveal-${live}`)).toBeVisible()
  await expect(page.getByTestId(`ai-level-${live}`)).toHaveCount(0)
})
