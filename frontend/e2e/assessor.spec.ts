import { expect, test } from '@playwright/test'

import { createAssessmentViaApi, GOLDEN, loginAs } from './helpers'

test('assessor: queue -> PC checklist with locked critical PCs, rubric anchors and challenge code', async ({
  page,
  request,
}) => {
  const { assessmentId, assessorUsername } = await createAssessmentViaApi(request, 'worker1', GOLDEN, [
    'ASC-N3124.PC1',
    'ASC-N9819.PC8',
  ])
  await loginAs(page, assessorUsername)
  await expect(page).toHaveURL(/\/assessor$/)
  await page.getByTestId(`queue-item-${assessmentId}`).click()

  await expect(page.getByTestId('assessment-view')).toBeVisible()
  // GTAW PC3 is critical: locked to live observation, with an explanation
  await expect(page.getByTestId('lock-ASC-N3124.PC3')).toBeVisible()
  await expect(page.getByTestId('route-ASC-N3124.PC3')).toHaveAttribute('data-route', 'observe')
  await expect(page.getByTestId('reason-ASC-N3124.PC3')).toContainText('cannot be overridden')
  // product PC -> signed photo; claimed declaration PC -> declaration + spot-check
  await expect(page.getByTestId('route-ASC-N3124.PC1')).toHaveAttribute('data-route', 'photo')
  await expect(page.getByTestId('route-ASC-N9819.PC8')).toHaveAttribute('data-route', 'declaration+spot-check')

  // rubric anchors with synthetic example images
  await page.getByTestId('pc-ASC-N3125.PC1').getByRole('button', { name: 'Rubric anchors' }).click()
  await expect(page.getByTestId('rubric-anchors')).toContainText('SYNTHETIC')

  await page.getByTestId('start-assessment').click()
  await expect(page.getByTestId('challenge-code')).toHaveText(/[A-Z0-9]{6}/)
})
