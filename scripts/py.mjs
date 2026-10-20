// Run the backend venv's Python on any OS:  node scripts/py.mjs <args...>
// (npm scripts use it so Windows and macOS/Linux share one command.)
import { spawnSync } from 'node:child_process'
import { existsSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = join(dirname(fileURLToPath(import.meta.url)), '..')
const python = join(root, 'backend', '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python')
if (!existsSync(python)) {
  console.error(`[py] ${python} not found. Run "npm run setup" first.`)
  process.exit(1)
}
const r = spawnSync(python, process.argv.slice(2), { stdio: 'inherit', cwd: process.cwd() })
process.exit(r.status ?? 1)
