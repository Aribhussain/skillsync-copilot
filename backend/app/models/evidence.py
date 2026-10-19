from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Column, Text, UniqueConstraint
from sqlmodel import Field, SQLModel

from app.core.security import utcnow


class DeviceKey(SQLModel, table=True):
    """Public half of a field device's ECDSA P-256 key. The private key never leaves the
    device: it is generated non-extractable in WebCrypto."""

    __tablename__ = "device_keys"

    id: int | None = Field(default=None, primary_key=True)
    device_id: str = Field(max_length=64, unique=True, index=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    public_key_spki: str = Field(sa_column=Column(Text, nullable=False))  # base64 DER SubjectPublicKeyInfo
    label: str | None = Field(default=None, max_length=128)
    revoked: bool = False
    created_at: datetime = Field(default_factory=utcnow)


class Evidence(SQLModel, table=True):
    """A signed capture packet (Process / Product / Person photo) and its integrity checks."""

    __tablename__ = "evidence"
    __table_args__ = (UniqueConstraint("assessment_id", "shot", "sha256", name="uq_evidence_packet"),)

    id: int | None = Field(default=None, primary_key=True)
    assessment_id: int = Field(foreign_key="assessments.id", index=True)
    shot: str = Field(max_length=16)  # process | product | person
    sha256: str = Field(max_length=64, index=True)
    phash: str | None = Field(default=None, max_length=32, index=True)
    signature: str = Field(sa_column=Column(Text, nullable=False))
    signature_valid: bool = False
    device_id: str = Field(max_length=64, index=True)
    uploaded_by: int = Field(foreign_key="users.id")
    captured_at: str = Field(max_length=40)  # device clock, ISO 8601 (signed)
    challenge_code: str = Field(max_length=12)
    gps_lat: float | None = None
    gps_lon: float | None = None
    gps_accuracy_m: float | None = None
    source: str = Field(default="camera", max_length=16)  # camera | upload | simulated
    qc: dict | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    exif: dict | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    integrity_flags: list | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    file_path: str = Field(max_length=255)
    mime: str = Field(default="image/jpeg", max_length=40)
    size_bytes: int = 0
    client_id: str | None = Field(default=None, max_length=64)
    received_at: datetime = Field(default_factory=utcnow)
