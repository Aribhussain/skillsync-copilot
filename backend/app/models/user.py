from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlmodel import Field, SQLModel

from app.core.security import utcnow


class Role(StrEnum):
    worker = "worker"
    assessor = "assessor"
    qa_lead = "qa_lead"
    admin = "admin"


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(max_length=64, unique=True, index=True)
    full_name: str = Field(max_length=128)
    role: str = Field(max_length=16, index=True)
    centre: str | None = Field(default=None, max_length=128)
    preferred_language: str = Field(default="hi", max_length=8)
    password_hash: str = Field(max_length=128)
    is_active: bool = True
    created_at: datetime = Field(default_factory=utcnow)


class UserPublic(SQLModel):
    id: int
    username: str
    full_name: str
    role: str
    centre: str | None
    preferred_language: str
