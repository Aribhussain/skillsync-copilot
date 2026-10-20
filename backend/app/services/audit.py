"""Hash-chained, append-only audit ledger — "append, then seal".

1. `record()` inserts the entry inside the caller's transaction (atomic with the business
   write). The database assigns `seq`; the chain fields stay empty.
2. After that transaction commits, `seal()` runs under a process-wide lock in its own short
   transaction: it takes unsealed entries in `seq` order, gives each the next
   `chain_index`, links `prev_hash` to the previous sealed entry and computes `hash`.

Why: computing the chain inside concurrent request transactions races on "read the last
entry" (two requests both write position N+1). Sealing after commit is serialised and
never holds a Python lock while waiting for a database write lock held by a request, so
it cannot deadlock. Chain order is `chain_index`, so it does not depend on how a given
database orders autoincrement ids. The only trade-off is a millisecond-scale window between
commit and seal; `verify_chain()` always seals pending entries first.
(Multi-process deployments would need a DB-level lock for the sealer; see DECISIONS.md.)
"""

from __future__ import annotations

import json
import logging
import threading
from typing import Any

from sqlalchemy import Engine, event
from sqlmodel import Session, func, select

from app.core.security import canonical_json, sha256_hex, utcnow_iso
from app.models.audit import AuditEntry

log = logging.getLogger(__name__)
GENESIS_HASH = "0" * 64
_seal_lock = threading.Lock()


def _entry_hash(index: int, ts: str, actor: str, action: str, payload_hash: str, prev_hash: str) -> str:
    return sha256_hex(f"{index}|{ts}|{actor}|{action}|{payload_hash}|{prev_hash}")


def _seal_after_commit(session: Session) -> None:
    try:
        seal(session.get_bind())
    except Exception:  # never fail the business request because sealing hiccupped
        log.exception("Audit sealing failed; pending entries will be sealed on the next commit/verify")


def record(session: Session, actor: str, action: str, payload: dict[str, Any] | None = None) -> AuditEntry:
    """Append an entry in the caller's transaction; it is sealed right after commit."""
    payload_json = canonical_json(payload or {})
    entry = AuditEntry(
        ts=utcnow_iso(),
        actor=actor,
        action=action,
        payload=json.loads(payload_json),
        payload_hash=sha256_hex(payload_json),
    )
    session.add(entry)
    session.flush()
    if not session.info.get("audit_seal_hook"):
        event.listen(session, "after_commit", _seal_after_commit)
        session.info["audit_seal_hook"] = True
    return entry


def seal(engine: Engine) -> int:
    """Chain every committed-but-unsealed entry. Returns how many were sealed."""
    with _seal_lock, Session(engine) as s:
        pending = s.exec(
            select(AuditEntry).where(AuditEntry.chain_index.is_(None)).order_by(AuditEntry.seq)
        ).all()
        if not pending:
            return 0
        last_index = s.exec(select(func.max(AuditEntry.chain_index))).one() or 0
        last = (
            s.exec(select(AuditEntry).where(AuditEntry.chain_index == last_index)).first()
            if last_index
            else None
        )
        prev = last.hash if last else GENESIS_HASH
        for i, e in enumerate(pending, start=last_index + 1):
            e.chain_index = i
            e.prev_hash = prev
            e.hash = _entry_hash(i, e.ts, e.actor, e.action, e.payload_hash, prev)
            prev = e.hash
            s.add(e)
        s.commit()
        return len(pending)


def verify_chain(session: Session) -> dict[str, Any]:
    """Seal pending entries, then recompute every hash.
    Returns {valid, entries, broken_at (chain index), reason, head}."""
    seal(session.get_bind())
    session.expire_all()
    prev_hash = GENESIS_HASH
    expected = 1
    count = 0
    rows = session.exec(select(AuditEntry).order_by(AuditEntry.chain_index))
    for entry in rows:
        count += 1
        reason = None
        if entry.chain_index is None:
            reason = "unsealed entry"
        elif entry.chain_index != expected:
            reason = f"chain gap: expected {expected}, found {entry.chain_index}"
        elif entry.prev_hash != prev_hash:
            reason = "prev_hash does not match the previous entry"
        elif sha256_hex(canonical_json(entry.payload)) != entry.payload_hash:
            reason = "payload was modified"
        elif (
            _entry_hash(
                entry.chain_index, entry.ts, entry.actor, entry.action, entry.payload_hash, entry.prev_hash
            )
            != entry.hash
        ):
            reason = "entry hash mismatch"
        if reason:
            return {
                "valid": False,
                "entries": count,
                "broken_at": entry.chain_index,
                "reason": reason,
                "head": None,
            }
        prev_hash = entry.hash
        expected += 1
    return {"valid": True, "entries": count, "broken_at": None, "reason": None, "head": prev_hash}
