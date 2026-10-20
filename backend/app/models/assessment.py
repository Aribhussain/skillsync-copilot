from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel

from app.core.security import utcnow


class Assessment(SQLModel, table=True):
    """An RPL assessment request: one worker, one confirmed QP, one assessor."""

    __tablename__ = "assessments"

    id: int | None = Field(default=None, primary_key=True)
    client_id: str = Field(max_length=64, unique=True, index=True)  # idempotency key from the device
    declaration_id: int | None = Field(default=None, foreign_key="declarations.id", index=True)
    worker_id: int | None = Field(default=None, foreign_key="users.id", index=True)
    assessor_id: int | None = Field(default=None, foreign_key="users.id", index=True)
    qp_id: str = Field(max_length=64, index=True)
    # requested -> in_progress -> scored -> signed_off
    status: str = Field(default="requested", max_length=20, index=True)
    claimed_pc_ids: list = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    # assessor changes to unlocked evidence routes: {pc_id: {"route": ..., "reason": ...}}
    # (nullable, no server default: MySQL forbids literal defaults on JSON columns)
    plan_overrides: dict | None = Field(default_factory=dict, sa_column=Column(JSON, nullable=True))
    # display name when there is no worker account (e.g. calibration packets)
    candidate_label: str | None = Field(default=None, max_length=128)
    started_at: datetime | None = Field(default=None)
    # set only by POST /assessments/{id}/signoff (assessor, password re-entered)
    decision: str | None = Field(default=None, max_length=16)  # full | partial | gap
    decision_justification: str | None = Field(default=None, max_length=1000)
    signed_off_at: datetime | None = Field(default=None)
    signed_off_by: int | None = Field(default=None, foreign_key="users.id")
    challenge_code: str | None = Field(default=None, max_length=12)
    centre: str | None = Field(default=None, max_length=128)
    # Golden packets are pre-graded calibration items. This flag is never exposed to assessors.
    is_golden: bool = Field(default=False, index=True)
    golden_packet_id: str | None = Field(default=None, max_length=32)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
