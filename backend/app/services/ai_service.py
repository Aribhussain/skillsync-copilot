"""Runs the shadow rater on product photos and turns analyses into per-PC suggestions."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import Engine
from sqlmodel import Session, select

from app.ml.shadow_rater import Analysis, ShadowRater
from app.models.evidence import Evidence
from app.models.scoring import AIAnalysis
from app.services.storage import BlobStorage

log = logging.getLogger(__name__)


def analyse_evidence(engine: Engine, storage: BlobStorage, rater: ShadowRater, evidence_id: int) -> None:
    """Background task: analyse one product photo and store the result."""
    with Session(engine) as session:
        ev = session.get(Evidence, evidence_id)
        if not ev or ev.shot != "product":
            return
        try:
            analysis = rater.analyse(storage.get(ev.file_path))
        except Exception as exc:  # undecodable image etc.: no AI opinion, workflow continues
            log.warning("Shadow rater failed on evidence %s: %s", evidence_id, exc)
            return
        session.add(
            AIAnalysis(
                assessment_id=ev.assessment_id,
                evidence_id=ev.id,
                model_version=analysis.model_version,
                result=analysis.to_dict(),
            )
        )
        session.commit()


def latest_analysis(session: Session, assessment_id: int) -> Analysis | None:
    row = session.exec(
        select(AIAnalysis)
        .where(AIAnalysis.assessment_id == assessment_id)
        .order_by(AIAnalysis.id.desc())
        .limit(1)
    ).first()
    if not row:
        return None
    r = row.result
    return Analysis(
        defect=r["defect"],
        defect_probs=r["defect_probs"],
        level=int(r["level"]),
        level_probs={int(k): v for k, v in r["level_probs"].items()},
        features=r["features"],
        model_version=r["model_version"],
        explanation=r.get("explanation", ""),
    )


def suggestion_for(rater: ShadowRater, pc: dict[str, Any], analysis: Analysis | None) -> dict[str, Any]:
    s = rater.suggest(pc, analysis)
    if s is None:
        return {
            "status": "none",
            "level": None,
            "confidence": None,
            "explanation": (
                "No AI opinion for this PC: it is judged by live observation, viva or declaration."
            ),
        }
    return s
