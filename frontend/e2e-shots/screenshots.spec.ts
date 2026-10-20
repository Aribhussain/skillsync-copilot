import { mkdirSync } from 'node:fs'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { type APIRequestContext, expect, type Page, test } from '@playwright/test'

import { API, apiToken, createAssessmentViaApi, GOLDEN, loginAs } from '../e2e/helpers'

/**
 * The 4 screenshots for the SIH deck, captured from the running app into docs/screenshots/
 * at 1280x800 (desktop project) and 390x844 (mobile project). Run: npm run screenshots
 *
 * Screenshot 1 uses a SIMULATED speech recogniser (injected below) so the real voice UI can
 * be shown in a headless browser; on a phone the browser's own Web Speech API feeds it.
 */
const OUT = fileURLToPath(new URL('../../docs/screenshots/', import.meta.url))
mkdirSync(OUT, { recursive: true })

const HINDI =
  'मैं 6 साल से फैब्रिकेशन शॉप में काम करता हूँ, CO2 और आर्गन दोनों वेल्डिंग करता हूँ, प्लेट और पाइप जॉइंट बनाता हूँ, ग्राइंडिंग करके फिनिशिंग देता हूँ'

async function shot(page: Page, name: string) {
  await page.waitForTimeout(400) // fonts, transitions and chart entrance animations settle
  await page.screenshot({ path: `${OUT}${name}-${test.info().project.name}.png` })
}

/** A stand-in for window.SpeechRecognition: speaks HINDI in two chunks, then waits for stop(). */
function simulatedSpeech(text: string) {
  const [first, ...rest] = text.split(', ')
  class FakeRecognition extends EventTarget {
    lang = 'hi-IN'
    continuous = true
    interimResults = true
    onresult: ((ev: unknown) => void) | null = null
    onerror: ((ev: unknown) => void) | null = null
    onend: (() => void) | null = null
    start() {
      const result = (t: string, isFinal: boolean) => Object.assign([{ transcript: t, confidence: 0.9 }], { isFinal })
      setTimeout(() => this.onresult?.({ resultIndex: 0, results: [result(first, true)] }), 150)
      setTimeout(
        () => this.onresult?.({ resultIndex: 1, results: [result(first, true), result(rest.join(', '), false)] }),
        300,
      )
    }
    stop() {
      setTimeout(() => this.onend?.(), 50)
    }
  }
  ;(window as unknown as { SpeechRecognition: unknown }).SpeechRecognition = FakeRecognition
}

test('01 voice declaration (Hindi) and 02 QP match + per-PC claims', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('skillsync.locale', 'hi'))
  await page.addInitScript(simulatedSpeech, HINDI)
  await loginAs(page, 'worker1')
  await page.goto('/worker/consent')
  await page.getByTestId('consent-rpl_assessment').check()
  await page.getByTestId('consent-evidence_capture').check()
  await page.getByTestId('consent-submit').click()
  await expect(page).toHaveURL(/\/worker\/declare$/)

  await page.getByTestId('mic-button').click()
  await expect(page.getByTestId('narrative-input')).toHaveValue(/फैब्रिकेशन/)
  await page.getByTestId('mic-button').scrollIntoViewIfNeeded()
  await shot(page, '01-voice-declaration-hi')

  // Stop listening; the final transcript is the whole narrative.
  await page.getByTestId('mic-button').click()
  await page.getByTestId('narrative-input').fill(HINDI)
  await page.getByTestId('declare-submit').click()
  await expect(page).toHaveURL(/\/worker\/results\//)
  await expect(page.getByTestId('qp-option-1')).toContainText('QG-4.5-AU-01811-2024-V1-ASDC')
  await expect(page.getByTestId('claim-ASC-N3124.PC1')).toBeChecked()
  // #1 match at the top of the frame so the per-PC claim prefill below it is in view too
  await page.getByTestId('qp-option-1').evaluate((el) => window.scrollTo(0, el.getBoundingClientRect().top + window.scrollY - 72))
  await shot(page, '02-qp-match-claims')
})

