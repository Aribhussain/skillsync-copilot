"""M6 — NSQF competency profile and Full / Partial / Gap RECOMMENDATION.

The recommendation supports the assessor; it is never a decision. Only the assessor's
sign-off (and later the awarding body) decides.

Scoring:
  level -> fraction          0: 0.0  1: 0.4  2: 0.8  3: 1.0   (same 0-3 rubric everywhere)
  PC marks earned            theory/practical/viva marks of the PC x fraction
                             (each PC carries its own T/P/V split from the QP file)
  NOS percentage             earned / NOS marks;  >= 70% competent, 40-70% partial, < 40% gap
  Qualification aggregate    earned / total marks (450 for Welding); pass at 70%

Recommendation:
  Full     aggregate >= 70%, every PC assessed, and no critical PC below level 2
  Partial  not Full, but at least one NOS competent -> credit those NOS, bridge the rest
  Gap      no NOS competent
"""

from __future__ import annotations

from typing import Any

LEVEL_FRACTION = {0: 0.0, 1: 0.4, 2: 0.8, 3: 1.0}
COMPONENTS = ("theory", "practical", "viva")
PASS = 70.0
PARTIAL = 40.0


def _r(x: float, nd: int = 1) -> float:
    return round(float(x), nd)


def nos_status(pct: float) -> str:
    return "competent" if pct >= PASS else "partial" if pct >= PARTIAL else "gap"


def build_profile(qp: dict[str, Any], final_scores: dict[str, int]) -> dict[str, Any]:
    nos_rows = []
    total_marks = earned_total = 0.0
    unassessed = 0
    critical_fail: list[str] = []
    for nos in qp["nos"]:
        earned = dict.fromkeys(COMPONENTS, 0.0)
        pcs = []
        weak = []
        for pc in nos["pcs"]:
            level = final_scores.get(pc["id"])
            frac = LEVEL_FRACTION.get(level, 0.0) if level is not None else 0.0
            for c in COMPONENTS:
                earned[c] += pc["marks"][c] * frac
            if level is None:
                unassessed += 1
            elif level < 2:
                weak.append(f"{pc['code']}{' (critical)' if pc['critical'] else ''} at level {level}")
            if pc["critical"] and (level is None or level < 2):
                critical_fail.append(f"{nos['id']} {pc['code']}")
            pcs.append(
                {
                    "pc_id": pc["id"],
                    "code": pc["code"],
                    "level": level,
                    "critical": pc["critical"],
                    "marks": sum(pc["marks"].values()),
                    "earned": _r(sum(pc["marks"].values()) * frac, 2),
                }
            )
        marks = float(sum(nos["marks"].values()))
        got = sum(earned.values())
        pct = 100 * got / marks if marks else 0.0
        status = nos_status(pct)
        missing = sum(1 for p in pcs if p["level"] is None)
        parts = [f"{_r(pct)}% ({_r(got)}/{int(marks)} marks)"]
        if weak:
            parts.append("below standard: " + ", ".join(weak))
        if missing:
            parts.append(f"{missing} PC(s) not assessed")
        nos_rows.append(
            {
                "nos_id": nos["id"],
                "title": nos["title"],
                "marks": nos["marks"],
                "earned": {c: _r(v) for c, v in earned.items()},
                "earned_total": _r(got),
                "max_total": int(marks),
                "percent": _r(pct),
                "status": status,
                "explanation": "; ".join(parts),
                "bridge_module": nos.get("bridge_module") if status != "competent" else None,
                "pcs": pcs,
            }
        )
        total_marks += marks
        earned_total += got

    aggregate = 100 * earned_total / total_marks if total_marks else 0.0
    competent = [n["nos_id"] for n in nos_rows if n["status"] == "competent"]
    if aggregate >= PASS and not unassessed and not critical_fail:
        rec, why = (
            "full",
            f"Aggregate {_r(aggregate)}% meets the {int(PASS)}% pass rule; all critical PCs at level 2+",
        )
    elif competent:
        reasons = []
        if aggregate < PASS:
            reasons.append(f"aggregate {_r(aggregate)}% is below {int(PASS)}%")
        if critical_fail:
            reasons.append("critical PC(s) below standard: " + ", ".join(critical_fail))
        if unassessed:
            reasons.append(f"{unassessed} PC(s) not assessed")
        rec, why = "partial", f"{len(competent)} of {len(nos_rows)} NOS competent; " + "; ".join(reasons)
    else:
        rec, why = "gap", f"No NOS reaches {int(PASS)}% (aggregate {_r(aggregate)}%)"
    bridges = [
        {"nos_id": n["nos_id"], "title": n["bridge_module"]["title"], "hours": n["bridge_module"]["hours"]}
        for n in nos_rows
        if n["bridge_module"]
    ]
    return {
        "qp_id": qp["id"],
        "qp_title": qp["title"],
        "nsqf_level": qp["nsqf_level"],
        "aggregate_percent": _r(aggregate),
        "earned_total": _r(earned_total),
        "max_total": int(total_marks),
        "recommendation": rec,
        "recommendation_reason": why,
        "competent_nos": competent,
        "critical_below_standard": critical_fail,
        "unassessed_pcs": unassessed,
        "bridge_modules": bridges,
        "bridge_hours": sum(b["hours"] for b in bridges),
        "nos": nos_rows,
        "note": "Recommendation only: the assessor decides at sign-off; the awarding body certifies.",
    }
