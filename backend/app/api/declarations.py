from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.core.db import get_session
from app.core.deps import get_current_user, require_roles
from app.models.declaration import Declaration
from app.models.user import Role, User
from app.services import audit
from app.services.consent import has_consent
from app.services.mapping import detect_language

router = APIRouter(prefix="/declarations", tags=["M1/M2 declaration & mapping"])


class DeclarationIn(BaseModel):
    narrative: str = Field(min_length=3, max_length=5000)
    language: str | None = None
    input_mode: str = Field(default="typed", pattern="^(voice|typed|cards)$")
    selected_cards: list[str] = Field(default_factory=list, max_length=40)
    client_id: str | None = Field(default=None, max_length=64)
    captured_at: str | None = Field(default=None, max_length=32)
    provisional_mapping: dict | None = None


class MapPreviewIn(BaseModel):
    narrative: str = Field(min_length=1, max_length=5000)


def get_owned_declaration(session: Session, declaration_id: int, user: User) -> Declaration:
    decl = session.get(Declaration, declaration_id)
    if not decl:
        raise HTTPException(404, "Declaration not found")
    if user.role == Role.worker and decl.worker_id != user.id:
        raise HTTPException(403, "Not your declaration")
    return decl


@router.post("", status_code=201)
def create_declaration(
    body: DeclarationIn,
    session: Session = Depends(get_session),
    user: User = Depends(require_roles(Role.worker)),
) -> Declaration:
    """Store the narrative. Idempotent on `client_id`, so offline retries never duplicate."""
    if body.client_id:
        existing = session.exec(select(Declaration).where(Declaration.client_id == body.client_id)).first()
        if existing:
            if existing.worker_id != user.id:
                raise HTTPException(409, "client_id already used")
            return existing
    if not has_consent(session, user.id, "rpl_assessment"):
        raise HTTPException(403, "Consent for RPL assessment is required before declaring experience")
    decl = Declaration(
        client_id=body.client_id or uuid.uuid4().hex,
        worker_id=user.id,
        narrative=body.narrative.strip(),
        language=body.language or detect_language(body.narrative),
        input_mode=body.input_mode,
        selected_cards=body.selected_cards,
        captured_at=body.captured_at,
        provisional_mapping=body.provisional_mapping,
    )
    session.add(decl)
    session.flush()
    audit.record(
        session,
        user.username,
        "declaration.created",
        {
            "declaration_id": decl.id,
            "language": decl.language,
            "input_mode": decl.input_mode,
            "client_id": decl.client_id,
        },
    )
    session.commit()
    session.refresh(decl)
    return decl


@router.post("/preview-map")
def preview_map(
    body: MapPreviewIn,
    request: Request,
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
) -> dict:
    """Map text without storing it (live preview while the worker speaks)."""
    return request.app.state.mapping.map(session, body.narrative)


@router.post("/{declaration_id}/map")
def map_declaration(
    declaration_id: int,
    request: Request,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict:
    """Top-3 QPs with confidence, matched lexicon terms and a per-PC claim prefill."""
    decl = get_owned_declaration(session, declaration_id, user)
    text = decl.narrative
    if decl.selected_cards:
        text = f"{text} {' '.join(decl.selected_cards)}"
    result = request.app.state.mapping.map(session, text)
    decl.mapping = result
    if decl.status == "submitted":
        decl.status = "mapped"
    session.add(decl)
    audit.record(
        session,
        user.username,
        "declaration.mapped",
        {
            "declaration_id": decl.id,
            "engine": result["engine"],
            "top": [[t["qp_id"], t["confidence"]] for t in result["top"]],
        },
    )
    session.commit()
    return {"declaration_id": decl.id, **result}


@router.get("/mine")
def my_declarations(
    session: Session = Depends(get_session), user: User = Depends(require_roles(Role.worker))
) -> list[Declaration]:
    q = select(Declaration).where(Declaration.worker_id == user.id).order_by(Declaration.id.desc())
    return list(session.exec(q))


@router.get("/{declaration_id}")
def read_declaration(
    declaration_id: int, session: Session = Depends(get_session), user: User = Depends(get_current_user)
) -> Declaration:
    return get_owned_declaration(session, declaration_id, user)
