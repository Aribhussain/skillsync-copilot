from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel

from app.core.security import utcnow


class AuditEntry(SQLModel, table=True):
    """Append-only, hash-chained ledger row.

    hash = sha256(seq | ts | actor | action | payload_hash | prev_hash). `ts` is
    stored as an ISO string so the hash recomputes identically on every database.
    """

    __tablename__ = "audit_ledger"

    seq: int = Field(primary_key=True, sa_column_kwargs={"autoincrement": False})
    ts: str = Field(max_length=32)
    actor: str = Field(max_length=64, index=True)
    action: str = Field(max_length=64, index=True)
    payload: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    payload_hash: str = Field(max_length=64)
    prev_hash: str = Field(max_length=64)
    hash: str = Field(max_length=64, unique=True)


class ConsentRecord(SQLModel, table=True):
    """DPDP Act 2023-style consent ledger. Rows are never updated: a withdrawal
    is a new row with granted=False."""

    __tablename__ = "consent_ledger"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    purpose: str = Field(max_length=48, index=True)
    notice_version: str = Field(max_length=16)
    notice_sha256: str = Field(max_length=64)
    language: str = Field(max_length=8)
    granted: bool
    created_at: datetime = Field(default_factory=utcnow)
