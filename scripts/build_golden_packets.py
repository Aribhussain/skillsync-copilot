"""Build the 10 SYNTHETIC golden (pre-graded calibration) packets.

Writes data/golden_packets/golden_packets.json and data/golden_packets/images/GP-XX.jpg.
Each packet is a Welding product photo plus consensus scores for the 14 PCs that are judged
from the product photo. The consensus is derived from the generator's ground truth
(defect + severity) with the rubric rule below, so it is a SYNTHETIC consensus, not one
agreed by a panel of real assessors.

Rule per PC ai_signal:  good weld -> 3;  'overall' -> quality level;  signal == defect ->
quality level;  otherwise -> 2.

Usage:  python scripts/build_golden_packets.py
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.qp_store import iter_pcs, load_corpus

OUT = ROOT / "data" / "golden_packets"
WELDING = "QG-4.5-AU-01811-2024-V1-ASDC"
PLAN = [
    ("good", 0),
    ("good", 0),
    ("porosity", 2),
    ("porosity", 1),
    ("undercut", 2),
    ("undercut", 1),
    ("spatter", 2),
    ("spatter", 1),
    ("incomplete", 2),
    ("incomplete", 1),
]


def main() -> None:
    spec = importlib.util.spec_from_file_location("gen", ROOT / "scripts" / "generate_synthetic.py")
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    image_pcs = [p for p in iter_pcs(load_corpus()[WELDING]) if p["ai_signal"]]
    (OUT / "images").mkdir(parents=True, exist_ok=True)
    packets = []
    for i, (defect, sev) in enumerate(PLAN, start=1):
        pid = f"GP-{i:02d}"
        img = gen.draw_weld(np.random.default_rng(7000 + i), defect, sev)
        cv2.imwrite(str(OUT / "images" / f"{pid}.jpg"), img, [cv2.IMWRITE_JPEG_QUALITY, 92])
        q = gen.quality_level(defect, sev)
        consensus = {}
        for pc in image_pcs:
            s = pc["ai_signal"]
            consensus[pc["id"]] = 3 if defect == "good" else q if s in ("overall", defect) else 2
        packets.append(
            {
                "id": pid,
                "qp_id": WELDING,
                "image": f"images/{pid}.jpg",
                "defect": defect,
                "severity": sev,
                "consensus": consensus,
            }
        )
    doc = {
        "synthetic": True,
        "note": "SYNTHETIC consensus derived from generator ground truth",
        "packets": packets,
    }
    (OUT / "golden_packets.json").write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {len(packets)} golden packets x {len(image_pcs)} PCs -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
