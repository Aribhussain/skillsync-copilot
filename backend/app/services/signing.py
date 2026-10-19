"""Evidence packet canonicalisation and ECDSA P-256 verification.

The device signs `canonical_packet(packet)` with WebCrypto ECDSA(SHA-256). WebCrypto emits
the raw IEEE P1363 form (r || s, 64 bytes); `cryptography` expects DER, so we convert.
Keep `canonical_packet` byte-identical with frontend/src/lib/evidence.ts.
"""

from __future__ import annotations

import base64
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature, encode_dss_signature

PACKET_VERSION = "v1"


def _coord(v: Any) -> str:
    return "" if v is None else f"{float(v):.6f}"


def canonical_packet(p: dict[str, Any]) -> str:
    gps = p.get("gps") or {}
    return "|".join(
        [
            PACKET_VERSION,
            str(int(p["assessment_id"])),
            str(p["shot"]),
            str(p["sha256"]).lower(),
            str(p["captured_at"]),
            str(p["device_id"]),
            str(p["challenge_code"]),
            _coord(gps.get("lat")),
            _coord(gps.get("lon")),
        ]
    )


def load_public_key(spki_b64: str) -> ec.EllipticCurvePublicKey:
    key = serialization.load_der_public_key(base64.b64decode(spki_b64))
    if not isinstance(key, ec.EllipticCurvePublicKey) or key.curve.name != "secp256r1":
        raise ValueError("Device key must be an ECDSA P-256 public key")
    return key


def verify_packet(spki_b64: str, packet: dict[str, Any], signature_b64: str) -> bool:
    try:
        raw = base64.b64decode(signature_b64)
        if len(raw) != 64:
            return False
        r, s = int.from_bytes(raw[:32], "big"), int.from_bytes(raw[32:], "big")
        load_public_key(spki_b64).verify(
            encode_dss_signature(r, s), canonical_packet(packet).encode("utf-8"), ec.ECDSA(hashes.SHA256())
        )
        return True
    except (InvalidSignature, ValueError, TypeError):
        return False


def sign_packet_for_tests(private_key: ec.EllipticCurvePrivateKey, packet: dict[str, Any]) -> str:
    """Produce a WebCrypto-style (raw r||s) signature. Used by tests and the demo seeder."""
    der = private_key.sign(canonical_packet(packet).encode("utf-8"), ec.ECDSA(hashes.SHA256()))
    r, s = decode_dss_signature(der)
    return base64.b64encode(r.to_bytes(32, "big") + s.to_bytes(32, "big")).decode("ascii")


def spki_b64(public_key: ec.EllipticCurvePublicKey) -> str:
    der = public_key.public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    return base64.b64encode(der).decode("ascii")
