"""Train the DEMO shadow-rater model on SYNTHETIC weld images and write a report.

  ml/models/shadow_rater.joblib          (git-ignored build artefact)
  docs/results/shadow_rater.md / .json   (metrics, honestly labelled)

The model is a pair of RandomForests over classical OpenCV features
(backend/app/ml/weld_features.py) behind the ShadowRater interface
(backend/app/ml/shadow_rater.py), so a ViT/ONNX model can be swapped in later.

Usage:  python ml/train_shadow_rater.py [--per-class 120] [--seed 26242]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import joblib

from app.ml.shadow_rater import DEFECTS, MODEL_LABEL, MODEL_PATH, DemoForestRater, train
from app.ml.weld_features import extract_from_bytes

OUT_MD = ROOT / "docs" / "results" / "shadow_rater.md"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-class", type=int, default=120)
    ap.add_argument("--seed", type=int, default=26242)
    args = ap.parse_args()

    bundle = train(seed=args.seed, per_class=args.per_class)
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, MODEL_PATH)
    m = bundle["metrics"]

    # The bundled demo samples (captioned) as a sanity check of the caption crop.
    rater = DemoForestRater(bundle)
    samples = json.loads(
        (ROOT / "frontend" / "public" / "samples" / "index.json").read_text(encoding="utf-8")
    )
    sample_rows = []
    for s in samples:
        data = (ROOT / "frontend" / "public" / s["file"].lstrip("/")).read_bytes()
        a = rater.analyse_features(extract_from_bytes(data))
        sample_rows.append(
            (s["file"].split("/")[-1], s["defect"], a.defect, a.level, a.defect_probs[a.defect])
        )
    sample_acc = sum(1 for r in sample_rows if r[1] == r[2]) / len(sample_rows)

    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    (OUT_MD.with_suffix(".json")).write_text(
        json.dumps({**m, "samples_accuracy": sample_acc}, indent=1) + "\n"
    )
    cm = m["defect_confusion_holdout"]["matrix"]
    lines = [
        "# Shadow rater — demo model",
        "",
        f"> **{MODEL_LABEL}.** Trained and evaluated on procedurally drawn weld images only. "
        "These numbers say the pipeline works end to end. They do **not** say how the model would do "
        "on real welds.",
        "",
        f"- Model: `{bundle['version']}`, two RandomForests (defect class, quality level 0–3) over "
        f"{len(bundle['features'])} OpenCV features",
        f"- Training data: {m['train_size']} synthetic images, with a {m['test_size']}-image hold-out "
        "from the same generator run",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Defect accuracy (hold-out) | {m['defect_accuracy_holdout']:.1%} |",
        f"| Quality level accuracy (hold-out) | {m['level_accuracy_holdout']:.1%} |",
        f"| Quality level within ±1 (hold-out) | {m['level_within_one_holdout']:.1%} |",
        f"| Defect accuracy (freshly generated, new seed) | {m['defect_accuracy_new_seed']:.1%} |",
        f"| Quality level accuracy (new seed) | {m['level_accuracy_new_seed']:.1%} |",
        f"| Defect accuracy on the 12 bundled demo samples (captioned) | {sample_acc:.1%} |",
        "",
        "## Confusion matrix (hold-out, rows = true, columns = predicted)",
        "",
        "| | " + " | ".join(DEFECTS) + " |",
        "|---" * (len(DEFECTS) + 1) + "|",
    ]
    for label, row in zip(DEFECTS, cm, strict=True):
        lines.append(f"| **{label}** | " + " | ".join(str(v) for v in row) + " |")
    lines += ["", "## Feature importance (defect model)", "", "| Feature | Importance |", "|---|---|"]
    lines += [f"| {k} | {v:.3f} |" for k, v in m["feature_importance"].items()]
    lines += [
        "",
        "## Bundled demo samples",
        "",
        "| Sample | True | Predicted | Level | p |",
        "|---|---|---|---|---|",
    ]
    lines += [f"| {f} | {t} | {p} | {lv} | {pr:.2f} |" for f, t, p, lv, pr in sample_rows]
    lines += [
        "",
        "## Limits",
        "",
        "- The synthetic generator draws every defect in one stylised way, so near-perfect scores are "
        "expected and uninformative about real welds, lighting, angles and metals.",
        "- In the product the model is a **second opinion shown only after the assessor's blind "
        "score**. It never decides a score. Real deployment needs a model trained on labelled field "
        "photos, swapped in behind the `ShadowRater` interface.",
        "",
    ]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({k: v for k, v in m.items() if not isinstance(v, dict)}, indent=1))
    print(f"samples accuracy: {sample_acc:.1%}")
    print(f"saved {MODEL_PATH.relative_to(ROOT)} and {OUT_MD.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
