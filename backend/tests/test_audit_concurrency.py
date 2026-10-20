import threading

from sqlalchemy import create_engine, text

from app.core.db import BACKEND_DIR, run_migrations
from app.core.security import canonical_json, sha256_hex


def test_concurrent_writers_keep_the_chain_valid(client):
    """Regression: parallel requests used to race on the next ledger position
    (UNIQUE constraint failed: audit_ledger.seq)."""
    errors: list[str] = []

    def login(user: str, pwd: str):
        r = client.post("/auth/login", json={"username": user, "password": pwd})
        if r.status_code != 200:
            errors.append(f"{r.status_code} {r.text[:80]}")

    users = [
        ("worker1", "worker123"),
        ("assessor1", "assessor123"),
        ("qa1", "qa123"),
        ("admin", "admin123"),
    ] * 3
    threads = [threading.Thread(target=login, args=u) for u in users]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []
    token = client.post("/auth/login", json={"username": "qa1", "password": "qa123"}).json()["access_token"]
    v = client.get("/audit/verify", headers={"Authorization": f"Bearer {token}"}).json()
    assert v["valid"] is True and v["entries"] >= 7 + len(users)


def _old_hash(seq, ts, actor, action, payload_hash, prev):
    return sha256_hex(f"{seq}|{ts}|{actor}|{action}|{payload_hash}|{prev}")


def test_migration_keeps_an_existing_ledger_valid(tmp_path):
    """A ledger written by the previous (in-transaction) scheme must still verify after upgrade."""
    from alembic import command
    from alembic.config import Config

    url = f"sqlite:///{(tmp_path / 'old.db').as_posix()}"
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "cf66b06047d9")  # the revision before append-then-seal
    engine = create_engine(url)
    prev = "0" * 64
    with engine.begin() as conn:
        for seq in (1, 2, 3):
            payload = {"n": seq}
            ph = sha256_hex(canonical_json(payload))
            h = _old_hash(seq, "2026-10-19T10:00:00.000000Z", "system", "old.write", ph, prev)
            conn.execute(
                text(
                    "INSERT INTO audit_ledger "
                    "(seq, ts, actor, action, payload, payload_hash, prev_hash, hash) "
                    "VALUES (:s, '2026-10-19T10:00:00.000000Z', 'system', 'old.write', :p, :ph, :prev, :h)"
                ),
                {"s": seq, "p": canonical_json(payload), "ph": ph, "prev": prev, "h": h},
            )
            prev = h
    engine.dispose()
    run_migrations(url)

    from sqlmodel import Session

    from app.services import audit

    engine = create_engine(url)
    with Session(engine) as s:
        audit.record(s, "system", "new.write", {"n": 4})
        s.commit()
        result = audit.verify_chain(s)
    assert result == {**result, "valid": True, "entries": 4}


def test_models_match_migrations(tmp_path):
    from alembic import command
    from alembic.config import Config

    url = f"sqlite:///{(tmp_path / 'check.db').as_posix()}"
    run_migrations(url)
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", url)
    command.check(cfg)  # raises if autogenerate would produce a new migration
