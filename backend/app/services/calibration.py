"""M6 — calibration: inter-assessor agreement on golden packets.

alpha            Krippendorff's alpha (ordinal) over units = (golden packet, PC), coders =
                 assessors; computed on blind scores (unassisted) and final scores (assisted)
alpha per PC     same, restricted to one PC
alpha decision   nominal alpha on a per-packet pass/fail proxy (mean final level >= 70%)
Calibration Index (per assessor, private to them and QA):
                 100 * (1 - mean |blind - consensus| / 3); bias = mean(blind - consensus)
                 (+ lenient / - severe); drift = slope of |error| over their scoring order
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

import numpy as np
from sqlmodel import Session, select

from app.models.assessment import Assessment
from app.models.scoring import PCScore
from app.models.user import Role, User
from app.services.golden import load_packets
from app.services.krippendorff import alpha
from app.services.qp_store import get_qp, pc_index

LEVEL_FRACTION = {0: 0.0, 1: 0.4, 2: 0.8, 3: 1.0}


def golden_scores(session: Session) -> list[dict[str, Any]]:
    packets = load_packets()
    rows = session.exec(
        select(PCScore, Assessment).where(PCScore.assessment_id == Assessment.id, Assessment.is_golden)
    ).all()
    out = []
    for s, a in rows:
        consensus = packets.get(a.golden_packet_id or "", {}).get("consensus", {})
        if s.pc_id not in consensus:
            continue
        out.append(
            {
                "packet": a.golden_packet_id,
                "pc_id": s.pc_id,
                "assessor_id": s.assessor_id,
                "blind": s.blind_score,
                "final": s.final_score,
                "consensus": consensus[s.pc_id],
                "at": s.created_at,
                "qp_id": a.qp_id,
            }
        )
    return out


def _alpha_units(rows: list[dict], field: str, assessors: list[int]) -> float | None:
    units: dict[tuple, dict[int, int]] = defaultdict(dict)
    for r in rows:
        units[(r["packet"], r["pc_id"])][r["assessor_id"]] = r[field]
    data = [[u.get(a) for a in assessors] for u in units.values()]
    return alpha(data, "ordinal")


def _round(x: float | None, nd: int = 3) -> float | None:
    return None if x is None else round(float(x), nd)


def calibration_index(rows: list[dict]) -> dict[str, Any]:
    if not rows:
        return {"n": 0, "index": None, "bias": None, "drift": None}
    rows = sorted(rows, key=lambda r: r["at"])
    err = np.array([r["blind"] - r["consensus"] for r in rows], dtype=float)
    drift = float(np.polyfit(np.arange(len(err)), np.abs(err), 1)[0]) if len(err) >= 4 else None
    return {
        "n": len(rows),
        "index": round(100 * (1 - np.abs(err).mean() / 3), 1),
        "bias": round(float(err.mean()), 2),
        "drift": _round(drift),
    }


def summary(session: Session) -> dict[str, Any]:
    rows = golden_scores(session)
    assessors = {u.id: u for u in session.exec(select(User).where(User.role == Role.assessor))}
    ids = sorted(assessors)
    by_pc: dict[str, list] = defaultdict(list)
    for r in rows:
        by_pc[r["pc_id"]].append(r)

    # decision proxy per (packet, assessor)
    dec: dict[tuple, list] = defaultdict(list)
    for r in rows:
        dec[(r["packet"], r["assessor_id"])].append(LEVEL_FRACTION[r["final"]])
    dec_units: dict[str, dict[int, int]] = defaultdict(dict)
    for (packet, aid), vals in dec.items():
        dec_units[packet][aid] = int(np.mean(vals) >= 0.7)
    decision_alpha = alpha([[u.get(a) for a in ids] for u in dec_units.values()], "nominal")

    # weekly trend
    weeks: dict[str, list] = defaultdict(list)
    for r in rows:
        y, w, _ = r["at"].isocalendar()
        weeks[f"{y}-W{w:02d}"].append(r)
    trend = [
        {
            "week": wk,
            "alpha_blind": _round(_alpha_units(rs, "blind", ids)),
            "alpha_final": _round(_alpha_units(rs, "final", ids)),
            "n": len(rs),
        }
        for wk, rs in sorted(weeks.items())
    ]

    # assessor x NOS heat-map of mean signed deviation from consensus
    nos_of: dict[str, str] = {}
    for r in rows:
        if r["pc_id"] not in nos_of:
            qp = get_qp(r["qp_id"])
            nos_of.update({pid: pc["nos_id"] for pid, pc in pc_index(qp).items()} if qp else {})
    cells: dict[tuple, list] = defaultdict(list)
    for r in rows:
        cells[(r["assessor_id"], nos_of.get(r["pc_id"], "?"))].append(r["blind"] - r["consensus"])
    nos_ids = sorted({n for _, n in cells})
    heatmap = {
        "assessors": [assessors[a].username for a in ids],
        "nos": nos_ids,
        "values": [
            [_round(np.mean(cells[(a, n)]), 2) if cells.get((a, n)) else None for n in nos_ids] for a in ids
        ],
    }

    per_assessor = {
        assessors[a].username: {
            **calibration_index([r for r in rows if r["assessor_id"] == a]),
            "centre": assessors[a].centre,
        }
        for a in ids
    }
    centres: dict[str, list] = defaultdict(list)
    for v in per_assessor.values():
        if v["index"] is not None:
            centres[v["centre"] or "?"].append(v["index"])
    reasons = Counter(
        s.reason_code for s in session.exec(select(PCScore).where(PCScore.reason_code.is_not(None)))
    )
    all_scores = session.exec(select(PCScore).where(PCScore.ai_level.is_not(None))).all()
    ai_agree = np.mean([abs(s.blind_score - s.ai_level) <= 1 for s in all_scores]) if all_scores else None
    return {
        "synthetic_note": "Golden packets and their consensus are SYNTHETIC.",
        "units": len({(r["packet"], r["pc_id"]) for r in rows}),
        "scores": len(rows),
        "alpha_blind": _round(_alpha_units(rows, "blind", ids)),
        "alpha_final": _round(_alpha_units(rows, "final", ids)),
        "alpha_decision": _round(decision_alpha),
        "alpha_per_pc": {pc: _round(_alpha_units(rs, "blind", ids)) for pc, rs in sorted(by_pc.items())},
        "trend": trend,
        "heatmap": heatmap,
        "assessors": per_assessor,
        "centres": {c: round(float(np.mean(v)), 1) for c, v in centres.items()},
        "reason_codes": dict(reasons),
        "ai_agreement_within_1": _round(ai_agree),
    }


def my_index(session: Session, user: User) -> dict[str, Any]:
    rows = [r for r in golden_scores(session) if r["assessor_id"] == user.id]
    return {
        "assessor": user.username,
        **calibration_index(rows),
        "note": "Private: visible only to you and the QA lead.",
    }
