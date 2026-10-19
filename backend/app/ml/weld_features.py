"""Classical, explainable weld-image features (OpenCV) for the DEMO shadow rater.

Pipeline: grayscale -> drop the bottom 12% (where demo captions live) -> Otsu threshold
-> largest bright component = bead -> rotate the bead to horizontal (PCA) -> measure:

  coverage        fraction of the bead's length that is actually welded (gaps -> incomplete)
  gaps            number of breaks along the bead
  width_cv        coefficient of variation of bead width
  pores           dark blobs inside the bead (porosity)
  pore_area       their total area relative to the bead
  toe_dark        darkness of the band just outside the bead edges (undercut groove)
  toe_dark_run    longest run of dark toe columns relative to bead length
  spatter         small blobs on the plate away from the bead
  bead_contrast   bead vs plate brightness
  lap_var         Laplacian variance (texture / sharpness)
  bead_area       bead area relative to the image

The features are deliberately simple: this is a demo model trained on SYNTHETIC images.
A production rater would be a CNN/ViT trained on real labelled welds behind the same
ShadowRater interface.
"""

from __future__ import annotations

import cv2
import numpy as np

FEATURE_NAMES = [
    "coverage",
    "gaps",
    "width_cv",
    "pores",
    "pore_area",
    "toe_dark",
    "toe_dark_run",
    "spatter",
    "bead_contrast",
    "lap_var",
    "bead_area",
]


def _decode(data: bytes) -> np.ndarray:
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise ValueError("Not a decodable image")
    return img


def _prepare(gray: np.ndarray) -> np.ndarray:
    h = gray.shape[0]
    gray = gray[: int(h * 0.88)]
    scale = 256 / max(gray.shape)
    if scale < 1:
        gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    return gray


def _bead_mask(gray: np.ndarray) -> np.ndarray:
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    _, th = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    th = cv2.morphologyEx(th, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    n, labels, stats, _ = cv2.connectedComponentsWithStats(th)
    if n <= 1:
        return np.zeros_like(gray, np.uint8)
    # bead = the components forming the dominant bright elongated structure: keep the largest
    # plus any component of comparable brightness on the same line (gapped beads).
    areas = stats[1:, cv2.CC_STAT_AREA]
    keep = 1 + np.flatnonzero(areas >= max(40, 0.04 * areas.max()))
    return np.isin(labels, keep).astype(np.uint8) * 255


def _rotate_horizontal(gray: np.ndarray, mask: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    ys, xs = np.nonzero(mask)
    if len(xs) < 20:
        return gray, mask
    pts = np.column_stack([xs, ys]).astype(np.float32)
    mean = pts.mean(axis=0)
    _, vecs = np.linalg.eigh(np.cov((pts - mean).T))
    major = vecs[:, -1]
    angle = np.degrees(np.arctan2(major[1], major[0]))
    m = cv2.getRotationMatrix2D((float(mean[0]), float(mean[1])), angle, 1.0)
    size = (gray.shape[1], gray.shape[0])
    g2 = cv2.warpAffine(gray, m, size, flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    m2 = cv2.warpAffine(mask, m, size, flags=cv2.INTER_NEAREST, borderValue=0)
    return g2, m2


def _runs(bool_arr: np.ndarray) -> list[int]:
    runs, cur = [], 0
    for v in bool_arr:
        if v:
            cur += 1
        elif cur:
            runs.append(cur)
            cur = 0
    if cur:
        runs.append(cur)
    return runs


def extract(gray: np.ndarray) -> dict[str, float]:
    gray = _prepare(gray)
    mask = _bead_mask(gray)
    g, m = _rotate_horizontal(gray, mask)
    feats = dict.fromkeys(FEATURE_NAMES, 0.0)
    feats["lap_var"] = float(cv2.Laplacian(g, cv2.CV_32F).var())
    cols = m.sum(axis=0) > 0
    if cols.sum() < 10:
        return feats  # no bead found: everything else stays 0
    x0, x1 = np.flatnonzero(cols)[[0, -1]]
    span = cols[x0 : x1 + 1]
    feats["coverage"] = float(span.mean())
    feats["gaps"] = float(sum(1 for r in _runs(~span) if r >= 3))
    rows_per_col = (m[:, x0 : x1 + 1] > 0).sum(axis=0)[span]
    feats["width_cv"] = float(rows_per_col.std() / max(rows_per_col.mean(), 1))
    bead = m > 0
    bead_px = g[bead].astype(np.float32)
    plate_mask = cv2.dilate(m, np.ones((15, 15), np.uint8)) == 0
    plate_px = g[plate_mask].astype(np.float32)
    plate_mean = float(np.median(plate_px)) if plate_px.size else 0.0
    feats["bead_contrast"] = float(np.median(bead_px) - plate_mean)
    feats["bead_area"] = float(bead.mean())

    # porosity: dark spots strictly inside the (eroded) bead
    inner = cv2.erode(m, np.ones((5, 5), np.uint8)) > 0
    dark = ((g.astype(np.float32) < np.median(bead_px) - 60) & inner).astype(np.uint8)
    n, _, stats, _ = cv2.connectedComponentsWithStats(dark)
    pores = [a for a in stats[1:, cv2.CC_STAT_AREA] if a >= 2]
    feats["pores"] = float(len(pores))
    feats["pore_area"] = float(sum(pores) / max(bead.sum(), 1))

    # undercut: dark band just outside the bead edges (per column, above or below)
    ring = (cv2.dilate(m, np.ones((9, 9), np.uint8)) > 0) & ~bead
    toe = np.where(ring, g, 255).astype(np.float32)
    toe_cols = (toe < plate_mean - 45).sum(axis=0)[x0 : x1 + 1] >= 2
    feats["toe_dark"] = float(toe_cols.mean())
    feats["toe_dark_run"] = float(max(_runs(toe_cols), default=0) / len(span))

    # spatter: small blobs on the plate far from the bead
    far = cv2.dilate(m, np.ones((21, 21), np.uint8)) == 0
    diff = np.abs(g.astype(np.float32) - cv2.medianBlur(g, 9).astype(np.float32))
    blobs = ((diff > 35) & far).astype(np.uint8)
    n, _, stats, _ = cv2.connectedComponentsWithStats(blobs)
    feats["spatter"] = float(sum(1 for a in stats[1:, cv2.CC_STAT_AREA] if 1 <= a <= 40))
    return feats


def extract_from_bytes(data: bytes) -> dict[str, float]:
    return extract(_decode(data))


def vector(feats: dict[str, float]) -> np.ndarray:
    return np.array([feats[k] for k in FEATURE_NAMES], dtype=np.float32)
