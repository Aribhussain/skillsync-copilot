import { defineConfig, devices } from '@playwright/test'

import base from './playwright.config'

/**
 * Browser e2e against the Docker full-mode stack (nginx on :8080, API on :8000).
 * Start it first: docker compose up -d --wait. Then: npm run e2e:docker
 * No webServer here: compose owns the processes.
 */
const launchOptions = base.use?.launchOptions

export default defineConfig({
  testDir: './e2e',
  timeout: 90_000,
  workers: 1,
  reporter: 'list',
  use: { baseURL: 'http://localhost:8080', trace: 'retain-on-failure', launchOptions },
  projects: [{ name: 'chromium-docker', use: { ...devices['Desktop Chrome'], launchOptions } }],
})
