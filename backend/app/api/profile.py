from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.api.assessments import assessment_card, get_visible_assessment
from app.core.db import get_session
from app.core.deps import get_current_user
from app.models.assessment import Assessment
from app.models.credential import Credential
from app.models.scoring import PCScore
from app.models.user import Role, User
from app.services.profile import build_profile
from app.services.qp_store import get_qp

router = APIRouter(prefix="/assessments", tags=["M6 competency profile"])


def profile_for(session: Session, a: Assessment) -> dict[str, Any]:
    qp = get_qp(a.qp_id)
    if not qp:
        raise HTTPException(500, "QP missing")
    rows = session.exec(
        select(PCScore).where(PCScore.assessment_id == a.id, PCScore.assessor_id == a.assessor_id)
    ).all()
    profile = build_profile(qp, {s.pc_id: s.final_score for s in rows})
    pending_reasons = [s.pc_id for s in rows if s.reason_required and not s.reason_code]
    profile["readiness"] = {
        "scored": len(rows),
        "total": sum(len(n["pcs"]) for n in qp["nos"]),
        "pending_reasons": pending_reasons,
        "can_sign_off": a.status in ("in_progress", "scored") and len(rows) > 0 and not pending_reasons,
    }
    return profile


@router.get("/{assessment_id}/profile")
def competency_profile(
    assessment_id: int, session: Session = Depends(get_session), user: User = Depends(get_current_user)
) -> dict:
    """Per-PC -> per-NOS NSQF competency profile with a Full / Partial / Gap recommendation."""
    a = get_visible_assessment(session, assessment_id, user)
    if user.role == Role.worker and a.status != "signed_off":
        raise HTTPException(403, "Your profile is available after the assessor signs off")
    cred = session.exec(select(Credential).where(Credential.assessment_id == a.id)).first()
    return {
        "assessment": assessment_card(session, a, user),
        **profile_for(session, a),
        "decision": a.decision,
        "decision_justification": a.decision_justification,
        "credential_id": cred.id if cred else None,
    }
