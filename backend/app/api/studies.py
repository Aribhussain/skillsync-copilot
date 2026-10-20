"""Live consistency study (the PS's 'evidence of consistency improvement', with REAL raters).

Protocol: each rater scores every study packet with assistance OFF (photo only), and only
after finishing all OFF scores, the same packets with assistance ON (rubric anchors + the
blind-first AI reveal). Alpha is computed from the real scores:
  alpha_off       OFF scores
  alpha_on_blind  ON blind scores (anchors, before the AI)
  alpha_on_final  ON final scores (after the AI reveal)
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.core.db import get_session
from app.core.deps import get_current_user, require_roles
from app.core.security import utcnow
from app.ml.shadow_rater import Analysis
from app.models.study import Study, StudyScore
from app.models.user import Role, User
from app.services import audit
from app.services.ai_service import suggestion_for
from app.services.golden import GOLDEN_DIR, load_packets
from app.services.krippendorff import alpha
from app.services.qp_store import get_qp, pc_index
from app.services.rubric import rubric

router = APIRouter(prefix="/studies", tags=["M6 live consistency study"])
ARMS = ("off", "on")


class StudyIn(BaseModel):
    name: str = Field(min_length=3, max_length=120)
    packet_ids: list[str] | None = None
    rater_usernames: list[str] | None = None


def _study(session: Session, study_id: int, user: User) -> Study:
    s = session.get(Study, study_id)
    if not s:
        raise HTTPException(404, "Study not found")
    if user.role == Role.assessor and user.id not in s.rater_ids:
        raise HTTPException(403, "You are not a rater in this study")
    return s


def _scores(session: Session, s: Study, rater_id: int | None = None) -> list[StudyScore]:
    q = select(StudyScore).where(StudyScore.study_id == s.id)
    if rater_id is not None:
        q = q.where(StudyScore.rater_id == rater_id)
    return list(session.exec(q))


def _progress(s: Study, mine: list[StudyScore]) -> dict:
    per_arm = len(s.packet_ids) * len(s.pc_ids)
    return {arm: sum(1 for x in mine if x.arm == arm) for arm in ARMS} | {"per_arm": per_arm}


@router.post("", status_code=201)
def create_study(
    body: StudyIn,
    session: Session = Depends(get_session),
    user: User = Depends(require_roles(Role.qa_lead, Role.admin)),
) -> Study:
    packets = load_packets()
    pids = body.packet_ids or list(packets)
    if unknown := set(pids) - set(packets):
        raise HTTPException(422, f"Unknown packets: {sorted(unknown)}")
    pcs = sorted(packets[pids[0]]["consensus"])
    raters = list(session.exec(select(User).where(User.role == Role.assessor)))
    if body.rater_usernames:
        raters = [u for u in raters if u.username in body.rater_usernames]
    if len(raters) < 2:
        raise HTTPException(422, "A study needs at least two raters")
    s = Study(
        name=body.name, created_by=user.id, packet_ids=pids, pc_ids=pcs, rater_ids=[u.id for u in raters]
    )
    session.add(s)
    session.flush()
    audit.record(
        session,
        user.username,
        "study.created",
        {"study_id": s.id, "packets": pids, "raters": [u.username for u in raters]},
    )
    session.commit()
    session.refresh(s)
    return s


@router.get("")
def list_studies(
    session: Session = Depends(get_session), user: User = Depends(get_current_user)
) -> list[dict]:
    if user.role == Role.worker:
        raise HTTPException(403, "Assessors and QA only")
    out = []
    for s in session.exec(select(Study).order_by(Study.id.desc())):
        if user.role == Role.assessor and user.id not in s.rater_ids:
            continue
        mine = _scores(session, s, user.id) if user.role == Role.assessor else []
        out.append({**s.model_dump(), "progress": _progress(s, mine)})
    return out


@router.get("/{study_id}/task")
def next_task(
    study_id: int,
    arm: str,
    session: Session = Depends(get_session),
    user: User = Depends(require_roles(Role.assessor)),
) -> dict:
    """The next packet for this rater in `arm`. ON unlocks only after every OFF score is done."""
    if arm not in ARMS:
        raise HTTPException(422, "arm must be off or on")
    s = _study(session, study_id, user)
    mine = _scores(session, s, user.id)
    prog = _progress(s, mine)
    if arm == "on" and prog["off"] < prog["per_arm"]:
        raise HTTPException(409, "Finish every packet with assistance OFF first")
    done = {(x.packet_id, x.pc_id) for x in mine if x.arm == arm}
    qp = get_qp(load_packets()[s.packet_ids[0]]["qp_id"])
    pcs = pc_index(qp)
    for pid in s.packet_ids:
        todo = [p for p in s.pc_ids if (pid, p) not in done]
        if todo:
            return {
                "study_id": s.id,
                "arm": arm,
                "packet_id": pid,
                "image_url": f"/studies/{s.id}/packets/{pid}/image",
                "pcs": [
                    {
                        "pc_id": p,
                        "code": pcs[p]["code"],
                        "text": pcs[p]["text"],
                        "nos_id": pcs[p]["nos_id"],
                        "ai_signal": pcs[p]["ai_signal"],
                        "done": (pid, p) in done,
                    }
                    for p in s.pc_ids
                ],
                "rubric": rubric() if arm == "on" else None,
                "progress": prog,
            }
    return {"study_id": s.id, "arm": arm, "packet_id": None, "progress": prog}


@router.get("/{study_id}/packets/{packet_id}/image")
def packet_image(
    study_id: int,
    packet_id: str,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> Response:
    if user.role == Role.worker:
        raise HTTPException(403, "Assessors and QA only")
    s = _study(session, study_id, user)
    if packet_id not in s.packet_ids:
        raise HTTPException(404, "Packet not in this study")
    data = (GOLDEN_DIR / load_packets()[packet_id]["image"]).read_bytes()
    return Response(data, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=3600"})


class StudyScoreIn(BaseModel):
    packet_id: str = Field(max_length=16)
    pc_id: str = Field(max_length=64)
    arm: str = Field(pattern="^(off|on)$")
    score: int = Field(ge=0, le=3)


@router.post("/{study_id}/scores", status_code=201)
def submit_study_score(
    study_id: int,
    body: StudyScoreIn,
    request: Request,
    session: Session = Depends(get_session),
    user: User = Depends(require_roles(Role.assessor)),
) -> dict:
    """Blind score. In the ON arm the AI suggestion is revealed only in this response."""
    s = _study(session, study_id, user)
    if body.packet_id not in s.packet_ids or body.pc_id not in s.pc_ids:
        raise HTTPException(404, "Packet or PC not in this study")
    mine = _scores(session, s, user.id)
    if body.arm == "on" and _progress(s, mine)["off"] < len(s.packet_ids) * len(s.pc_ids):
        raise HTTPException(409, "Finish every packet with assistance OFF first")
    existing = next(
        (x for x in mine if (x.packet_id, x.pc_id, x.arm) == (body.packet_id, body.pc_id, body.arm)), None
    )
    if existing:
        raise HTTPException(409, "Already scored")
    row = StudyScore(
        study_id=s.id,
        packet_id=body.packet_id,
        pc_id=body.pc_id,
        rater_id=user.id,
        arm=body.arm,
        blind_score=body.score,
        final_score=body.score,
    )
    ai = None
    if body.arm == "on":
        rater = request.app.state.rater
        qp = get_qp(load_packets()[body.packet_id]["qp_id"])
        ai = suggestion_for(rater, pc_index(qp)[body.pc_id], _analysis(rater, body.packet_id))
        row.ai_level = ai.get("level")
    session.add(row)
    session.commit()
    session.refresh(row)
    return {"score": row.model_dump(), "ai": ai}


_analyses: dict[tuple[str, str], Analysis] = {}  # (model version, packet) -> analysis


def _analysis(rater, packet_id: str) -> Analysis:
    """Shadow-rater analysis of a study packet's photo, computed once per model version."""
    key = (rater.version, packet_id)
    if key not in _analyses:
        _analyses[key] = rater.analyse((GOLDEN_DIR / load_packets()[packet_id]["image"]).read_bytes())
    return _analyses[key]


