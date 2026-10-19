"""M4 — signed Process-Product-Person evidence: device registry and verified upload."""

from __future__ import annotations

import hashlib
import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile
from pydantic import BaseModel, Field, ValidationError
from sqlmodel import Session, select

from app.api.assessments import get_visible_assessment
from app.core.db import get_session
from app.core.deps import get_current_user, require_roles
from app.models.evidence import DeviceKey, Evidence
from app.models.user import Role, User
from app.services import audit
from app.services.integrity import check_evidence
from app.services.signing import load_public_key, verify_packet

router = APIRouter(tags=["M4 evidence"])

MAX_BYTES = 10 * 1024 * 1024
SHOTS = ("process", "product", "person")


class DeviceIn(BaseModel):
    device_id: str = Field(min_length=8, max_length=64)
    public_key_spki: str = Field(min_length=40, max_length=600)
    label: str | None = Field(default=None, max_length=128)


@router.post("/devices", status_code=201)
def register_device(
    body: DeviceIn,
    session: Session = Depends(get_session),
    user: User = Depends(require_roles(Role.assessor)),
) -> dict:
    """Register this device's ECDSA P-256 public key (idempotent for the same key)."""
    try:
        load_public_key(body.public_key_spki)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    existing = session.exec(select(DeviceKey).where(DeviceKey.device_id == body.device_id)).first()
    if existing:
        if existing.user_id != user.id or existing.public_key_spki != body.public_key_spki:
            raise HTTPException(409, "device_id already registered with a different key or user")
        return {"device_id": existing.device_id, "registered": True}
    session.add(
        DeviceKey(
            device_id=body.device_id, user_id=user.id, public_key_spki=body.public_key_spki, label=body.label
        )
    )
    audit.record(session, user.username, "device.registered", {"device_id": body.device_id})
    session.commit()
    return {"device_id": body.device_id, "registered": True}


class GPS(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    accuracy: float | None = None


class PacketIn(BaseModel):
    v: str = "v1"
    assessment_id: int
    shot: str = Field(pattern="^(process|product|person)$")
    sha256: str = Field(pattern="^[0-9a-f]{64}$")
    captured_at: str = Field(max_length=40)
    device_id: str = Field(max_length=64)
    challenge_code: str = Field(max_length=12)
    gps: GPS | None = None
    qc: dict | None = None
    source: str = Field(default="camera", pattern="^(camera|upload|simulated)$")
    client_id: str | None = Field(default=None, max_length=64)


def evidence_view(e: Evidence) -> dict:
    data = e.model_dump(exclude={"file_path", "signature"})
    data["image_url"] = f"/evidence/{e.id}/image"
    return data


@router.post("/assessments/{assessment_id}/evidence", status_code=201)
async def upload_evidence(
    assessment_id: int,
    request: Request,
    packet: str = Form(...),
    signature: str = Form(...),
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    user: User = Depends(require_roles(Role.assessor)),
) -> dict:
    """Accept a capture packet only if the image hash and the device signature verify."""
    a = get_visible_assessment(session, assessment_id, user)
    try:
        p = PacketIn.model_validate(json.loads(packet))
    except (ValidationError, json.JSONDecodeError) as exc:
        raise HTTPException(422, f"Invalid packet: {exc}") from exc
    if p.assessment_id != assessment_id:
        raise HTTPException(422, "Packet is for a different assessment")

    data = await file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "Image too large")
    if hashlib.sha256(data).hexdigest() != p.sha256:
        audit.record(session, user.username, "evidence.rejected", {"assessment_id": a.id, "reason": "hash"})
        session.commit()
        raise HTTPException(400, "Image does not match the signed SHA-256")

    # Idempotent: the outbox may retry the same packet.
    existing = session.exec(
        select(Evidence).where(
            Evidence.assessment_id == a.id, Evidence.shot == p.shot, Evidence.sha256 == p.sha256
        )
    ).first()
    if existing:
        return evidence_view(existing)

    device = session.exec(select(DeviceKey).where(DeviceKey.device_id == p.device_id)).first()
    if not device or device.revoked or device.user_id != user.id:
        raise HTTPException(403, "Unknown or revoked device for this assessor")
    packet_dict = p.model_dump()
    if not verify_packet(device.public_key_spki, packet_dict, signature):
        audit.record(
            session, user.username, "evidence.rejected", {"assessment_id": a.id, "reason": "signature"}
        )
        session.commit()
        raise HTTPException(400, "Invalid device signature")

    flags: list[dict] = []
    if p.challenge_code != (a.challenge_code or ""):
        flags.append(
            {
                "code": "challenge_mismatch",
                "severity": "high",
                "detail": "Signed challenge code does not match this assessment's code",
            }
        )
    if p.qc and p.qc.get("issues"):
        flags.append(
            {"code": "qc_warning", "severity": "low", "detail": f"Accepted with: {', '.join(p.qc['issues'])}"}
        )

    storage = request.app.state.storage
    key = storage.put(f"evidence/{a.id}/{p.shot}-{p.sha256[:16]}.jpg", data)
    ev = Evidence(
        assessment_id=a.id,
        shot=p.shot,
        sha256=p.sha256,
        signature=signature,
        signature_valid=True,
        device_id=p.device_id,
        uploaded_by=user.id,
        captured_at=p.captured_at,
        challenge_code=p.challenge_code,
        gps_lat=p.gps.lat if p.gps else None,
        gps_lon=p.gps.lon if p.gps else None,
        gps_accuracy_m=p.gps.accuracy if p.gps else None,
        source=p.source,
        qc=p.qc,
        integrity_flags=flags,
        file_path=key,
        mime=file.content_type or "image/jpeg",
        size_bytes=len(data),
        client_id=p.client_id,
    )
    session.add(ev)
    session.flush()
    # Integrity checks (pHash reuse across all evidence, EXIF, time, GPS, OCR): flags only.
    flags = flags + check_evidence(session, ev, data, a, request.app.state.settings.phash_hamming_threshold)
    ev.integrity_flags = flags
    session.add(ev)
    audit.record(
        session,
        user.username,
        "evidence.received",
        {
            "assessment_id": a.id,
            "evidence_id": ev.id,
            "shot": p.shot,
            "sha256": p.sha256,
            "flags": [f["code"] for f in flags],
        },
    )
    session.commit()
    session.refresh(ev)
    return evidence_view(ev)


@router.get("/assessments/{assessment_id}/evidence")
def list_evidence(
    assessment_id: int, session: Session = Depends(get_session), user: User = Depends(get_current_user)
) -> list[dict]:
    if user.role == Role.worker:
        raise HTTPException(403, "Assessors and QA only")
    a = get_visible_assessment(session, assessment_id, user)
    rows = session.exec(select(Evidence).where(Evidence.assessment_id == a.id).order_by(Evidence.id))
    return [evidence_view(e) for e in rows]


@router.get("/evidence/{evidence_id}/image")
def evidence_image(
    evidence_id: int,
    request: Request,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> Response:
    e = session.get(Evidence, evidence_id)
    if not e:
        raise HTTPException(404, "Evidence not found")
    if user.role == Role.worker:
        raise HTTPException(403, "Assessors and QA only")
    get_visible_assessment(session, e.assessment_id, user)
    return Response(
        request.app.state.storage.get(e.file_path),
        media_type=e.mime,
        headers={"Cache-Control": "private, max-age=3600"},
    )
