import { expect, test } from '@playwright/test'

import { GOLDEN, loginAs } from './helpers'

test('worker offline: on-device mapping, queued request, then sync when back online', async ({ page, context }) => {
  await loginAs(page, 'worker1')
  await page.goto('/worker/consent')
  await page.getByTestId('consent-rpl_assessment').check()
  await page.getByTestId('consent-submit').click()
  await expect(page).toHaveURL(/\/worker\/declare$/)
  // No full page reloads from here: the role's views were prefetched after login.
  await expect(page.getByTestId('outbox-count')).toHaveAttribute('data-count', '0', { timeout: 20_000 })

  await context.setOffline(true)
  await expect(page.getByTestId('network-status').locator('[role=status]')).toHaveAttribute('data-online', 'false')

  await page.getByTestId('narrative-input').fill(GOLDEN)
  await page.getByTestId('declare-submit').click()
  await expect(page).toHaveURL(/\/worker\/results\//)
  await expect(page.getByTestId('mapping-source')).toHaveAttribute('data-provisional', 'true')
  await expect(page.getByTestId('qp-option-1')).toContainText('Welding')
  await expect(page.getByTestId('lexicon-matches')).toContainText('GTAW (141)')

  await page.getByTestId('confirm-qp').click()
  await expect(page.getByTestId('request-queued')).toBeVisible()
  await expect(page.getByTestId('outbox-count')).toHaveAttribute('data-count', '2')

  await context.setOffline(false)
  await expect(page.getByTestId('request-synced')).toBeVisible({ timeout: 30_000 })
  await expect(page.getByTestId('mapping-source')).toHaveAttribute('data-provisional', 'false')
  await expect(page.getByTestId('outbox-count')).toHaveAttribute('data-count', '0')
})
