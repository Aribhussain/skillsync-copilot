from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Column, Text, UniqueConstraint
from sqlmodel import Field, SQLModel

from app.core.security import utcnow


class AIAnalysis(SQLModel, table=True):
    """Output of the shadow rater for one product photo. Never returned to an assessor
    directly: only per-PC suggestions, and only after that PC's blind score exists."""

    __tablename__ = "ai_analyses"

    id: int | None = Field(default=None, primary_key=True)
    assessment_id: int = Field(foreign_key="assessments.id", index=True)
    evidence_id: int = Field(foreign_key="evidence.id", index=True)
    model_version: str = Field(max_length=64)
    result: dict = Field(sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utcnow)


class PCScore(SQLModel, table=True):
    """An assessor's score for one PC. `blind_score` is immutable once written; the AI
    suggestion is snapshotted at reveal time; revisions change `final_score` only."""

    __tablename__ = "pc_scores"
    __table_args__ = (UniqueConstraint("assessment_id", "pc_id", "assessor_id", name="uq_pc_score"),)

    id: int | None = Field(default=None, primary_key=True)
    assessment_id: int = Field(foreign_key="assessments.id", index=True)
    pc_id: str = Field(max_length=64, index=True)
    assessor_id: int = Field(foreign_key="users.id", index=True)
    blind_score: int
    final_score: int
    ai_status: str | None = Field(default=None, max_length=24)  # ok | awaiting_photo | none
    ai_level: int | None = None
    ai_confidence: float | None = None
    ai_explanation: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    ai_model_version: str | None = Field(default=None, max_length=64)
    gap: int | None = None
    reason_required: bool = False
    reason_code: str | None = Field(default=None, max_length=32)
    note: str | None = Field(default=None, max_length=500)
    client_id: str | None = Field(default=None, max_length=64)
    created_at: datetime = Field(default_factory=utcnow)
    revealed_at: datetime | None = None
    revised_at: datetime | None = None
