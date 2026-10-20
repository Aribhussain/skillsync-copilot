"""M5 — AI shadow rater (DEMO model trained on SYNTHETIC weld images).

`ShadowRater` is the interface the scoring API depends on, so a production model (e.g. a
ViT/CNN exported to ONNX and trained on real labelled welds) can replace
`DemoForestRater` without touching the blind-first workflow.

The demo model has two scikit-learn RandomForests over the classical features in
`weld_features.py`:
  - defect classifier: good | porosity | undercut | spatter | incomplete
  - quality-level classifier: 0..3 (the same 0-3 rubric scale assessors use)
Per-PC suggestions use the PC's `ai_signal` (overall / porosity / undercut / spatter /
incomplete). PCs without an image signal get no AI opinion at all.
"""

from __future__ import annotations

import importlib.util
import logging
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, confusion_matrix
from sklearn.model_selection import train_test_split

from app.core.config import ML_DIR, REPO_ROOT
from app.ml.weld_features import FEATURE_NAMES, extract, extract_from_bytes, vector

log = logging.getLogger(__name__)

MODEL_PATH = ML_DIR / "models" / "shadow_rater.joblib"
DEFECTS = ["good", "porosity", "undercut", "spatter", "incomplete"]
MODEL_LABEL = "Demo model trained on synthetic images — not for certification"

EXPLAIN = {
    "porosity": "{pores:.0f} dark pore(s) detected inside the bead",
    "undercut": "dark groove along {toe_pct:.0f}% of the bead edge",
    "spatter": "{spatter:.0f} spatter spot(s) on the plate",
    "incomplete": "bead covers {cov_pct:.0f}% of its length ({gaps:.0f} gap(s))",
    "good": "continuous, even bead; no pores, groove or spatter detected",
}


@dataclass
class Analysis:
    defect: str
    defect_probs: dict[str, float]
    level: int
    level_probs: dict[int, float]
    features: dict[str, float]
    model_version: str
    explanation: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "defect": self.defect,
            "defect_probs": self.defect_probs,
            "level": self.level,
            "level_probs": {str(k): v for k, v in self.level_probs.items()},
            "features": self.features,
            "model_version": self.model_version,
            "explanation": self.explanation,
        }


class ShadowRater(Protocol):
    version: str
    label: str

    def analyse(self, image: bytes) -> Analysis: ...

    def suggest(self, pc: dict[str, Any], analysis: Analysis | None) -> dict[str, Any] | None: ...


def explain(defect: str, f: dict[str, float]) -> str:
    return EXPLAIN[defect].format(
        pores=f["pores"],
        toe_pct=100 * f["toe_dark"],
        spatter=f["spatter"],
        cov_pct=100 * f["coverage"],
        gaps=f["gaps"],
    )


class DemoForestRater:
    label = MODEL_LABEL

    def __init__(self, bundle: dict[str, Any]) -> None:
        self.defect_model: RandomForestClassifier = bundle["defect_model"]
        self.level_model: RandomForestClassifier = bundle["level_model"]
        self.version = bundle["version"]
        self.metrics = bundle.get("metrics", {})

    def analyse(self, image: bytes) -> Analysis:
        feats = extract_from_bytes(image)
        return self.analyse_features(feats)

    def analyse_features(self, feats: dict[str, float]) -> Analysis:
        x = vector(feats).reshape(1, -1)
        dp = self.defect_model.predict_proba(x)[0]
        lp = self.level_model.predict_proba(x)[0]
        defect_probs = {
            str(c): round(float(p), 4) for c, p in zip(self.defect_model.classes_, dp, strict=True)
        }
        level_probs = {int(c): round(float(p), 4) for c, p in zip(self.level_model.classes_, lp, strict=True)}
        defect = max(defect_probs, key=defect_probs.get)
        level = max(level_probs, key=level_probs.get)
        return Analysis(defect, defect_probs, level, level_probs, feats, self.version, explain(defect, feats))

    def suggest(self, pc: dict[str, Any], analysis: Analysis | None) -> dict[str, Any] | None:
        signal = pc.get("ai_signal")
        if not signal:
            return None  # observe / viva PCs: no image opinion
        if analysis is None:
            return {
                "status": "awaiting_photo",
                "level": None,
                "confidence": None,
                "explanation": "No product photo synced yet",
            }
        p = analysis.defect_probs
        if signal == "overall":
            level = analysis.level
            conf = analysis.level_probs.get(level, 0.0)
            why = analysis.explanation
        elif analysis.defect == signal:
            level = min(analysis.level, 2)
            conf = p.get(signal, 0.0)
            why = explain(signal, analysis.features)
        elif analysis.defect == "good":
            level = 3
            conf = p.get("good", 0.0)
            why = f"no {signal} detected; {EXPLAIN['good']}"
        else:
            # a different defect dominates: this specific aspect looks acceptable
            level = 2
            conf = round(1.0 - p.get(signal, 0.0), 4)
            why = f"no clear {signal}; main issue looks like {analysis.defect}"
        return {
            "status": "ok",
            "level": int(level),
            "confidence": round(float(conf), 3),
            "explanation": why,
            "signal": signal,
            "model_version": analysis.model_version,
            "model_label": self.label,
        }


