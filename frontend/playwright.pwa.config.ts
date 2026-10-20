import { defineConfig, devices } from '@playwright/test'

import base from './playwright.config'

/**
 * Offline e2e against the BUILT PWA (vite preview, real service worker), so offline reloads
 * are served by the service worker exactly as on a field device. Run: npm run e2e:pwa
 */
const isWin = process.platform === 'win32'
const python = process.env.BACKEND_PYTHON ?? (isWin ? '.venv\\Scripts\\python.exe' : '.venv/bin/python')
const launchOptions = base.use?.launchOptions

export default defineConfig({
  testDir: './e2e-pwa',
  timeout: 120_000,
  workers: 1,
  reporter: process.env.CI ? [['list'], ['html', { open: 'never', outputFolder: 'playwright-report-pwa' }]] : 'list',
  use: { baseURL: 'http://localhost:4173', trace: 'retain-on-failure', serviceWorkers: 'allow', launchOptions },
  projects: [{ name: 'chromium-pwa', use: { ...devices['Desktop Chrome'], launchOptions } }],
  webServer: [
    {
      command: `${python} -m uvicorn app.main:app --port 8000`,
      cwd: '../backend',
      url: 'http://localhost:8000/health',
      env: {
        DATABASE_URL: 'sqlite:///./storage/e2e.db',
        EMBEDDINGS_ENABLED: 'false',
        CORS_ORIGINS: 'http://localhost:4173,http://127.0.0.1:4173,http://localhost:5173',
      },
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
    {
      command: 'npx vite build && npx vite preview --port 4173 --strictPort',
      url: 'http://localhost:4173',
      reuseExistingServer: !process.env.CI,
      timeout: 240_000,
    },
  ],
})
