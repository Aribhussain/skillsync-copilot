"""M3 — PC-level evidence plan (rules engine). Mirrored in frontend/src/lib/evidencePlan.ts.

Rules, in order:
  1. critical or safety PC          -> observe (LOCKED: live observation, cannot be downgraded)
  2. evidence_hint == photo         -> photo
  3. evidence_hint == viva          -> viva
  4. evidence_hint == declaration   -> declaration+spot-check if the worker claimed the PC, else viva
  5. otherwise (observe)            -> observe

Assessors may override unlocked PCs (with a reason). Locked PCs can never be changed.
"""

from __future__ import annotations

from typing import Any

ROUTES = ("observe", "photo", "viva", "declaration+spot-check")

REASONS = {
    "critical": "Critical PC: must be observed live by the assessor. This rule cannot be overridden.",
    "safety": "Safety PC: must be observed live by the assessor. This rule cannot be overridden.",
    "photo": "Product evidence: a signed photo of the finished work is enough.",
    "viva": "Knowledge PC: checked by oral questions (viva).",
    "declaration_claimed": "The worker declared this PC: accept the declaration with a spot-check question.",
    "declaration_unclaimed": "Not declared by the worker: check it with a viva question instead.",
    "observe": "Performance PC: observe the worker doing it.",
    "override": "Changed by the assessor.",
}


def route_for(pc: dict[str, Any], claimed: bool) -> dict[str, Any]:
    if pc.get("critical") or pc.get("safety"):
        kind = "critical" if pc.get("critical") else "safety"
        return {"route": "observe", "locked": True, "rule": kind, "reason": REASONS[kind]}
    hint = pc.get("evidence_hint", "observe")
    if hint == "photo":
        return {"route": "photo", "locked": False, "rule": "photo", "reason": REASONS["photo"]}
    if hint == "viva":
        return {"route": "viva", "locked": False, "rule": "viva", "reason": REASONS["viva"]}
    if hint == "declaration":
        if claimed:
            return {
                "route": "declaration+spot-check",
                "locked": False,
                "rule": "declaration_claimed",
                "reason": REASONS["declaration_claimed"],
            }
        return {
            "route": "viva",
            "locked": False,
            "rule": "declaration_unclaimed",
            "reason": REASONS["declaration_unclaimed"],
        }
    return {"route": "observe", "locked": False, "rule": "observe", "reason": REASONS["observe"]}


def build_plan(
    qp: dict[str, Any], claimed_pc_ids: list[str], overrides: dict[str, Any] | None = None
) -> list[dict]:
    """Evidence plan grouped by NOS. `overrides` = {pc_id: {"route": ..., "reason": ...}}."""
    claimed = set(claimed_pc_ids)
    overrides = overrides or {}
    plan = []
    for nos in qp["nos"]:
        pcs = []
        for pc in nos["pcs"]:
            r = route_for(pc, pc["id"] in claimed)
            ov = overrides.get(pc["id"])
            if ov and not r["locked"]:
                r = {
                    "route": ov["route"],
                    "locked": False,
                    "rule": "override",
                    "reason": ov.get("reason") or REASONS["override"],
                    "default_route": r["route"],
                }
            pcs.append(
                {
                    "pc_id": pc["id"],
                    "code": pc["code"],
                    "text": pc["text"],
                    "marks": pc["marks"],
                    "critical": pc["critical"],
                    "safety": pc["safety"],
                    "claimed": pc["id"] in claimed,
                    "ai_signal": pc.get("ai_signal"),
                    **r,
                }
            )
        plan.append({"nos_id": nos["id"], "title": nos["title"], "marks": nos["marks"], "pcs": pcs})
    return plan


def plan_summary(plan: list[dict]) -> dict[str, int]:
    counts = dict.fromkeys(ROUTES, 0)
    locked = 0
    for nos in plan:
        for pc in nos["pcs"]:
            counts[pc["route"]] += 1
            locked += pc["locked"]
    return {**counts, "locked": locked}


def evidence_plan_rules() -> dict[str, Any]:
    """Machine-readable rules for the device (mirrored engine in TypeScript)."""
    return {"routes": list(ROUTES), "reasons": REASONS}
