"""Shared test helpers: assessments, device keys and signed capture packets."""

from __future__ import annotations

import hashlib
import io
import json
import uuid
from datetime import UTC, datetime

import numpy as np
from cryptography.hazmat.primitives.asymmetric import ec
from PIL import Image

from app.services.signing import sign_packet_for_tests, spki_b64

WELDING = "QG-4.5-AU-01811-2024-V1-ASDC"


def started_assessment(client, auth, worker="worker1", claimed=()):
    """Worker requests Welding; the assigned assessor starts it. Returns (assessment, assessor username)."""
    h = auth(worker)
    client.post("/consents", json={"purposes": ["rpl_assessment", "evidence_capture"]}, headers=h)
    d = client.post("/declarations", json={"narrative": "argon aur co2 welding, grinding"}, headers=h).json()
    a = client.post(
        "/assessments",
        json={"qp_id": WELDING, "declaration_id": d["id"], "claimed_pc_ids": list(claimed)},
        headers=h,
    ).json()
    assessors = client.get("/users?role=assessor", headers=auth("admin")).json()
    username = next(u["username"] for u in assessors if u["id"] == a["assessor_id"])
    started = client.post(f"/assessments/{a['id']}/start", headers=auth(username)).json()
    return started, username


class Device:
    def __init__(self):
        self.key = ec.generate_private_key(ec.SECP256R1())
        self.device_id = f"dev-{uuid.uuid4().hex[:16]}"

    def register(self, client, headers):
        r = client.post(
            "/devices",
            json={"device_id": self.device_id, "public_key_spki": spki_b64(self.key.public_key())},
            headers=headers,
        )
        assert r.status_code == 201, r.text

    def packet(self, assessment, shot, data: bytes, **over):
        p = {
            "v": "v1",
            "assessment_id": assessment["id"],
            "shot": shot,
            "sha256": hashlib.sha256(data).hexdigest(),
            "captured_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
            "device_id": self.device_id,
            "challenge_code": assessment["challenge_code"],
            "gps": {"lat": 28.4089, "lon": 77.3178, "accuracy": 12.0},
            "source": "camera",
        }
        p.update(over)
        return p

    def upload(self, client, headers, assessment, shot, data: bytes, packet=None, signature=None):
        packet = packet or self.packet(assessment, shot, data)
        signature = signature or sign_packet_for_tests(self.key, packet)
        return client.post(
            f"/assessments/{assessment['id']}/evidence",
            data={"packet": json.dumps(packet), "signature": signature},
            files={"file": (f"{shot}.jpg", data, "image/jpeg")},
            headers=headers,
        )


def jpeg_bytes(seed: int = 0, size=(320, 240), brightness: float = 1.0) -> bytes:
    """A textured test image (distinct per seed)."""
    rng = np.random.default_rng(seed)
    arr = rng.integers(0, 255, (size[1] // 8, size[0] // 8, 3), dtype=np.uint8)
    img = Image.fromarray(arr).resize(size, Image.NEAREST)
    if brightness != 1.0:
        img = Image.fromarray(np.clip(np.asarray(img) * brightness, 0, 255).astype(np.uint8))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()
