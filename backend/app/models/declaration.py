from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Column, UniqueConstraint
from sqlmodel import Field, SQLModel

from app.core.security import utcnow


class Declaration(SQLModel, table=True):
    """M1 — a worker's 'kaam ki kahani' (self-declaration of prior experience)."""

    __tablename__ = "declarations"

    id: int | None = Field(default=None, primary_key=True)
    client_id: str = Field(max_length=64, unique=True, index=True)  # idempotency key from the device
    worker_id: int = Field(foreign_key="users.id", index=True)
    narrative: str
    language: str = Field(max_length=12)
    input_mode: str = Field(max_length=12)  # voice | typed | cards
    selected_cards: list = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    provisional_mapping: dict | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    mapping: dict | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    status: str = Field(default="submitted", max_length=16)  # submitted | mapped | confirmed
    created_at: datetime = Field(default_factory=utcnow)
    captured_at: str | None = Field(default=None, max_length=32)  # device time when created offline


class QPEmbedding(SQLModel, table=True):
    """Embedding vectors stored portably as JSON; loaded into a numpy VectorIndex at startup."""

    __tablename__ = "qp_embeddings"
    __table_args__ = (UniqueConstraint("ref", "model", name="uq_qp_embedding_ref_model"),)

    id: int | None = Field(default=None, primary_key=True)
    ref: str = Field(max_length=96, index=True)  # e.g. "qp:QG-4.5-AU-01811-2024-V1-ASDC"
    model: str = Field(max_length=128)
    text_sha256: str = Field(max_length=64)
    vector: list = Field(sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utcnow)