class StudyFinalIn(BaseModel):
    packet_id: str = Field(max_length=16)
    pc_id: str = Field(max_length=64)
    final_score: int = Field(ge=0, le=3)


@router.post("/{study_id}/scores/final")
def revise_study_score(
    study_id: int,
    body: StudyFinalIn,
    session: Session = Depends(get_session),
    user: User = Depends(require_roles(Role.assessor)),
) -> dict:
    """ON arm only: the rater's final score after seeing the AI (the blind score is kept)."""
    s = _study(session, study_id, user)
    row = session.exec(
        select(StudyScore).where(
            StudyScore.study_id == s.id,
            StudyScore.rater_id == user.id,
            StudyScore.packet_id == body.packet_id,
            StudyScore.pc_id == body.pc_id,
            StudyScore.arm == "on",
        )
    ).first()
    if not row:
        raise HTTPException(404, "No ON-arm blind score yet")
    row.final_score = body.final_score
    row.revised_at = utcnow()
    session.add(row)
    session.commit()
    return row.model_dump()


@router.get("/{study_id}/results")
def study_results(
    study_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(require_roles(Role.qa_lead, Role.admin)),
) -> dict:
    s = _study(session, study_id, user)
    rows = _scores(session, s)
    raters = list(s.rater_ids)

    def a(arm: str, field: str) -> float | None:
        units: dict[tuple, dict[int, int]] = {}
        for r in rows:
            if r.arm == arm:
                units.setdefault((r.packet_id, r.pc_id), {})[r.rater_id] = getattr(r, field)
        val = alpha([[u.get(x) for x in raters] for u in units.values()], "ordinal")
        return None if val is None else round(val, 3)

    complete = {arm: sorted({r.rater_id for r in rows if r.arm == arm}) for arm in ARMS}
    return {
        "study": s.model_dump(),
        "scores": {arm: sum(1 for r in rows if r.arm == arm) for arm in ARMS},
        "raters_with_scores": {arm: len(v) for arm, v in complete.items()},
        "alpha_off": a("off", "blind_score"),
        "alpha_on_blind": a("on", "blind_score"),
        "alpha_on_final": a("on", "final_score"),
        "ai_changed_scores": sum(1 for r in rows if r.arm == "on" and r.final_score != r.blind_score),
        "note": "Computed live from real raters' scores (Krippendorff's alpha, ordinal).",
    }
