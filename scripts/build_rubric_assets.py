"""Draw the rubric anchor images (SYNTHETIC) shown to assessors next to the 0-3 scale.

Writes frontend/public/rubric/{good,porosity,undercut,spatter,incomplete}.jpg using the
seeded weld generator, so the images are reproducible. Each image gets a small
'SYNTHETIC' caption so it can never be mistaken for real evidence.

Usage:  python scripts/build_rubric_assets.py
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "frontend" / "public" / "rubric"

EXAMPLES = {
    "good": ("good", 0),
    "porosity": ("porosity", 2),
    "undercut": ("undercut", 2),
    "spatter": ("spatter", 2),
    "incomplete": ("incomplete", 2),
}


def main() -> None:
    spec = importlib.util.spec_from_file_location("gen", ROOT / "scripts" / "generate_synthetic.py")
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    OUT.mkdir(parents=True, exist_ok=True)
    for i, (name, (defect, severity)) in enumerate(EXAMPLES.items()):
        img = gen.draw_weld(np.random.default_rng(1000 + i), defect, severity)
        cv2.rectangle(img, (0, 232), (256, 256), (77, 31, 11), -1)  # navy, in BGR
        cv2.putText(
            img,
            f"SYNTHETIC - {name}",
            (6, 249),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )
        cv2.imwrite(str(OUT / f"{name}.jpg"), img, [cv2.IMWRITE_JPEG_QUALITY, 88])
    print(f"wrote {len(EXAMPLES)} rubric images -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
