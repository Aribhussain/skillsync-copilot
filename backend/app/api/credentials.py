"""Assessor sign-off (the only path to a decision), verifiable credential, verify page API,
printable PDF and a SIDH-style export (MOCK schema)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.api.assessments import candidate_name, get_visible_assessment, touch
from app.api.profile import profile_for
from app.core.db import get_session
from app.core.deps import get_current_user, require_roles
from app.core.security import utcnow, verify_password
from app.models.credential import Credential
from app.models.evidence import Evidence
from app.models.user import Role, User
from app.services import audit
from app.services.credential import issuer_for, verify_vc
from app.services.pdf_profile import render_profile_pdf

router = APIRouter(tags=["M6 sign-off & credential"])


def issuer(request: Request):
    return issuer_for(str(request.app.state.settings.storage_path / "keys" / "issuer_ed25519.pem"))


def verify_url(request: Request, credential_id: str) -> str:
    return f"{request.app.state.settings.public_app_url.rstrip('/')}/verify/{credential_id}"


class SignOffIn(BaseModel):
    password: str = Field(min_length=1, max_length=200)
    decision: str = Field(pattern="^(full|partial|gap)$")
    justification: str | None = Field(default=None, max_length=1000)
    confirm: bool


@router.post("/assessments/{assessment_id}/signoff", status_code=201)
def sign_off(
    assessment_id: int,
    body: SignOffIn,
    request: Request,
    session: Session = Depends(get_session),
    user: User = Depends(require_roles(Role.assessor)),
) -> dict:
    """The assessor's decision. Nothing else in the system sets `signed_off`: no automatic
    submission, ever. Requires the assessor's password, every PC scored and every large AI
    gap explained. A decision that differs from the recommendation needs a justification."""
    a = get_visible_assessment(session, assessment_id, user)
    if a.status == "signed_off":
        raise HTTPException(409, "Already signed off")
    if not body.confirm:
        raise HTTPException(422, "Please confirm you reviewed the profile and the evidence")
    if not verify_password(body.password, user.password_hash):
        audit.record(session, user.username, "signoff.password_failed", {"assessment_id": a.id})
        session.commit()
        raise HTTPException(401, "Password does not match")
    profile = profile_for(session, a)
    ready = profile["readiness"]
    if ready["scored"] < ready["total"]:
        raise HTTPException(409, f"{ready['total'] - ready['scored']} PC(s) not scored yet")
    if ready["pending_reasons"]:
        raise HTTPException(409, f"Reason codes missing for: {', '.join(ready['pending_reasons'])}")
    if body.decision != profile["recommendation"] and not (
        body.justification and len(body.justification) >= 10
    ):
        raise HTTPException(422, "Your decision differs from the recommendation: add a justification")

    a.status = "signed_off"
    a.decision = body.decision
    a.decision_justification = body.justification
    a.signed_off_at = utcnow()
    a.signed_off_by = user.id
    touch(a)
    session.add(a)
    audit.record(
        session,
        user.username,
        "assessment.signed_off",
        {"assessment_id": a.id, "decision": body.decision, "recommendation": profile["recommendation"]},
    )

    credential = None
    if body.decision in ("full", "partial"):
        cred_id = str(uuid.uuid4())
        hashes = [e.sha256 for e in session.exec(select(Evidence).where(Evidence.assessment_id == a.id))]
        subject = {
            "id": f"urn:skillsync:candidate:{a.worker_id or 'calibration-' + str(a.id)}",
            "name": candidate_name(session, a),
            "achievement": {
                "type": "NSQFQualification",
                "qualificationPack": profile["qp_id"],
                "title": profile["qp_title"],
                "nsqfLevel": str(profile["nsqf_level"]),
                "result": body.decision,
                "aggregatePercent": str(profile["aggregate_percent"]),
                "competentNOS": profile["competent_nos"],
                "bridgeModules": [b["title"] for b in profile["bridge_modules"]],
            },
            "assessment": {
                "id": str(a.id),
                "assessor": user.username,
                "centre": a.centre or "",
                "signedOff": a.signed_off_at.isoformat(),
                "evidenceSha256": hashes,
                "method": "RPL with blind-first AI second opinion; assessor decision",
            },
        }
        vc = issuer(request).issue(subject, cred_id)
        credential = Credential(id=cred_id, assessment_id=a.id, worker_id=a.worker_id, vc=vc)
        session.add(credential)
        audit.record(
            session, user.username, "credential.issued", {"assessment_id": a.id, "credential_id": cred_id}
        )
    session.commit()
    return {
        "assessment_id": a.id,
        "decision": a.decision,
        "credential_id": credential.id if credential else None,
        "verify_url": verify_url(request, credential.id) if credential else None,
    }


def _credential(session: Session, credential_id: str) -> Credential:
    c = session.get(Credential, credential_id)
    if not c:
        raise HTTPException(404, "Unknown credential")
    return c


@router.get("/credentials/{credential_id}")
def get_credential(credential_id: str, session: Session = Depends(get_session)) -> dict:
    """The verifiable credential JSON (public, like any shareable credential)."""
    return _credential(session, credential_id).vc


@router.get("/credentials/{credential_id}/verify")
def verify_credential(credential_id: str, request: Request, session: Session = Depends(get_session)) -> dict:
    """Public verification for the QR code: checks the Ed25519 proof and the issuer."""
    c = _credential(session, credential_id)
    result = verify_vc(c.vc, issuer(request).did)
    ach = c.vc["credentialSubject"]["achievement"]
    return {
        "credential_id": c.id,
        **result,
        "valid": result["signature_valid"] and result["issuer_trusted"] and c.status == "active",
        "status": c.status,
        "issuer": c.vc["issuer"],
        "issued": c.vc["validFrom"],
        "holder": c.vc["credentialSubject"]["name"],
        "qualification": f"{ach['title']} ({ach['qualificationPack']}, NSQF {ach['nsqfLevel']})",
        "result": ach["result"],
        "note": "Prototype issuer with synthetic demo data - not an official certificate.",
    }


@router.get("/credentials/{credential_id}/pdf")
def credential_pdf(
    credential_id: str,
    request: Request,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> Response:
    c = _credential(session, credential_id)
    a = get_visible_assessment(session, c.assessment_id, user)
    assessor = session.get(User, a.signed_off_by) if a.signed_off_by else None
    pdf = render_profile_pdf(
        profile_for(session, a),
        candidate_name(session, a),
        a.decision or "",
        c.id,
        verify_url(request, c.id),
        assessor.full_name if assessor else "",
        a.signed_off_at.isoformat() if a.signed_off_at else "",
    )
    return Response(
        pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="competency-profile-{a.id}.pdf"'},
    )


@router.get("/credentials/mine/list")
def my_credentials(
    session: Session = Depends(get_session), user: User = Depends(require_roles(Role.worker))
) -> list:
    rows = session.exec(
        select(Credential).where(Credential.worker_id == user.id).order_by(Credential.issued_at)
    )
    return [
        {
            "credential_id": c.id,
            "assessment_id": c.assessment_id,
            "status": c.status,
            "title": c.vc["credentialSubject"]["achievement"]["title"],
            "result": c.vc["credentialSubject"]["achievement"]["result"],
            "issued": c.vc["validFrom"],
        }
        for c in rows
    ]


@router.get("/export/sidh/{assessment_id}")
def sidh_export(
    assessment_id: int,
    request: Request,
    session: Session = Depends(get_session),
    user: User = Depends(require_roles(Role.assessor, Role.qa_lead, Role.admin)),
) -> dict:
    """SIDH-style result payload. MOCK schema for the prototype, NOT the official
    Skill India Digital Hub API (documented in docs/API.md)."""
    a = get_visible_assessment(session, assessment_id, user)
    if a.status != "signed_off":
        raise HTTPException(409, "Only signed-off assessments can be exported")
    profile = profile_for(session, a)
    cred = session.exec(select(Credential).where(Credential.assessment_id == a.id)).first()
    assessor = session.get(User, a.signed_off_by) if a.signed_off_by else None
    return {
        "schema": "skillsync.sidh-export.mock.v1",
        "mock": True,
        "candidate": {"name": candidate_name(session, a), "reference": f"SKS-W{a.worker_id}"},
        "qualification": {
            "qp_code": profile["qp_id"],
            "title": profile["qp_title"],
            "nsqf_level": profile["nsqf_level"],
        },
        "assessment": {
            "mode": "RPL",
            "assessment_id": a.id,
            "centre": a.centre,
            "assessor": assessor.username if assessor else None,
            "signed_off_at": a.signed_off_at.isoformat() if a.signed_off_at else None,
        },
        "result": {
            "decision": a.decision,
            "aggregate_percent": profile["aggregate_percent"],
            "nos": [
                {"nos_code": n["nos_id"], "percent": n["percent"], "status": n["status"]}
                for n in profile["nos"]
            ],
            "bridge_modules": profile["bridge_modules"],
        },
        "credential": {"id": cred.id, "verify_url": verify_url(request, cred.id)} if cred else None,
    }
