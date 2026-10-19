from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel

from app.core.security import utcnow


class LexiconAddition(SQLModel, table=True):
    """Assessor-confirmed lexicon terms. They are merged on top of the seed
    lexicon in data/lexicon/lexicon.json, so the lexicon grows from field use."""

    __tablename__ = "lexicon_additions"

    id: int | None = Field(default=None, primary_key=True)
    term: str = Field(max_length=96, unique=True, index=True)
    lang: str = Field(max_length=12)
    canonical: str = Field(max_length=96)
    category: str = Field(max_length=24)
    expand: list = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    added_by: str = Field(max_length=64)
    created_at: datetime = Field(default_factory=utcnow)
