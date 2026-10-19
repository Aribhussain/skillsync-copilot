from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.core.db import get_session
from app.core.deps import get_current_user, require_roles
from app.models.audit import AuditEntry, ConsentRecord
from app.models.user import Role, User
from app.services import audit
from app.services.consent import NOTICE_VERSION, PURPOSES, get_notice, notice_hash

router = APIRouter(tags=["audit & consent"])


@router.get("/audit/verify")
def verify_audit_chain(
    session: Session = Depends(get_session),
    _: User = Depends(require_roles(Role.qa_lead, Role.admin, Role.assessor)),
) -> dict:
    """Recompute the whole hash chain. Any edited, deleted or reordered row breaks it."""
    return audit.verify_chain(session)


@router.get("/audit/entries")
def list_audit_entries(
    limit: int = 50,
    action: str | None = None,
    session: Session = Depends(get_session),
    _: User = Depends(require_roles(Role.qa_lead, Role.admin)),
) -> list[AuditEntry]:
    q = select(AuditEntry)
    if action:
        q = q.where(AuditEntry.action == action)
    return list(session.exec(q.order_by(AuditEntry.seq.desc()).limit(min(limit, 500))))


@router.get("/consents/notice")
def consent_notice(lang: str = "en") -> dict:
    return get_notice(lang)


class ConsentIn(BaseModel):
    purposes: list[str]
    language: str = "en"
    granted: bool = True
    notice_version: str = NOTICE_VERSION
    notice_sha256: str | None = None


@router.post("/consents", status_code=201)
def give_consent(
    body: ConsentIn,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> list[ConsentRecord]:
    lang = body.language if body.language in ("en", "hi") else "en"
    expected = notice_hash(lang)
    if body.notice_sha256 and body.notice_sha256 != expected:
        raise HTTPException(409, "The consent notice has changed. Please review the latest notice.")
    unknown = set(body.purposes) - set(PURPOSES)
    if unknown or not body.purposes:
        raise HTTPException(422, f"Unknown or missing purposes: {sorted(unknown)}")
    records = []
    for purpose in body.purposes:
        rec = ConsentRecord(
            user_id=user.id,
            purpose=purpose,
            notice_version=body.notice_version,
            notice_sha256=expected,
            language=lang,
            granted=body.granted,
        )
        session.add(rec)
        records.append(rec)
    session.flush()
    audit.record(
        session,
        user.username,
        "consent.granted" if body.granted else "consent.withdrawn",
        {
            "purposes": sorted(body.purposes),
            "notice_sha256": expected,
            "consent_ids": [r.id for r in records],
        },
    )
    session.commit()
    for r in records:
        session.refresh(r)
    return records


@router.get("/consents/me")
def my_consents(session: Session = Depends(get_session), user: User = Depends(get_current_user)) -> dict:
    """Current consent state per purpose (latest row wins) plus the full history."""
    rows = list(
        session.exec(select(ConsentRecord).where(ConsentRecord.user_id == user.id).order_by(ConsentRecord.id))
    )
    state = {p: False for p in PURPOSES}
    for r in rows:
        state[r.purpose] = r.granted
    return {"state": state, "history": rows}


def has_consent(session: Session, user_id: int, purpose: str) -> bool:
    row = session.exec(
        select(ConsentRecord)
        .where(ConsentRecord.user_id == user_id, ConsentRecord.purpose == purpose)
        .order_by(ConsentRecord.id.desc())
        .limit(1)
    ).first()
    return bool(row and row.granted)
