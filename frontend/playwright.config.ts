import { existsSync } from 'node:fs'
import path from 'node:path'

import { defineConfig, devices } from '@playwright/test'

/**
 * Local runs drive an installed Chromium-based browser (Brave) instead of downloading one:
 *   PLAYWRIGHT_BROWSER_PATH (env)  ->  Program Files Brave  ->  per-user Brave install.
 * `launch()` with an executablePath always uses a fresh temporary profile, never the
 * personal browser profile. In CI (no Brave) we fall back to Playwright's own Chromium,
 * installed there with `npx playwright install chromium`.
 */
function resolveBrowser(): string | undefined {
  const candidates = [
    process.env.PLAYWRIGHT_BROWSER_PATH,
    'C:\\Program Files\\BraveSoftware\\Brave-Browser\\Application\\brave.exe',
    process.env.LOCALAPPDATA
      ? path.join(process.env.LOCALAPPDATA, 'BraveSoftware', 'Brave-Browser', 'Application', 'brave.exe')
      : undefined,
  ]
  return candidates.find((p): p is string => !!p && existsSync(p))
}

const executablePath = process.env.CI ? undefined : resolveBrowser()
const isWin = process.platform === 'win32'
const python =
  process.env.BACKEND_PYTHON ?? (isWin ? '.venv\\Scripts\\python.exe' : '.venv/bin/python')

// e2e uses its own database so it never touches your dev data.
const backendEnv = {
  DATABASE_URL: 'sqlite:///./storage/e2e.db',
  EMBEDDINGS_ENABLED: 'false',
  APP_ENV: 'development',
}

export default defineConfig({
  testDir: './e2e',
  timeout: 60_000,
  fullyParallel: false,
  workers: 1,
  reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : 'list',
  use: {
    baseURL: 'http://localhost:5173',
    trace: 'retain-on-failure',
    launchOptions: { executablePath, channel: undefined },
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'], launchOptions: { executablePath } } }],
  webServer: [
    {
      command: `${python} -m uvicorn app.main:app --port 8000`,
      cwd: '../backend',
      url: 'http://localhost:8000/health',
      env: backendEnv,
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
    {
      command: 'npx vite --port 5173',
      url: 'http://localhost:5173',
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
  ],
})
