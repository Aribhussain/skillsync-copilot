from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlmodel import Session

from app.core.db import get_session
from app.core.deps import require_roles
from app.models.user import Role, User
from app.services import calibration
from app.services.golden import seed_golden

router = APIRouter(prefix="/calibration", tags=["M6 calibration"])


@router.get("/me")
def my_calibration(
    session: Session = Depends(get_session), user: User = Depends(require_roles(Role.assessor))
) -> dict:
    """The assessor's own Calibration Index (never other assessors')."""
    return calibration.my_index(session, user)


@router.get("/summary")
def calibration_summary(
    session: Session = Depends(get_session), _: User = Depends(require_roles(Role.qa_lead, Role.admin))
) -> dict:
    """QA view: Krippendorff's alpha, trend, assessor x NOS drift, centres, reason codes."""
    return calibration.summary(session)


class SeedIn(BaseModel):
    per_assessor: int = Field(default=4, ge=1, le=10)
    seed: int = 26242


@router.post("/golden/seed", status_code=201)
def seed(
    body: SeedIn,
    request: Request,
    session: Session = Depends(get_session),
    user: User = Depends(require_roles(Role.qa_lead, Role.admin)),
) -> dict:
    """Randomly seed golden packets into assessor queues (they are not marked as golden)."""
    st = request.app.state
    ids = seed_golden(session, st.storage, st.rater, user.username, body.per_assessor, body.seed)
    return {"created": len(ids)}
