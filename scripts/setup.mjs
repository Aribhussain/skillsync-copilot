// One-time setup for lite mode: backend venv + deps, frontend deps, .env from the example.
//   npm run setup        (from the repo root; needs Python 3.11+ and Node 20.19+ / 22.12+)
// Never downloads Playwright browsers (PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1).
import { execFileSync } from 'node:child_process'
import { copyFileSync, existsSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = join(dirname(fileURLToPath(import.meta.url)), '..')
const isWin = process.platform === 'win32'
const run = (cmd, args, cwd = root, env = {}) => {
  console.log(`[setup] ${cmd} ${args.join(' ')}`)
  execFileSync(cmd, args, { cwd, stdio: 'inherit', shell: isWin, env: { ...process.env, ...env } })
}

const venv = join(root, 'backend', '.venv')
const python = join(venv, isWin ? 'Scripts/python.exe' : 'bin/python')
if (!existsSync(python)) run(isWin ? 'py' : 'python3', [...(isWin ? ['-3.11'] : []), '-m', 'venv', venv])
run(python, ['-m', 'pip', 'install', '-r', 'requirements.txt', '-r', 'requirements-dev.txt'], join(root, 'backend'))
run(isWin ? 'npm.cmd' : 'npm', ['ci'], join(root, 'frontend'), { PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD: '1' })
if (!existsSync(join(root, '.env'))) {
  copyFileSync(join(root, '.env.example'), join(root, '.env'))
  console.log('[setup] created .env from .env.example (edit JWT_SECRET for anything beyond a demo)')
}
console.log('[setup] done. Optional: pip install -r backend/requirements-embeddings.txt (~1 GB, multilingual re-rank)')
console.log('[setup] start with: npm run lite')
