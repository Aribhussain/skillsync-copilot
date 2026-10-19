/**
 * SIMULATED captures for demoing on a laptop without a camera. Every image is visibly
 * stamped "SIMULATED", so it can never pass as real evidence.
 *  - process: a drawn workbench with PPE items
 *  - person:  a silhouette holding a slate showing the one-time challenge code
 *  - product: one of the bundled synthetic weld photos (public/samples)
 */

function rng(seed: number) {
  let s = seed >>> 0 || 1
  return () => {
    s = (s * 1664525 + 1013904223) >>> 0
    return s / 2 ** 32
  }
}

function hashString(s: string): number {
  let h = 2166136261
  for (let i = 0; i < s.length; i++) h = Math.imul(h ^ s.charCodeAt(i), 16777619)
  return h >>> 0
}

function canvas(w = 640, h = 480): [HTMLCanvasElement, CanvasRenderingContext2D] {
  const c = document.createElement('canvas')
  c.width = w
  c.height = h
  const ctx = c.getContext('2d')
  if (!ctx) throw new Error('Canvas 2D not available')
  return [c, ctx]
}

function noise(ctx: CanvasRenderingContext2D, r: () => number, w: number, h: number) {
  for (let i = 0; i < 1800; i++) {
    ctx.fillStyle = `rgba(${Math.floor(r() * 255)},${Math.floor(r() * 255)},${Math.floor(r() * 255)},0.12)`
    ctx.fillRect(r() * w, r() * h, 2, 2)
  }
}

function stamp(ctx: CanvasRenderingContext2D, text: string, w: number, h: number) {
  ctx.fillStyle = 'rgba(11,31,77,0.85)'
  ctx.fillRect(0, h - 34, w, 34)
  ctx.fillStyle = '#fff'
  ctx.font = 'bold 18px sans-serif'
  ctx.fillText(text, 12, h - 11)
}

export function drawProcessSample(seedKey: string): HTMLCanvasElement {
  const r = rng(hashString(`process:${seedKey}`))
  const [c, ctx] = canvas()
  const g = ctx.createLinearGradient(0, 0, 0, 480)
  g.addColorStop(0, `hsl(${200 + r() * 40}, 20%, ${55 + r() * 15}%)`)
  g.addColorStop(1, `hsl(${30 + r() * 20}, 25%, 35%)`)
  ctx.fillStyle = g
  ctx.fillRect(0, 0, 640, 480)
  noise(ctx, r, 640, 480)
  // workbench
  ctx.fillStyle = '#6b4a2b'
  ctx.fillRect(60, 300, 520, 40)
  ctx.fillRect(90, 340, 24, 110)
  ctx.fillRect(526, 340, 24, 110)
  // welding machine
  ctx.fillStyle = '#c0392b'
  ctx.fillRect(120 + r() * 40, 200, 150, 100)
  ctx.fillStyle = '#222'
  ctx.fillRect(140 + r() * 30, 220, 40, 30)
  // plate on the bench
  ctx.fillStyle = '#9aa3ad'
  ctx.fillRect(330, 280, 180, 20)
  // PPE
  ctx.font = '64px serif'
  ctx.fillText('⛑️', 360 + r() * 60, 250)
  ctx.fillText('🧤', 470 + r() * 30, 250)
  ctx.fillText('🥽', 300 + r() * 20, 200)
  stamp(ctx, 'SIMULATED · Process: set-up + PPE', 640, 480)
  return c
}

export function drawPersonSample(seedKey: string, challengeCode: string): HTMLCanvasElement {
  const r = rng(hashString(`person:${seedKey}:${challengeCode}`))
  const [c, ctx] = canvas()
  ctx.fillStyle = `hsl(${r() * 360}, 18%, ${62 + r() * 12}%)`
  ctx.fillRect(0, 0, 640, 480)
  noise(ctx, r, 640, 480)
  // silhouette (no face details: no face templates are created or stored)
  ctx.fillStyle = '#2b2b2b'
  ctx.beginPath()
  ctx.arc(320, 120, 55, 0, Math.PI * 2)
  ctx.fill()
  ctx.fillRect(235, 180, 170, 220)
  // slate with the challenge code
  ctx.fillStyle = '#1d2b22'
  ctx.fillRect(200, 250, 240, 110)
  ctx.strokeStyle = '#8b5a2b'
  ctx.lineWidth = 10
  ctx.strokeRect(200, 250, 240, 110)
  ctx.fillStyle = '#f5f5f5'
  ctx.font = 'bold 56px monospace'
  ctx.textAlign = 'center'
  ctx.fillText(challengeCode, 320, 325)
  ctx.textAlign = 'start'
  stamp(ctx, `SIMULATED · Person + slate · ${new Date().toISOString().slice(0, 16)}`, 640, 480)
  return c
}

export interface ProductSample {
  file: string
  defect: string
  severity: number
}

export async function productSamples(): Promise<ProductSample[]> {
  const res = await fetch('/samples/index.json')
  return res.ok ? ((await res.json()) as ProductSample[]) : []
}

export async function loadImage(src: string): Promise<HTMLImageElement> {
  const img = new Image()
  img.decoding = 'async'
  img.src = src
  await img.decode()
  return img
}

export function canvasToBlob(c: HTMLCanvasElement, quality = 0.9): Promise<Blob> {
  return new Promise((resolve, reject) =>
    c.toBlob((b) => (b ? resolve(b) : reject(new Error('toBlob failed'))), 'image/jpeg', quality),
  )
}

export async function imageToCanvas(img: HTMLImageElement | ImageBitmap): Promise<HTMLCanvasElement> {
  const w = 'naturalWidth' in img ? img.naturalWidth : img.width
  const h = 'naturalHeight' in img ? img.naturalHeight : img.height
  const [c, ctx] = canvas(w, h)
  ctx.drawImage(img, 0, 0)
  return c
}
