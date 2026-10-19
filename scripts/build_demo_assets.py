"""Draw the SYNTHETIC images the frontend ships with.

  frontend/public/rubric/{good,porosity,undercut,spatter,incomplete}.jpg
      rubric anchors shown to assessors next to the 0-3 scale
  frontend/public/samples/weld_XX_<defect>.jpg  (+ index.json)
      12 distinct 'Product' sample photos for demoing capture on a laptop without a camera

All images come from the seeded weld generator (reproducible) and carry a visible
'SYNTHETIC' caption, so they can never be mistaken for real evidence.

Usage:  python scripts/build_demo_assets.py
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
RUBRIC = ROOT / "frontend" / "public" / "rubric"
SAMPLES = ROOT / "frontend" / "public" / "samples"

RUBRIC_EXAMPLES = {
    "good": ("good", 0),
    "porosity": ("porosity", 2),
    "undercut": ("undercut", 2),
    "spatter": ("spatter", 2),
    "incomplete": ("incomplete", 2),
}
SAMPLE_PLAN = [("good", 0)] * 4 + [
    ("porosity", 2),
    ("porosity", 1),
    ("undercut", 2),
    ("undercut", 1),
    ("spatter", 2),
    ("spatter", 1),
    ("incomplete", 2),
    ("incomplete", 1),
]


def _generator():
    spec = importlib.util.spec_from_file_location("gen", ROOT / "scripts" / "generate_synthetic.py")
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    return gen


def _caption(img: np.ndarray, text: str) -> np.ndarray:
    cv2.rectangle(img, (0, 232), (256, 256), (77, 31, 11), -1)  # navy, in BGR
    cv2.putText(
        img,
        text,
        (6, 249),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.45,
        (255, 255, 255),
        1,
        cv2.LINE_AA,
    )
    return img


def main() -> None:
    gen = _generator()
    RUBRIC.mkdir(parents=True, exist_ok=True)
    for i, (name, (defect, severity)) in enumerate(RUBRIC_EXAMPLES.items()):
        img = _caption(
            gen.draw_weld(np.random.default_rng(1000 + i), defect, severity),
            f"SYNTHETIC - {name}",
        )
        cv2.imwrite(str(RUBRIC / f"{name}.jpg"), img, [cv2.IMWRITE_JPEG_QUALITY, 88])

    SAMPLES.mkdir(parents=True, exist_ok=True)
    index = []
    for i, (defect, severity) in enumerate(SAMPLE_PLAN):
        img = gen.draw_weld(np.random.default_rng(5000 + i), defect, severity)
        name = f"weld_{i:02d}_{defect}.jpg"
        cv2.imwrite(
            str(SAMPLES / name),
            _caption(img, f"SYNTHETIC sample {i:02d}"),
            [cv2.IMWRITE_JPEG_QUALITY, 90],
        )
        index.append({"file": f"/samples/{name}", "defect": defect, "severity": severity})
    (SAMPLES / "index.json").write_text(json.dumps(index, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {len(RUBRIC_EXAMPLES)} rubric images and {len(index)} product samples")


if __name__ == "__main__":
    main()