test('03 guided P-P-P capture with the challenge code', async ({ page, request }) => {
  const { assessmentId, assessorUsername } = await createAssessmentViaApi(request, 'worker2', GOLDEN, [])
  await loginAs(page, assessorUsername)
  await page.goto(`/assessor/assessment/${assessmentId}`)
  await page.getByTestId('start-assessment').click()
  await page.getByTestId('go-capture').click()
  await page.getByTestId('simulate-shot').click()
  await page.getByTestId('accept-shot').click()
  await page.getByTestId('sample-0').click()
  await page.getByTestId('simulate-shot').click()
  await page.getByTestId('accept-shot').click()
  await expect(page.getByTestId('capture-challenge-code')).toBeVisible()
  await page.getByTestId('simulate-shot').click()
  await expect(page.getByTestId('qc-result')).toBeVisible()
  await shot(page, '03-ppp-capture-challenge-code')
})

test('04 blind scoring with the AI reveal, and the calibration dashboard', async ({ page, request }) => {
  const { assessmentId, assessorUsername } = await createAssessmentViaApi(request, 'worker1', GOLDEN, [])
  await loginAs(page, assessorUsername)
  await page.goto(`/assessor/assessment/${assessmentId}`)
  await page.getByTestId('start-assessment').click()
  await page.getByTestId('go-capture').click()
  await page.getByTestId('simulate-shot').click()
  await page.getByTestId('accept-shot').click()
  await page.getByTestId('sample-4').click() // porous weld
  await page.getByTestId('simulate-shot').click()
  await page.getByTestId('accept-shot').click()
  await page.getByTestId('simulate-shot').click()
  await page.getByTestId('accept-shot').click()
  await page.getByTestId('seal-all').click()
  await expect(page.getByTestId('sealed-all')).toBeVisible()
  await expect(page.getByTestId('outbox-count')).toHaveAttribute('data-count', '0', { timeout: 20_000 })

  await page.goto(`/assessor/assessment/${assessmentId}`)
  await page.getByTestId('go-score').click()
  const pc = 'ASC-N3125.PC1'
  await page.getByTestId('nos-filter-N3125').click() // one NOS: the PC sits near the top on a phone
  await page.getByTestId(`pick-${pc}-3`).click()
  await page.getByTestId(`lock-${pc}`).click()
  await expect(page.getByTestId(`ai-level-${pc}`)).toBeVisible({ timeout: 30_000 })
  await expect(page.getByTestId(`reason-box-${pc}`)).toBeVisible()
  await page.getByTestId(`scorer-${pc}`).scrollIntoViewIfNeeded()
  await page.evaluate(() => window.scrollBy(0, -120))
  await shot(page, '04a-blind-scoring-ai-reveal')

  await page.getByTestId('logout').click()
  await loginAs(page, 'qa1')
  await page.getByTestId('seed-golden').click()
  for (const [assessor, offset] of [
    ['assessor1', 0],
    ['assessor2', 0],
    ['assessor3', 1],
  ] as const) {
    await scoreGolden(request, assessor, offset)
  }
  await page.reload()
  await expect(page.getByTestId('kpi-alpha-blind')).not.toContainText('—')
  await expect(page.getByTestId('heatmap').locator('canvas').first()).toBeVisible()
  await page.waitForTimeout(500)
  await shot(page, '04b-calibration-dashboard')
})

const GOLDEN_PACKETS = JSON.parse(
  readFileSync(new URL('../../data/golden_packets/golden_packets.json', import.meta.url), 'utf8'),
) as { packets: { id: string; consensus: Record<string, number> }[] }
const CONSENSUS = Object.fromEntries(GOLDEN_PACKETS.packets.map((p) => [p.id, p.consensus]))

/** Score the assessor's (SYNTHETIC) golden packets at consensus + offset, via the API. */
async function scoreGolden(request: APIRequestContext, assessor: string, offset: number) {
  const h = { Authorization: `Bearer ${await apiToken(request, assessor)}` }
  const admin = { Authorization: `Bearer ${await apiToken(request, 'admin')}` }
  for (const card of await (await request.get(`${API}/assessor/queue`, { headers: h })).json()) {
    const a = await (await request.get(`${API}/assessments/${card.id}`, { headers: admin })).json()
    if (!a.is_golden) continue
    for (const [pc, level] of Object.entries(CONSENSUS[a.golden_packet_id])) {
      await request.post(`${API}/assessments/${card.id}/scores`, {
        headers: h,
        data: { pc_id: pc, score: Math.max(0, Math.min(3, level + offset)) },
      })
    }
  }
}
