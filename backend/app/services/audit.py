"""Hash-chained, append-only audit ledger."""

from __future__ import annotations

import json
from typing import Any

from sqlmodel import Session, select

from app.core.security import canonical_json, sha256_hex, utcnow_iso
from app.models.audit import AuditEntry

GENESIS_HASH = "0" * 64


def _entry_hash(seq: int, ts: str, actor: str, action: str, payload_hash: str, prev_hash: str) -> str:
    return sha256_hex(f"{seq}|{ts}|{actor}|{action}|{payload_hash}|{prev_hash}")


def record(session: Session, actor: str, action: str, payload: dict[str, Any] | None = None) -> AuditEntry:
    """Append an entry. It is added to `session`; the caller commits it together
    with the business write so the ledger and the data never diverge."""
    payload = payload or {}
    session.flush()
    last = session.exec(select(AuditEntry).order_by(AuditEntry.seq.desc()).limit(1)).first()
    seq = (last.seq + 1) if last else 1
    prev_hash = last.hash if last else GENESIS_HASH
    ts = utcnow_iso()
    payload_json = canonical_json(payload)
    payload_hash = sha256_hex(payload_json)
    entry = AuditEntry(
        seq=seq,
        ts=ts,
        actor=actor,
        action=action,
        payload=json.loads(payload_json),
        payload_hash=payload_hash,
        prev_hash=prev_hash,
        hash=_entry_hash(seq, ts, actor, action, payload_hash, prev_hash),
    )
    session.add(entry)
    session.flush()
    return entry


def verify_chain(session: Session) -> dict[str, Any]:
    """Recompute every hash. Returns {valid, entries, broken_at, reason, head}."""
    prev_hash = GENESIS_HASH
    expected_seq = 1
    count = 0
    for entry in session.exec(select(AuditEntry).order_by(AuditEntry.seq)):
        count += 1
        reason = None
        if entry.seq != expected_seq:
            reason = f"sequence gap: expected {expected_seq}, found {entry.seq}"
        elif entry.prev_hash != prev_hash:
            reason = "prev_hash does not match the previous entry"
        elif sha256_hex(canonical_json(entry.payload)) != entry.payload_hash:
            reason = "payload was modified"
        elif (
            _entry_hash(entry.seq, entry.ts, entry.actor, entry.action, entry.payload_hash, entry.prev_hash)
            != entry.hash
        ):
            reason = "entry hash mismatch"
        if reason:
            return {"valid": False, "entries": count, "broken_at": entry.seq, "reason": reason, "head": None}
        prev_hash = entry.hash
        expected_seq += 1
    return {"valid": True, "entries": count, "broken_at": None, "reason": None, "head": prev_hash}
