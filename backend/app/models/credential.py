from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel

from app.core.security import utcnow


class Credential(SQLModel, table=True):
    """A W3C Verifiable Credential issued at assessor sign-off (never automatically)."""

    __tablename__ = "credentials"

    id: str = Field(primary_key=True, max_length=36)  # uuid; also in the VC id (urn:uuid:...)
    assessment_id: int = Field(foreign_key="assessments.id", unique=True, index=True)
    worker_id: int | None = Field(default=None, foreign_key="users.id", index=True)
    vc: dict = Field(sa_column=Column(JSON, nullable=False))
    status: str = Field(default="active", max_length=16)  # active | revoked
    issued_at: datetime = Field(default_factory=utcnow)
