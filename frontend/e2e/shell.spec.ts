import { expect, test } from '@playwright/test'

test('login with a demo account lands on the role home, with synthetic badge', async ({ page }) => {
  await page.goto('/login')
  await expect(page.getByTestId('demo-accounts')).toBeVisible()
  await page.getByTestId('demo-worker1').click()
  await page.getByTestId('login-submit').click()
  await expect(page).toHaveURL(/\/worker$/)
  await expect(page.getByTestId('current-user')).toContainText('Ramesh Kumar')
  await expect(page.getByTestId('synthetic-badge')).toBeVisible()
})

test('wrong password shows an error', async ({ page }) => {
  await page.goto('/login')
  await page.locator('input[name=username]').fill('worker1')
  await page.locator('input[name=password]').fill('nope')
  await page.getByTestId('login-submit').click()
  await expect(page.getByTestId('login-error')).toBeVisible()
})

test('online / offline indicator follows the network', async ({ page, context }) => {
  await page.goto('/login')
  const status = page.getByTestId('network-status').locator('[role=status]')
  await expect(status).toHaveAttribute('data-online', 'true')
  await context.setOffline(true)
  await expect(status).toHaveAttribute('data-online', 'false')
  await context.setOffline(false)
  await expect(status).toHaveAttribute('data-online', 'true', { timeout: 20_000 })
})

test('language toggle switches to Hindi', async ({ page }) => {
  await page.goto('/login')
  await page.getByTestId('lang-toggle').click()
  await expect(page.locator('h1')).toHaveText('साइन इन करें')
})

test('role guard keeps a worker out of the QA dashboard', async ({ page }) => {
  await page.goto('/login')
  await page.getByTestId('demo-worker1').click()
  await page.getByTestId('login-submit').click()
  await expect(page).toHaveURL(/\/worker$/)
  await page.goto('/qa')
  await expect(page).toHaveURL(/\/worker$/)
})