# ---------------------------------------------------------------- training


def _generator():
    spec = importlib.util.spec_from_file_location("gen", REPO_ROOT / "scripts" / "generate_synthetic.py")
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    return gen


def synthetic_dataset(seed: int, per_class: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Generate (X, defect, level) in memory with the same generator as data/synthetic."""
    import cv2

    gen = _generator()
    rng = np.random.default_rng(seed)
    xs, ds, ls = [], [], []
    for defect in DEFECTS:
        for _ in range(per_class):
            sev = 0 if defect == "good" else int(rng.choice([1, 2, 3] if defect == "incomplete" else [1, 2]))
            img = gen.draw_weld(rng, defect, sev)
            xs.append(vector(extract(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY))))
            ds.append(defect)
            ls.append(gen.quality_level(defect, sev))
    return np.vstack(xs), np.array(ds), np.array(ls)


def train(seed: int = 26242, per_class: int = 120) -> dict[str, Any]:
    X, d, lvl = synthetic_dataset(seed, per_class)
    Xtr, Xte, dtr, dte, ltr, lte = train_test_split(X, d, lvl, test_size=0.3, random_state=seed, stratify=d)
    defect_model = RandomForestClassifier(n_estimators=200, min_samples_leaf=2, random_state=seed).fit(
        Xtr, dtr
    )
    level_model = RandomForestClassifier(n_estimators=200, min_samples_leaf=2, random_state=seed).fit(
        Xtr, ltr
    )
    dpred, lpred = defect_model.predict(Xte), level_model.predict(Xte)
    # fresh generator seed: out-of-sample (still synthetic!)
    Xo, do, lo = synthetic_dataset(seed + 999, max(20, per_class // 3))
    metrics = {
        "train_size": int(len(Xtr)),
        "test_size": int(len(Xte)),
        "defect_accuracy_holdout": round(float(accuracy_score(dte, dpred)), 4),
        "level_accuracy_holdout": round(float(accuracy_score(lte, lpred)), 4),
        "level_within_one_holdout": round(float(np.mean(np.abs(lte - lpred) <= 1)), 4),
        "defect_accuracy_new_seed": round(float(accuracy_score(do, defect_model.predict(Xo))), 4),
        "level_accuracy_new_seed": round(float(accuracy_score(lo, level_model.predict(Xo))), 4),
        "defect_confusion_holdout": {
            "labels": DEFECTS,
            "matrix": confusion_matrix(dte, dpred, labels=DEFECTS).tolist(),
        },
        "feature_importance": dict(
            sorted(
                (
                    (n, round(float(v), 4))
                    for n, v in zip(FEATURE_NAMES, defect_model.feature_importances_, strict=True)
                ),
                key=lambda kv: -kv[1],
            )
        ),
    }
    version = f"demo-rf-{seed}-{per_class}"
    return {
        "defect_model": defect_model,
        "level_model": level_model,
        "version": version,
        "metrics": metrics,
        "features": FEATURE_NAMES,
        "label": MODEL_LABEL,
    }


_lock = threading.Lock()
_cached: DemoForestRater | None = None


def load_rater(path: Path = MODEL_PATH, train_if_missing: bool = True) -> DemoForestRater:
    """Load the trained demo model; train (seconds) and save it if it doesn't exist yet."""
    global _cached
    with _lock:
        if _cached is not None:
            return _cached
        if path.exists():
            bundle = joblib.load(path)
        elif train_if_missing:
            log.warning("Shadow-rater model missing; training the demo model on synthetic data")
            bundle = train()  # same defaults as ml/train_shadow_rater.py (documented results)
            path.parent.mkdir(parents=True, exist_ok=True)
            joblib.dump(bundle, path)
        else:
            raise FileNotFoundError(path)
        _cached = DemoForestRater(bundle)
        return _cached
