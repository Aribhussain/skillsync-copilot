from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlmodel import Session, select

from app.core.db import get_session
from app.core.deps import get_current_user, require_roles
from app.core.security import utcnow
from app.models.assessment import Assessment
from app.models.declaration import Declaration
from app.models.user import Role, User
from app.services import audit
from app.services.qp_store import get_qp, pc_index

router = APIRouter(prefix="/assessments", tags=["assessments"])


class AssessmentRequestIn(BaseModel):
    qp_id: str = Field(max_length=64)
    declaration_id: int | None = None
    declaration_client_id: str | None = Field(default=None, max_length=64)
    claimed_pc_ids: list[str] = Field(default_factory=list, max_length=200)
    client_id: str | None = Field(default=None, max_length=64)


def public_view(a: Assessment, viewer: User) -> dict:
    """What a given user may see. Assessors never see whether an item is a golden packet."""
    data = a.model_dump()
    if viewer.role in (Role.worker, Role.assessor):
        data.pop("is_golden", None)
        data.pop("golden_packet_id", None)
    if viewer.role == Role.worker:
        data.pop("challenge_code", None)
    return data


def pick_assessor(session: Session) -> User | None:
    """Least-loaded assessor (open assessments), ties broken by id."""
    assessors = list(session.exec(select(User).where(User.role == Role.assessor, User.is_active)))
    if not assessors:
        return None
    open_counts = dict(
        session.exec(
            select(Assessment.assessor_id, func.count(Assessment.id))
            .where(Assessment.status.in_(["requested", "in_progress"]))
            .group_by(Assessment.assessor_id)
        ).all()
    )
    return min(assessors, key=lambda u: (open_counts.get(u.id, 0), u.id))


@router.post("", status_code=201)
def request_assessment(
    body: AssessmentRequestIn,
    session: Session = Depends(get_session),
    user: User = Depends(require_roles(Role.worker)),
) -> dict:
    """The worker confirms a QP (and their claimed PCs); this creates the assessment request."""
    if body.client_id:
        existing = session.exec(select(Assessment).where(Assessment.client_id == body.client_id)).first()
        if existing:
            return public_view(existing, user)
    qp = get_qp(body.qp_id)
    if not qp:
        raise HTTPException(422, "Unknown QP")
    decl = None
    if body.declaration_id is not None:
        decl = session.get(Declaration, body.declaration_id)
    elif body.declaration_client_id:
        decl = session.exec(
            select(Declaration).where(Declaration.client_id == body.declaration_client_id)
        ).first()
    if decl is None:
        raise HTTPException(404, "Declaration not found (it may not have synced yet)")
    if decl.worker_id != user.id:
        raise HTTPException(403, "Not your declaration")
    valid = pc_index(qp)
    claimed = [p for p in body.claimed_pc_ids if p in valid]
    assessor = pick_assessor(session)
    a = Assessment(
        client_id=body.client_id or uuid.uuid4().hex,
        declaration_id=decl.id,
        worker_id=user.id,
        assessor_id=assessor.id if assessor else None,
        qp_id=qp["id"],
        claimed_pc_ids=claimed,
        centre=assessor.centre if assessor else user.centre,
    )
    decl.status = "confirmed"
    session.add(decl)
    session.add(a)
    session.flush()
    audit.record(
        session,
        user.username,
        "assessment.requested",
        {
            "assessment_id": a.id,
            "qp_id": a.qp_id,
            "claimed": len(claimed),
            "assessor": assessor.username if assessor else None,
        },
    )
    session.commit()
    session.refresh(a)
    return public_view(a, user)


@router.get("/mine")
def my_assessments(
    session: Session = Depends(get_session), user: User = Depends(require_roles(Role.worker))
) -> list[dict]:
    q = select(Assessment).where(Assessment.worker_id == user.id).order_by(Assessment.id.desc())
    return [public_view(a, user) for a in session.exec(q)]


def get_visible_assessment(session: Session, assessment_id: int, user: User) -> Assessment:
    a = session.get(Assessment, assessment_id)
    if not a:
        raise HTTPException(404, "Assessment not found")
    if user.role == Role.worker and a.worker_id != user.id:
        raise HTTPException(403, "Not your assessment")
    if user.role == Role.assessor and a.assessor_id != user.id:
        raise HTTPException(403, "Not assigned to you")
    return a


def touch(a: Assessment) -> None:
    a.updated_at = utcnow()


@router.get("/{assessment_id}")
def read_assessment(
    assessment_id: int, session: Session = Depends(get_session), user: User = Depends(get_current_user)
) -> dict:
    return public_view(get_visible_assessment(session, assessment_id, user), user)
