import { readFileSync } from 'node:fs'

import { type APIRequestContext, expect, test } from '@playwright/test'

import { API, apiToken, loginAs } from './helpers'

const GOLDEN = JSON.parse(
  readFileSync(new URL('../../data/golden_packets/golden_packets.json', import.meta.url), 'utf8'),
) as { packets: { id: string; consensus: Record<string, number> }[] }
const consensus = Object.fromEntries(GOLDEN.packets.map((p) => [p.id, p.consensus]))

async function scoreGolden(request: APIRequestContext, assessor: string, offset: number) {
  const h = { Authorization: `Bearer ${await apiToken(request, assessor)}` }
  const admin = { Authorization: `Bearer ${await apiToken(request, 'admin')}` }
  const queue = await (await request.get(`${API}/assessor/queue`, { headers: h })).json()
  for (const card of queue) {
    const a = await (await request.get(`${API}/assessments/${card.id}`, { headers: admin })).json()
    if (!a.is_golden) continue
    for (const [pc, level] of Object.entries(consensus[a.golden_packet_id])) {
      await request.post(`${API}/assessments/${card.id}/scores`, {
        headers: h,
        data: { pc_id: pc, score: Math.max(0, Math.min(3, level + offset)) },
      })
    }
  }
}

test('QA dashboard: alpha, drift heat-map, audit badge; assessor sees only their own index', async ({ page, request }) => {
  await loginAs(page, 'qa1')
  await page.getByTestId('seed-golden').click()
  await scoreGolden(request, 'assessor1', 0)
  await scoreGolden(request, 'assessor2', 0)
  await scoreGolden(request, 'assessor3', 1)
  await page.reload()

  await expect(page.getByTestId('audit-badge')).toHaveAttribute('data-valid', 'true')
  await expect(page.getByTestId('kpi-alpha-blind')).not.toContainText('—')
  await expect(page.getByTestId('heatmap').locator('canvas').first()).toBeVisible()
  await expect(page.getByTestId('assessor-indices')).toContainText('assessor3')
  await page.setViewportSize({ width: 1280, height: 1100 })
  await page.waitForTimeout(800) // let the 300 ms chart entrance animation finish before the screenshot
  await page.screenshot({ path: test.info().outputPath('qa-dashboard.png'), fullPage: true })

  await page.getByTestId('logout').click()
  await loginAs(page, 'assessor3')
  await expect(page.getByTestId('my-index')).toBeVisible()
  await expect(page.getByTestId('my-index')).not.toContainText('assessor1')
})
