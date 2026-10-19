"""Qualification Pack corpus: QP → NOS → PC, loaded from data/qp_corpus/*.json.

Normalisation:
- every PC gets a URL-safe global id, e.g. ``ASC-N3124.PC3``;
- PCs without explicit marks get the NOS theory/practical/viva marks distributed by
  ``weight`` (largest-remainder, so totals stay exact);
- every PC gets ``weight`` = its total marks, the NOS id/title and the QP id.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.core.config import DATA_DIR

COMPONENTS = ("theory", "practical", "viva")
EVIDENCE_HINTS = {"observe", "photo", "viva", "declaration"}
AI_SIGNALS = {None, "overall", "porosity", "undercut", "spatter", "incomplete"}

QP_DIR = DATA_DIR / "qp_corpus"


def pc_global_id(nos_id: str, pc_code: str) -> str:
    return f"{nos_id.replace('/', '-')}.{pc_code}"


def _distribute(total: int, weights: list[float]) -> list[int]:
    if not weights:
        return []
    s = sum(weights) or 1.0
    raw = [total * w / s for w in weights]
    floors = [int(r) for r in raw]
    remainder = total - sum(floors)
    order = sorted(range(len(raw)), key=lambda i: raw[i] - floors[i], reverse=True)
    for i in order[:remainder]:
        floors[i] += 1
    return floors


def _normalise(qp: dict[str, Any]) -> dict[str, Any]:
    for nos in qp["nos"]:
        pcs = nos["pcs"]
        if any("marks" not in p for p in pcs):
            weights = [float(p.get("weight", 1)) for p in pcs]
            split = {c: _distribute(int(nos["marks"][c]), weights) for c in COMPONENTS}
            for i, p in enumerate(pcs):
                p["marks"] = {c: split[c][i] for c in COMPONENTS}
        for p in pcs:
            p["id"] = pc_global_id(nos["id"], p["code"])
            p["nos_id"] = nos["id"]
            p["nos_title"] = nos["title"]
            p["qp_id"] = qp["id"]
            p["weight"] = sum(p["marks"].values())
            p.setdefault("critical", False)
            p.setdefault("safety", False)
            p.setdefault("evidence_hint", "observe")
            p.setdefault("ai_signal", None)
    return qp


def validate_qp(qp: dict[str, Any]) -> list[str]:
    """Return a list of problems (empty list = valid)."""
    errors: list[str] = []
    for key in ("id", "title", "nos", "pass_percentage"):
        if key not in qp:
            errors.append(f"{qp.get('id', '?')}: missing {key}")
    total = 0
    for nos in qp.get("nos", []):
        for c in COMPONENTS:
            pc_sum = sum(p["marks"][c] for p in nos["pcs"])
            if pc_sum != nos["marks"][c]:
                errors.append(f"{nos['id']}: PC {c} marks {pc_sum} != NOS {c} marks {nos['marks'][c]}")
        total += sum(nos["marks"].values())
        for p in nos["pcs"]:
            if p["evidence_hint"] not in EVIDENCE_HINTS:
                errors.append(f"{p['id']}: bad evidence_hint {p['evidence_hint']}")
            if p["ai_signal"] not in AI_SIGNALS:
                errors.append(f"{p['id']}: bad ai_signal {p['ai_signal']}")
    if "total_marks" in qp and qp["total_marks"] != total:
        errors.append(f"{qp['id']}: total_marks {qp['total_marks']} != sum of NOS marks {total}")
    return errors


def load_corpus(directory: Path = QP_DIR) -> dict[str, dict[str, Any]]:
    corpus: dict[str, dict[str, Any]] = {}
    for path in sorted(directory.glob("*.json")):
        qp = _normalise(json.loads(path.read_text(encoding="utf-8")))
        errors = validate_qp(qp)
        if errors:
            raise ValueError(f"Invalid QP file {path.name}: {errors}")
        corpus[qp["id"]] = qp
    return corpus


@lru_cache
def get_corpus() -> dict[str, dict[str, Any]]:
    return load_corpus()


def get_qp(qp_id: str) -> dict[str, Any] | None:
    return get_corpus().get(qp_id)


def iter_pcs(qp: dict[str, Any]):
    for nos in qp["nos"]:
        yield from nos["pcs"]


def pc_index(qp: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {p["id"]: p for p in iter_pcs(qp)}


def qp_summary(qp: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": qp["id"],
        "title": qp["title"],
        "title_hi": qp.get("title_hi"),
        "sector": qp["sector"],
        "awarding_body": qp["awarding_body"],
        "nsqf_level": qp["nsqf_level"],
        "source_kind": qp["source_kind"],
        "nos_count": len(qp["nos"]),
        "pc_count": sum(len(n["pcs"]) for n in qp["nos"]),
        "total_marks": sum(sum(n["marks"].values()) for n in qp["nos"]),
    }
