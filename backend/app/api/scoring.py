"""M5 — blind-first scoring with a server-enforced AI reveal.

Rules enforced here (not in the UI):
  1. An AI suggestion for a PC is only ever returned to an assessor AFTER that assessor's
     blind score for that PC exists (in the POST /scores response, or via
     /ai-suggestions, which returns 403 for unscored PCs).
  2. The blind score is immutable. Revisions change final_score only, and the original
     stays in the DB and in the audit ledger.
  3. If |blind - AI| >= AI_GAP_THRESHOLD, a reason code is required.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.api.assessments import get_visible_assessment, touch
from app.core.db import get_session
from app.core.deps import require_roles
from app.core.security import utcnow
from app.models.assessment import Assessment
from app.models.evidence import Evidence
from app.models.scoring import PCScore
from app.models.user import Role, User
from app.services import audit
from app.services.ai_service import latest_analysis, suggestion_for
from app.services.qp_store import get_qp, pc_index

router = APIRouter(prefix="/assessments", tags=["M5 blind-first scoring"])

REASON_CODES = (
    "evidence_unclear",
    "ai_misread_image",
    "observed_live_differently",
    "rubric_ambiguity",
    "other",
)


class BlindScoreIn(BaseModel):
    pc_id: str = Field(max_length=64)
    score: int = Field(ge=0, le=3)
    client_id: str | None = Field(default=None, max_length=64)


class ReviseIn(BaseModel):
    final_score: int | None = Field(default=None, ge=0, le=3)
    reason_code: str | None = Field(default=None, pattern="^(" + "|".join(REASON_CODES) + ")$")
    note: str | None = Field(default=None, max_length=500)


def score_view(s: PCScore) -> dict:
    return s.model_dump(exclude={"assessor_id"})


def _assessor_assessment(session: Session, assessment_id: int, user: User) -> tuple[Assessment, dict]:
    a = get_visible_assessment(session, assessment_id, user)
    qp = get_qp(a.qp_id)
    if not qp:
        raise HTTPException(500, "QP missing")
    return a, pc_index(qp)


def _my_score(session: Session, assessment_id: int, pc_id: str, user: User) -> PCScore | None:
    return session.exec(
        select(PCScore).where(
            PCScore.assessment_id == assessment_id, PCScore.pc_id == pc_id, PCScore.assessor_id == user.id
        )
    ).first()


@router.post("/{assessment_id}/scores", status_code=201)
def submit_blind_score(
    assessment_id: int,
    body: BlindScoreIn,
    request: Request,
    session: Session = Depends(get_session),
    user: User = Depends(require_roles(Role.assessor)),
) -> dict:
    """Record the assessor's blind score. Only now is the AI suggestion revealed."""
    a, pcs = _assessor_assessment(session, assessment_id, user)
    if a.status not in ("in_progress", "scored"):
        raise HTTPException(
            409, "Start the assessment before scoring" if a.status == "requested" else "Locked"
        )
    pc = pcs.get(body.pc_id)
    if not pc:
        raise HTTPException(404, "PC not in this qualification")
    existing = _my_score(session, a.id, body.pc_id, user)
    if existing:
        if existing.blind_score != body.score:
            raise HTTPException(
                409, "Blind score already recorded; it cannot be changed (revise the final score)"
            )
        return {"score": score_view(existing), "ai": _reveal_payload(existing)}

    settings = request.app.state.settings
    s = PCScore(
        assessment_id=a.id,
        pc_id=body.pc_id,
        assessor_id=user.id,
        blind_score=body.score,
        final_score=body.score,
        client_id=body.client_id,
    )
    session.add(s)
    session.flush()
    audit.record(
        session,
        user.username,
        "score.blind",
        {"assessment_id": a.id, "pc_id": body.pc_id, "score": body.score},
    )
    # --- reveal (strictly after the blind score has been written)
    sug = _suggestion(session, request, a, pc)
    _apply_suggestion(s, sug, settings.ai_gap_threshold)
    session.add(s)
    audit.record(
        session,
        user.username,
        "ai.revealed",
        {"assessment_id": a.id, "pc_id": body.pc_id, "ai_level": s.ai_level, "gap": s.gap},
    )
    _update_status(session, a, len(pcs), user)
    session.commit()
    session.refresh(s)
    return {"score": score_view(s), "ai": _reveal_payload(s, sug)}


def _suggestion(session: Session, request: Request, a: Assessment, pc: dict) -> dict:
    """The AI suggestion for one PC. In full mode the analysis runs on a Celery worker, so a
    product photo can be synced while its analysis is still running: that is `pending`,
    not `awaiting_photo`, and the client polls /ai-refresh until it resolves."""
    sug = suggestion_for(request.app.state.rater, pc, latest_analysis(session, a.id))
    if sug["status"] == "awaiting_photo":
        has_photo = session.exec(
            select(Evidence.id).where(Evidence.assessment_id == a.id, Evidence.shot == "product")
        ).first()
        if has_photo is not None:
            sug = {**sug, "status": "pending", "explanation": "Product photo synced; AI analysis running"}
    return sug


def _apply_suggestion(s: PCScore, sug: dict, gap_threshold: int) -> None:
    s.ai_status = sug["status"]
    s.ai_level = sug.get("level")
    s.ai_confidence = sug.get("confidence")
    s.ai_explanation = sug.get("explanation")
    s.ai_model_version = sug.get("model_version")
    s.revealed_at = utcnow()
    if s.ai_level is not None:
        s.gap = s.blind_score - s.ai_level
        s.reason_required = abs(s.gap) >= gap_threshold


