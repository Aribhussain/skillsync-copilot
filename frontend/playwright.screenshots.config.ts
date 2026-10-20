import { defineConfig, devices } from '@playwright/test'

import base from './playwright.config'

/**
 * Deck screenshots (docs/screenshots/*-desktop.png and *-mobile.png). Run: npm run screenshots
 * Same dev servers and e2e database as the e2e suite; Brave locally, Chromium in CI.
 */
const launchOptions = base.use?.launchOptions

export default defineConfig({
  ...base,
  testDir: './e2e-shots',
  timeout: 120_000,
  reporter: 'list',
  projects: [
    {
      name: 'desktop',
      use: { ...devices['Desktop Chrome'], viewport: { width: 1280, height: 800 }, launchOptions },
    },
    {
      name: 'mobile',
      use: {
        ...devices['Desktop Chrome'],
        viewport: { width: 390, height: 844 },
        deviceScaleFactor: 2,
        isMobile: true,
        hasTouch: true,
        launchOptions,
      },
    },
  ],
})
