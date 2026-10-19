"""Seed golden (pre-graded, SYNTHETIC) calibration packets into assessor queues.

Each seeded packet becomes an ordinary-looking assessment (a synthetic candidate name, a
signed product photo, a challenge code), so assessors cannot tell it is a calibration item.
The photo is signed by a per-assessor 'demo seeder' device key registered on the server:
the signature is genuinely valid, and the seeding is documented as demo infrastructure.
"""

from __future__ import annotations

import hashlib
import json
import random
import uuid
from functools import lru_cache
from typing import Any

from cryptography.hazmat.primitives.asymmetric import ec
from sqlmodel import Session, select

from app.core.config import DATA_DIR
from app.core.security import utcnow, utcnow_iso
from app.ml.shadow_rater import ShadowRater
from app.models.assessment import Assessment
from app.models.evidence import DeviceKey, Evidence
from app.models.scoring import AIAnalysis
from app.models.user import Role, User
from app.services import audit
from app.services.integrity import compute_phash
from app.services.signing import sign_packet_for_tests, spki_b64
from app.services.storage import BlobStorage

GOLDEN_DIR = DATA_DIR / "golden_packets"
CANDIDATE_NAMES = [
    "Deepak Yadav",
    "Sunil Kumar",
    "Imran Ansari",
    "Rajesh Verma",
    "Mohan Das",
    "Vijay Singh",
    "Arjun Patel",
    "Farhan Khan",
    "Naveen Gupta",
    "Om Prakash",
    "Harish Nair",
    "Raju Sharma",
]


@lru_cache
def load_packets() -> dict[str, dict[str, Any]]:
    doc = json.loads((GOLDEN_DIR / "golden_packets.json").read_text(encoding="utf-8"))
    return {p["id"]: p for p in doc["packets"]}


def _seeder_key(session: Session, user: User, keys: dict[int, ec.EllipticCurvePrivateKey]) -> tuple[str, Any]:
    key = keys.setdefault(user.id, ec.generate_private_key(ec.SECP256R1()))
    device_id = f"seeder-{user.username}-{uuid.uuid4().hex[:8]}"
    session.add(
        DeviceKey(
            device_id=device_id,
            user_id=user.id,
            public_key_spki=spki_b64(key.public_key()),
            label="demo seeder (golden packets)",
        )
    )
    return device_id, key


def seed_golden(
    session: Session,
    storage: BlobStorage,
    rater: ShadowRater,
    actor: str,
    per_assessor: int = 4,
    seed: int = 26242,
) -> list[int]:
    rng = random.Random(seed)
    packets = list(load_packets().values())
    created: list[int] = []
    keys: dict[int, ec.EllipticCurvePrivateKey] = {}
    for assessor in session.exec(select(User).where(User.role == Role.assessor).order_by(User.id)):
        device_id, key = _seeder_key(session, assessor, keys)
        for p in rng.sample(packets, min(per_assessor, len(packets))):
            data = (GOLDEN_DIR / p["image"]).read_bytes()
            code = "".join(rng.choice("ACDEFGHJKMNPQRTUVWXY34679") for _ in range(6))
            a = Assessment(
                client_id=uuid.uuid4().hex,
                assessor_id=assessor.id,
                qp_id=p["qp_id"],
                status="in_progress",
                is_golden=True,
                golden_packet_id=p["id"],
                candidate_label=rng.choice(CANDIDATE_NAMES),
                centre=assessor.centre,
                challenge_code=code,
                started_at=utcnow(),
            )
            session.add(a)
            session.flush()
            sha = hashlib.sha256(data).hexdigest()
            packet = {
                "assessment_id": a.id,
                "shot": "product",
                "sha256": sha,
                "captured_at": utcnow_iso(),
                "device_id": device_id,
                "challenge_code": code,
                "gps": None,
            }
            ev = Evidence(
                assessment_id=a.id,
                shot="product",
                sha256=sha,
                phash=compute_phash(data),
                signature=sign_packet_for_tests(key, packet),
                signature_valid=True,
                device_id=device_id,
                uploaded_by=assessor.id,
                captured_at=packet["captured_at"],
                challenge_code=code,
                source="camera",
                integrity_flags=[],
                file_path=storage.put(f"evidence/{a.id}/product-{sha[:16]}.jpg", data),
                size_bytes=len(data),
            )
            session.add(ev)
            session.flush()
            analysis = rater.analyse(data)
            session.add(
                AIAnalysis(
                    assessment_id=a.id,
                    evidence_id=ev.id,
                    model_version=analysis.model_version,
                    result=analysis.to_dict(),
                )
            )
            created.append(a.id)
    audit.record(session, actor, "golden.seeded", {"assessments": created, "per_assessor": per_assessor})
    session.commit()
    return created
