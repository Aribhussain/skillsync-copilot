from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.core.db import get_session
from app.core.deps import require_roles
from app.models.lexicon import LexiconAddition
from app.models.user import Role, User
from app.services import audit
from app.services.lexicon import all_entries, detect_lang, lexicon_version

router = APIRouter(prefix="/lexicon", tags=["lexicon"])


@router.get("")
def get_lexicon(session: Session = Depends(get_session)) -> dict:
    entries = all_entries(session)
    return {"version": lexicon_version(session), "count": len(entries), "entries": entries}


class LexiconIn(BaseModel):
    term: str = Field(min_length=2, max_length=96)
    canonical: str = Field(min_length=2, max_length=96)
    category: str = Field(default="process", max_length=24)
    expand: list[str] = Field(min_length=1, max_length=12)
    lang: str | None = None


@router.post("", status_code=201)
def add_term(
    body: LexiconIn,
    session: Session = Depends(get_session),
    user: User = Depends(require_roles(Role.assessor, Role.qa_lead, Role.admin)),
) -> LexiconAddition:
    """Assessor-confirmed addition: a worker used a term the lexicon didn't know."""
    term = body.term.strip()
    if any(e["term"].lower() == term.lower() for e in all_entries(session)):
        raise HTTPException(409, "Term already in lexicon")
    add = LexiconAddition(
        term=term,
        lang=body.lang or detect_lang(term),
        canonical=body.canonical.strip(),
        category=body.category,
        expand=[x.strip().lower() for x in body.expand if x.strip()],
        added_by=user.username,
    )
    session.add(add)
    session.flush()
    audit.record(session, user.username, "lexicon.term_added", {"term": term, "canonical": add.canonical})
    session.commit()
    session.refresh(add)
    return add


@router.get("/additions")
def list_additions(session: Session = Depends(get_session)) -> list[LexiconAddition]:
    return list(session.exec(select(LexiconAddition).order_by(LexiconAddition.id)))
