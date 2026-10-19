import { describe, expect, it } from 'vitest'

import { analyseGray, centreEdgeShare, laplacianVariance } from './imageQc'

/** Deterministic test pattern: a textured, centred bright bar on a mid-grey plate. */
function pattern(w: number, h: number, base = 120): Float32Array {
  const g = new Float32Array(w * h)
  for (let y = 0; y < h; y++)
    for (let x = 0; x < w; x++) {
      const inBar = y > h * 0.4 && y < h * 0.6 && x > w * 0.25 && x < w * 0.75
      const ripple = inBar && x % 6 < 3 ? 60 : 0
      g[y * w + x] = base + (inBar ? 50 : 0) + ripple + (((x * 7 + y * 13) % 5) - 2)
    }
  return g
}

function boxBlur(g: Float32Array, w: number, h: number, r: number): Float32Array {
  const out = new Float32Array(g.length)
  for (let y = 0; y < h; y++)
    for (let x = 0; x < w; x++) {
      let s = 0
      let n = 0
      for (let dy = -r; dy <= r; dy++)
        for (let dx = -r; dx <= r; dx++) {
          const yy = Math.min(h - 1, Math.max(0, y + dy))
          const xx = Math.min(w - 1, Math.max(0, x + dx))
          s += g[yy * w + xx]
          n++
        }
      out[y * w + x] = s / n
    }
  return out
}

describe('capture quality checks', () => {
  const W = 160
  const H = 120

  it('accepts a sharp, well-lit, centred image', () => {
    const r = analyseGray(pattern(W, H), W, H, 640, 480)
    expect(r.issues).toEqual([])
    expect(r.ok).toBe(true)
  })

  it('flags blur ("hold steady")', () => {
    const sharp = pattern(W, H)
    const blurred = boxBlur(sharp, W, H, 4)
    expect(laplacianVariance(blurred, W, H)).toBeLessThan(laplacianVariance(sharp, W, H) / 10)
    expect(analyseGray(blurred, W, H, 640, 480).issues).toContain('blur')
  })

  it('flags too dark and too bright', () => {
    expect(analyseGray(pattern(W, H, 5), W, H, 640, 480).issues).toContain('dark')
    expect(analyseGray(pattern(W, H, 200).map((v) => Math.min(255, v + 40)), W, H, 640, 480).issues).toContain('bright')
  })

  it('flags an off-centre subject', () => {
    // subject pushed into the top-left corner
    const g = new Float32Array(W * H).fill(120)
    for (let y = 0; y < 20; y++) for (let x = 0; x < 30; x++) g[y * W + x] = x % 4 < 2 ? 230 : 40
    expect(centreEdgeShare(g, W, H)).toBeLessThan(0.25)
    expect(analyseGray(g, W, H, 640, 480).issues).toContain('framing')
  })

  it('flags images that are too small', () => {
    expect(analyseGray(pattern(W, H), W, H, 200, 150).issues).toContain('small')
  })
})
