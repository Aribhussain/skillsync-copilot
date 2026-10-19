import { expect, test } from '@playwright/test'

import { GOLDEN, loginAs } from './helpers'

test('worker: consent -> kaam ki kahani -> Welding #1 -> confirm (online)', async ({ page }) => {
  await loginAs(page, 'worker1')
  await page.goto('/worker/consent')
  await page.getByTestId('consent-rpl_assessment').check()
  await page.getByTestId('consent-evidence_capture').check()
  await page.getByTestId('consent-submit').click()
  await expect(page).toHaveURL(/\/worker\/declare$/)

  // Headless browsers have no Web Speech API: the typed/cards fallback must be offered.
  const mic = page.getByTestId('mic-button')
  if (await mic.isDisabled()) await expect(page.getByTestId('voice-unavailable')).toBeVisible()

  await page.getByTestId('narrative-input').fill(GOLDEN)
  await page.getByTestId('declare-submit').click()
  await expect(page).toHaveURL(/\/worker\/results\//)

  await expect(page.getByTestId('mapping-source')).toHaveAttribute('data-provisional', 'false')
  await expect(page.getByTestId('qp-option-1')).toContainText('Welding')
  await expect(page.getByTestId('qp-option-1')).toContainText('QG-4.5-AU-01811-2024-V1-ASDC')
  await expect(page.getByTestId('lexicon-matches')).toContainText('GTAW (141)')
  await expect(page.getByTestId('claim-ASC-N3124.PC1')).toBeChecked() // argon -> GTAW claimed
  await expect(page.getByTestId('claim-ASC-N3123.PC1')).not.toBeChecked() // never said flux-cored

  await page.getByTestId('confirm-qp').click()
  await expect(page.getByTestId('confirmed')).toBeVisible()
})

test('worker: icon cards alone are enough to get a match', async ({ page }) => {
  await loginAs(page, 'worker2')
  await page.goto('/worker/consent')
  await page.getByTestId('consent-rpl_assessment').check()
  await page.getByTestId('consent-submit').click()
  await page.getByTestId('card-sewing').click()
  await page.getByTestId('declare-submit').click()
  await expect(page.getByTestId('qp-option-1')).toContainText('Sewing Machine Operator')
})