@router.post("/{assessment_id}/scores/{pc_id}/ai-refresh")
def refresh_ai(
    assessment_id: int,
    pc_id: str,
    request: Request,
    session: Session = Depends(get_session),
    user: User = Depends(require_roles(Role.assessor)),
) -> dict:
    """Re-check the AI opinion for a PC this assessor has ALREADY blind-scored, when it was
    `pending` or `awaiting_photo` at lock time. Blind-first still holds: no score, no AI."""
    a, pcs = _assessor_assessment(session, assessment_id, user)
    pc = pcs.get(pc_id)
    if not pc:
        raise HTTPException(404, "PC not in this qualification")
    s = _my_score(session, a.id, pc_id, user)
    if not s:
        raise HTTPException(
            403, "Blind-first: submit your own score for this PC before seeing the AI suggestion"
        )
    if s.ai_status not in ("pending", "awaiting_photo"):
        return {"score": score_view(s), "ai": _reveal_payload(s)}
    sug = _suggestion(session, request, a, pc)
    if sug["status"] != s.ai_status:
        _apply_suggestion(s, sug, request.app.state.settings.ai_gap_threshold)
        session.add(s)
        if s.ai_status == "ok":
            audit.record(
                session,
                user.username,
                "ai.revealed",
                {"assessment_id": a.id, "pc_id": pc_id, "ai_level": s.ai_level, "gap": s.gap, "late": True},
            )
        session.commit()
        session.refresh(s)
    return {"score": score_view(s), "ai": _reveal_payload(s, sug)}


def _reveal_payload(s: PCScore, sug: dict | None = None) -> dict:
    out = {
        "status": s.ai_status,
        "level": s.ai_level,
        "confidence": s.ai_confidence,
        "explanation": s.ai_explanation,
        "model_version": s.ai_model_version,
        "gap": s.gap,
        "reason_required": s.reason_required,
    }
    if sug and sug.get("model_label"):
        out["model_label"] = sug["model_label"]
    return out


def _update_status(session: Session, a: Assessment, total_pcs: int, user: User) -> None:
    scored = len(
        session.exec(
            select(PCScore.id).where(PCScore.assessment_id == a.id, PCScore.assessor_id == user.id)
        ).all()
    )
    if scored >= total_pcs and a.status == "in_progress":
        a.status = "scored"
        touch(a)
        session.add(a)


@router.get("/{assessment_id}/ai-suggestions")
def ai_suggestions(
    assessment_id: int,
    request: Request,
    pc_id: str | None = None,
    session: Session = Depends(get_session),
    user: User = Depends(require_roles(Role.assessor)),
) -> list[dict]:
    """AI suggestions ONLY for PCs this assessor has already scored (blind-first)."""
    a, pcs = _assessor_assessment(session, assessment_id, user)
    mine = {
        s.pc_id: s
        for s in session.exec(
            select(PCScore).where(PCScore.assessment_id == a.id, PCScore.assessor_id == user.id)
        )
    }
    if pc_id is not None:
        if pc_id not in pcs:
            raise HTTPException(404, "PC not in this qualification")
        if pc_id not in mine:
            raise HTTPException(
                403, "Blind-first: submit your own score for this PC before seeing the AI suggestion"
            )
        wanted = [pc_id]
    else:
        wanted = list(mine)
    analysis = latest_analysis(session, a.id)
    out = []
    for pid in wanted:
        sug = suggestion_for(request.app.state.rater, pcs[pid], analysis)
        out.append({"pc_id": pid, "your_blind_score": mine[pid].blind_score, **sug})
    return out


@router.get("/{assessment_id}/scores")
def my_scores(
    assessment_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(require_roles(Role.assessor)),
) -> list[dict]:
    a, _ = _assessor_assessment(session, assessment_id, user)
    rows = session.exec(
        select(PCScore)
        .where(PCScore.assessment_id == a.id, PCScore.assessor_id == user.id)
        .order_by(PCScore.id)
    )
    return [score_view(s) for s in rows]


@router.patch("/{assessment_id}/scores/{pc_id}")
def revise_score(
    assessment_id: int,
    pc_id: str,
    body: ReviseIn,
    session: Session = Depends(get_session),
    user: User = Depends(require_roles(Role.assessor)),
) -> dict:
    """Revise the final score and/or give the reason for a large gap. The blind score never changes."""
    a, _ = _assessor_assessment(session, assessment_id, user)
    if a.status == "signed_off":
        raise HTTPException(409, "Signed off: scores are locked")
    s = _my_score(session, a.id, pc_id, user)
    if not s:
        raise HTTPException(404, "No blind score for this PC yet")
    reason = body.reason_code or s.reason_code
    if s.reason_required and not reason:
        raise HTTPException(422, "The gap to the AI suggestion is large: pick a reason code")
    if reason == "other" and not (body.note or s.note):
        raise HTTPException(422, "Reason 'other' needs a note")
    before = s.final_score
    if body.final_score is not None:
        s.final_score = body.final_score
    s.reason_code = reason
    if body.note is not None:
        s.note = body.note
    s.revised_at = utcnow()
    session.add(s)
    audit.record(
        session,
        user.username,
        "score.revised",
        {
            "assessment_id": a.id,
            "pc_id": pc_id,
            "blind_score": s.blind_score,
            "final_before": before,
            "final_after": s.final_score,
            "reason_code": reason,
        },
    )
    session.commit()
    session.refresh(s)
    return score_view(s)
