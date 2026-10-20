// Lite mode launcher: API (uvicorn) + PWA (vite) together, on Windows, macOS and Linux.
//   npm run lite        (from the repo root)
// Ctrl+C stops both. No Docker, no database server: SQLite + local files.
import { spawn } from 'node:child_process'
import { existsSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = join(dirname(fileURLToPath(import.meta.url)), '..')
const isWin = process.platform === 'win32'
const python = join(root, 'backend', '.venv', isWin ? 'Scripts/python.exe' : 'bin/python')
if (!existsSync(python)) {
  console.error(`[lite] ${python} not found. Run "npm run setup" first.`)
  process.exit(1)
}

const procs = [
  ['api', python, ['-m', 'uvicorn', 'app.main:app', '--reload', '--port', '8000'], join(root, 'backend')],
  ['web', process.execPath, [join(root, 'frontend', 'node_modules', 'vite', 'bin', 'vite.js')], join(root, 'frontend')],
].map(([name, cmd, args, cwd]) => {
  const p = spawn(cmd, args, { cwd, stdio: ['ignore', 'pipe', 'pipe'] })
  const tag = (chunk) =>
    chunk
      .toString()
      .split(/\r?\n/)
      .filter(Boolean)
      .forEach((line) => console.log(`[${name}] ${line}`))
  p.stdout.on('data', tag)
  p.stderr.on('data', tag)
  p.on('exit', (code) => {
    console.log(`[${name}] exited (${code})`)
    shutdown()
  })
  return p
})

let stopping = false
function shutdown() {
  if (stopping) return
  stopping = true
  for (const p of procs) if (p.exitCode === null) p.kill()
  setTimeout(() => process.exit(0), 500)
}
process.on('SIGINT', shutdown)
process.on('SIGTERM', shutdown)
console.log('[lite] API http://localhost:8000/docs   PWA http://localhost:5173   (Ctrl+C to stop)')
