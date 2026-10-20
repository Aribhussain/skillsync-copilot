import { expect, type Page, test } from '@playwright/test'

import { API, apiToken, GOLDEN, loginAs } from '../e2e/helpers'

async function waitForServiceWorker(page: Page) {
  await page.evaluate(async () => {
    await navigator.serviceWorker.ready
  })
  // the SW calls clients.claim(); make sure it actually controls this page
  for (let i = 0; i < 10 && !(await page.evaluate(() => !!navigator.serviceWorker.controller)); i++) {
    await page.reload()
  }
  expect(await page.evaluate(() => !!navigator.serviceWorker.controller)).toBe(true)
}

test('built PWA: worker declares offline, assessor captures offline, everything syncs signed', async ({
  page,
  context,
  request,
}) => {
  // ---- worker: install the PWA while online, then work fully offline
  await page.goto('/login')
  await waitForServiceWorker(page)
  await loginAs(page, 'worker1')

  await context.setOffline(true)
  await page.reload() // served by the service worker
  await expect(page.getByTestId('network-status').locator('[role=status]')).toHaveAttribute('data-online', 'false')
  await page.goto('/worker/consent') // a full offline navigation
  await page.getByTestId('consent-rpl_assessment').check()
  await page.getByTestId('consent-evidence_capture').check()
  await page.getByTestId('consent-submit').click()
  await page.getByTestId('narrative-input').fill(GOLDEN)
  await page.getByTestId('declare-submit').click()
  await expect(page.getByTestId('mapping-source')).toHaveAttribute('data-provisional', 'true')
  await expect(page.getByTestId('qp-option-1')).toContainText('Welding')
  await page.getByTestId('confirm-qp').click()
  await expect(page.getByTestId('request-queued')).toBeVisible()

  await context.setOffline(false)
  await expect(page.getByTestId('request-synced')).toBeVisible({ timeout: 45_000 })

  // ---- find the synced assessment and its assessor
  const admin = { Authorization: `Bearer ${await apiToken(request, 'admin')}` }
  const worker = { Authorization: `Bearer ${await apiToken(request, 'worker1')}` }
  const mine = await (await request.get(`${API}/assessments/mine`, { headers: worker })).json()
  const assessment = mine[0]
  const users = await (await request.get(`${API}/users?role=assessor`, { headers: admin })).json()
  const assessor = users.find((u: { id: number }) => u.id === assessment.assessor_id).username

  // ---- assessor: start online (gets the challenge code), capture + seal offline
  await page.getByTestId('logout').click()
  await loginAs(page, assessor)
  await page.goto(`/assessor/assessment/${assessment.id}`)
  await page.getByTestId('start-assessment').click()
  await expect(page.getByTestId('challenge-code')).toBeVisible()

  await context.setOffline(true)
  await page.goto(`/assessor/assessment/${assessment.id}/capture`) // offline full navigation
  await page.getByTestId('simulate-shot').click()
  await page.getByTestId('accept-shot').click()
  await page.getByTestId('sample-2').click()
  await page.getByTestId('simulate-shot').click()
  await page.getByTestId('accept-shot').click()
  await page.getByTestId('simulate-shot').click()
  await page.getByTestId('accept-shot').click()
  await page.getByTestId('seal-all').click()
  await expect(page.getByTestId('sealed-all')).toBeVisible()
  await expect(page.getByTestId('outbox-count')).not.toHaveAttribute('data-count', '0')

  await context.setOffline(false)
  await expect(page.getByTestId('outbox-count')).toHaveAttribute('data-count', '0', { timeout: 45_000 })
  const h = { Authorization: `Bearer ${await apiToken(request, assessor)}` }
  const evidence = await (await request.get(`${API}/assessments/${assessment.id}/evidence`, { headers: h })).json()
  expect(evidence.map((e: { shot: string }) => e.shot).sort()).toEqual(['person', 'process', 'product'])
  expect(evidence.every((e: { signature_valid: boolean }) => e.signature_valid)).toBe(true)
})
