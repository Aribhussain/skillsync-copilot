import { expect, test } from '@playwright/test'

import { API, apiToken, loginAs } from './helpers'

test('live consistency study: OFF arm without AI, then ON arm with blind-first reveal; QA sees alpha', async ({
  page,
  request,
}) => {
  const qa = { Authorization: `Bearer ${await apiToken(request, 'qa1')}` }
  const study = await (
    await request.post(`${API}/studies`, {
      headers: qa,
      data: { name: 'E2E pilot', packet_ids: ['GP-03'], rater_usernames: ['assessor1', 'assessor2'] },
    })
  ).json()

  await loginAs(page, 'assessor1')
  await page.getByTestId(`study-link-${study.id}`).click()
  await expect(page.getByTestId('study-arm')).toHaveAttribute('data-arm', 'off')
  for (const pc of study.pc_ids as string[]) {
    await page.getByTestId(`study-pick-${pc}-2`).click()
    await page.getByTestId(`study-lock-${pc}`).click()
  }
  await expect(page.getByText('AI suggests')).toHaveCount(0) // never in the OFF arm
  await page.getByTestId('study-next').click()

  await expect(page.getByTestId('study-arm')).toHaveAttribute('data-arm', 'on')
  const first = (study.pc_ids as string[])[0]
  await page.getByTestId(`study-pick-${first}-3`).click()
  await page.getByTestId(`study-lock-${first}`).click()
  await expect(page.getByTestId(`study-pc-${first}`)).toContainText('AI suggests')

  await page.getByTestId('logout').click()
  await loginAs(page, 'qa1')
  await expect(page.getByTestId(`study-row-${study.id}`)).toContainText('E2E pilot')
})
