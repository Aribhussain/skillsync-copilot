"""W3C Verifiable Credential (VC Data Model 2.0) issued after assessor sign-off.

Issuer: a server Ed25519 key, published as a `did:key` (multicodec 0xed01 + base58btc).
Proof:  `DataIntegrityProof` following the `eddsa-jcs-2022` construction:
          hashData   = SHA-256(canon(proofConfig)) || SHA-256(canon(credential without proof))
          proofValue = "z" + base58btc(Ed25519(hashData))
        canon() is sorted-key, whitespace-free UTF-8 JSON. That matches RFC 8785 (JCS) for
        the value types used here (strings, integers, booleans, short decimals), but it is
        not a full JCS implementation and this credential has NOT been checked with an
        external VC verifier. Documented in docs/DECISIONS.md.

The key file lives in storage/keys/ (git-ignored) and is created on first use.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from functools import lru_cache
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from app.core.security import utcnow_iso

B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
ED25519_PUB_MULTICODEC = b"\xed\x01"
VC_CONTEXT = "https://www.w3.org/ns/credentials/v2"


def b58encode(data: bytes) -> str:
    n = int.from_bytes(data, "big")
    out = ""
    while n:
        n, r = divmod(n, 58)
        out = B58[r] + out
    pad = len(data) - len(data.lstrip(b"\0"))
    return "1" * pad + out


def b58decode(s: str) -> bytes:
    n = 0
    for ch in s:
        n = n * 58 + B58.index(ch)
    body = n.to_bytes((n.bit_length() + 7) // 8, "big") if n else b""
    pad = len(s) - len(s.lstrip("1"))
    return b"\0" * pad + body


def canon(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def did_key(public_key: Ed25519PublicKey) -> str:
    raw = public_key.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return "did:key:z" + b58encode(ED25519_PUB_MULTICODEC + raw)


def public_key_from_did(did: str) -> Ed25519PublicKey:
    if not did.startswith("did:key:z"):
        raise ValueError("Not a base58btc did:key")
    data = b58decode(did[len("did:key:z") :])
    if data[:2] != ED25519_PUB_MULTICODEC or len(data) != 34:
        raise ValueError("Not an Ed25519 did:key")
    return Ed25519PublicKey.from_public_bytes(data[2:])


class Issuer:
    def __init__(self, key: Ed25519PrivateKey) -> None:
        self.key = key
        self.did = did_key(key.public_key())
        self.verification_method = f"{self.did}#{self.did[len('did:key:') :]}"

    @classmethod
    def load_or_create(cls, path: Path) -> Issuer:
        if path.exists():
            key = serialization.load_pem_private_key(path.read_bytes(), password=None)
            assert isinstance(key, Ed25519PrivateKey)
        else:
            key = Ed25519PrivateKey.generate()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(
                key.private_bytes(
                    serialization.Encoding.PEM,
                    serialization.PrivateFormat.PKCS8,
                    serialization.NoEncryption(),
                )
            )
        return cls(key)

    def _hash_data(self, unsecured: dict[str, Any], proof_config: dict[str, Any]) -> bytes:
        return hashlib.sha256(canon(proof_config)).digest() + hashlib.sha256(canon(unsecured)).digest()

    def issue(self, subject: dict[str, Any], credential_id: str | None = None) -> dict[str, Any]:
        now = utcnow_iso()
        vc = {
            "@context": [VC_CONTEXT],
            "id": f"urn:uuid:{credential_id or uuid.uuid4()}",
            "type": ["VerifiableCredential", "NSQFCompetencyCredential"],
            "issuer": {"id": self.did, "name": "SkillSync Co-Pilot (prototype issuer, not an awarding body)"},
            "validFrom": now,
            "credentialSubject": subject,
        }
        proof_config = {
            "@context": vc["@context"],
            "type": "DataIntegrityProof",
            "cryptosuite": "eddsa-jcs-2022",
            "created": now,
            "verificationMethod": self.verification_method,
            "proofPurpose": "assertionMethod",
        }
        signature = self.key.sign(self._hash_data(vc, proof_config))
        return {**vc, "proof": {**proof_config, "proofValue": "z" + b58encode(signature)}}


def verify_vc(vc: dict[str, Any], trusted_did: str) -> dict[str, Any]:
    """Check the proof against the issuer's did:key, and that the issuer is our trusted DID."""
    try:
        proof = dict(vc["proof"])
        proof_value = proof.pop("proofValue")
        unsecured = {k: v for k, v in vc.items() if k != "proof"}
        issuer_did = vc["issuer"]["id"] if isinstance(vc["issuer"], dict) else vc["issuer"]
        if not proof["verificationMethod"].startswith(issuer_did + "#"):
            return {
                "signature_valid": False,
                "issuer_trusted": False,
                "reason": "verificationMethod/issuer mismatch",
            }
        key = public_key_from_did(issuer_did)
        hash_data = hashlib.sha256(canon(proof)).digest() + hashlib.sha256(canon(unsecured)).digest()
        key.verify(b58decode(proof_value[1:]), hash_data)
        return {"signature_valid": True, "issuer_trusted": issuer_did == trusted_did, "reason": None}
    except InvalidSignature:
        return {
            "signature_valid": False,
            "issuer_trusted": False,
            "reason": "signature does not match the content",
        }
    except (KeyError, ValueError, TypeError) as exc:
        return {"signature_valid": False, "issuer_trusted": False, "reason": f"malformed credential: {exc}"}


@lru_cache
def issuer_for(path: str) -> Issuer:
    return Issuer.load_or_create(Path(path))
