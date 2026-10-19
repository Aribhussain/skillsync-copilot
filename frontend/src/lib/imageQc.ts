/**
 * On-device capture quality checks (no network, runs in a few ms on a phone).
 *  - blur:       variance of the 4-neighbour Laplacian on a <=320 px grayscale copy
 *  - brightness: mean gray level
 *  - framing:    share of edge energy inside the central 60% box (is the subject centred?)
 *  - size:       minimum resolution
 * Thresholds were calibrated on our synthetic weld images (sharp 15-37, blurred < 2.5);
 * they need field calibration on real phone photos.
 */

export const QC_THRESHOLDS = {
  minLaplacianVar: 8,
  minBrightness: 45,
  maxBrightness: 220,
  minCentreEdgeShare: 0.25,
  minSide: 240,
  maxSide: 320, // analysis size
}

export type QcIssue = 'blur' | 'dark' | 'bright' | 'framing' | 'small'

export interface QcResult {
  ok: boolean
  issues: QcIssue[]
  metrics: { laplacianVar: number; brightness: number; centreEdgeShare: number; width: number; height: number }
}

export function toGray(data: Uint8ClampedArray, w: number, h: number): Float32Array {
  const g = new Float32Array(w * h)
  for (let i = 0, p = 0; i < g.length; i++, p += 4) g[i] = 0.299 * data[p] + 0.587 * data[p + 1] + 0.114 * data[p + 2]
  return g
}

/** Laplacian response over interior pixels (border excluded). */
function laplacian(g: Float32Array, w: number, h: number): Float32Array {
  const out = new Float32Array((w - 2) * (h - 2))
  let k = 0
  for (let y = 1; y < h - 1; y++) {
    for (let x = 1; x < w - 1; x++) {
      const i = y * w + x
      out[k++] = g[i - w] + g[i + w] + g[i - 1] + g[i + 1] - 4 * g[i]
    }
  }
  return out
}

export function laplacianVariance(g: Float32Array, w: number, h: number): number {
  const l = laplacian(g, w, h)
  if (!l.length) return 0
  let mean = 0
  for (const v of l) mean += v
  mean /= l.length
  let s = 0
  for (const v of l) s += (v - mean) ** 2
  return s / l.length
}

export function meanBrightness(g: Float32Array): number {
  let s = 0
  for (const v of g) s += v
  return g.length ? s / g.length : 0
}

function percentile(sorted: Float32Array, p: number): number {
  if (!sorted.length) return 0
  return sorted[Math.min(sorted.length - 1, Math.floor((p / 100) * (sorted.length - 1)))]
}

/**
 * Share of edge energy inside the central 60% box. Edge magnitudes are clipped at the
 * 95th percentile (so a few very strong edges, e.g. printed text or glare, can't dominate)
 * and the median is subtracted as a noise floor.
 * Known limitation: a small off-centre subject on a *noisy* background is not detected.
 */
export function centreEdgeShare(g: Float32Array, w: number, h: number): number {
  const l = laplacian(g, w, h).map(Math.abs)
  const sorted = Float32Array.from(l).sort()
  const clip = percentile(sorted, 95)
  const floor = percentile(sorted, 50)
  const iw = w - 2
  const x0 = Math.floor(iw * 0.2)
  const x1 = Math.ceil(iw * 0.8)
  const y0 = Math.floor((h - 2) * 0.2)
  const y1 = Math.ceil((h - 2) * 0.8)
  let total = 0
  let centre = 0
  for (let y = 0; y < h - 2; y++) {
    for (let x = 0; x < iw; x++) {
      const e = Math.max(0, Math.min(l[y * iw + x], clip) - floor)
      total += e
      if (x >= x0 && x < x1 && y >= y0 && y < y1) centre += e
    }
  }
  return total > 0 ? centre / total : 0
}

/** Analyse grayscale pixels (already downscaled). `origW/H` = original resolution. */
export function analyseGray(g: Float32Array, w: number, h: number, origW: number, origH: number): QcResult {
  const T = QC_THRESHOLDS
  const metrics = {
    laplacianVar: laplacianVariance(g, w, h),
    brightness: meanBrightness(g),
    centreEdgeShare: centreEdgeShare(g, w, h),
    width: origW,
    height: origH,
  }
  const issues: QcIssue[] = []
  if (Math.min(origW, origH) < T.minSide) issues.push('small')
  if (metrics.brightness < T.minBrightness) issues.push('dark')
  if (metrics.brightness > T.maxBrightness) issues.push('bright')
  if (metrics.laplacianVar < T.minLaplacianVar) issues.push('blur')
  if (metrics.centreEdgeShare < T.minCentreEdgeShare) issues.push('framing')
  return { ok: issues.length === 0, issues, metrics }
}

/** Browser entry point: downscale with a canvas, then analyse. */
export async function analyseImage(source: ImageBitmap | HTMLCanvasElement | HTMLImageElement): Promise<QcResult> {
  const origW = 'naturalWidth' in source ? source.naturalWidth : source.width
  const origH = 'naturalHeight' in source ? source.naturalHeight : source.height
  const scale = Math.min(1, QC_THRESHOLDS.maxSide / Math.max(origW, origH))
  const w = Math.max(3, Math.round(origW * scale))
  const h = Math.max(3, Math.round(origH * scale))
  const canvas = document.createElement('canvas')
  canvas.width = w
  canvas.height = h
  const ctx = canvas.getContext('2d', { willReadFrequently: true })
  if (!ctx) throw new Error('Canvas 2D not available')
  ctx.drawImage(source, 0, 0, w, h)
  const { data } = ctx.getImageData(0, 0, w, h)
  return analyseGray(toGray(data, w, h), w, h, origW, origH)
}
