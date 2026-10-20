from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Column, UniqueConstraint
from sqlmodel import Field, SQLModel

from app.core.security import utcnow


class Study(SQLModel, table=True):
    """Live consistency study: raters score the same packets with assistance OFF, then ON."""

    __tablename__ = "studies"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(max_length=120)
    created_by: int = Field(foreign_key="users.id")
    packet_ids: list = Field(sa_column=Column(JSON, nullable=False))
    pc_ids: list = Field(sa_column=Column(JSON, nullable=False))
    rater_ids: list = Field(sa_column=Column(JSON, nullable=False))
    status: str = Field(default="open", max_length=16)  # open | closed
    created_at: datetime = Field(default_factory=utcnow)


class StudyScore(SQLModel, table=True):
    __tablename__ = "study_scores"
    __table_args__ = (
        UniqueConstraint("study_id", "packet_id", "pc_id", "rater_id", "arm", name="uq_study_score"),
    )

    id: int | None = Field(default=None, primary_key=True)
    study_id: int = Field(foreign_key="studies.id", index=True)
    packet_id: str = Field(max_length=16)
    pc_id: str = Field(max_length=64)
    rater_id: int = Field(foreign_key="users.id", index=True)
    arm: str = Field(max_length=4)  # off | on
    blind_score: int
    final_score: int  # ON arm: after the AI reveal (may equal blind); OFF arm: = blind
    ai_level: int | None = None
    created_at: datetime = Field(default_factory=utcnow)
    revised_at: datetime | None = None
