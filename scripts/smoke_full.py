"""Smoke test for Docker full mode (run after `docker compose up -d --wait`).

    backend/.venv/Scripts/python scripts/smoke_full.py      (Windows)
    backend/.venv/bin/python scripts/smoke_full.py          (macOS / Linux)

Checks, against the running stack:
  1. /health reports full mode on PostgreSQL
  2. worker consents, declares and requests an assessment; the assessor starts it
  3. three signed P-P-P shots upload; the image is read back from the S3 object store
  4. the Celery worker writes the shadow-rater analysis for the product shot
  5. pgvector: CREATE EXTENSION, upsert and cosine search through PgVectorIndex
  6. the audit hash chain verifies on Postgres
Uses the demo accounts (local defaults). Exits non-zero on the first failure.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from tests.helpers import Device, jpeg_bytes, started_assessment  # noqa: E402

API = os.environ.get("SMOKE_API", "http://localhost:8000")
PASSWORDS = {"worker": "worker123", "assessor": "assessor123", "qa": "qa123", "admin": "admin123"}


def step(msg: str) -> None:
    print(f"[smoke] {msg}", flush=True)


def compose(*args: str) -> str:
    out = subprocess.run(
        ["docker", "compose", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8"
    )
    if out.returncode != 0:
        raise SystemExit(f"docker compose {' '.join(args)} failed:\n{out.stderr}")
    return out.stdout.strip()


def psql(sql: str) -> str:
    return compose("exec", "-T", "postgres", "psql", "-U", "skillsync", "-d", "skillsync", "-tAc", sql)


def main() -> None:
    client = httpx.Client(base_url=API, timeout=30)
    cache: dict[str, dict] = {}

    def auth(username: str) -> dict:
        if username not in cache:
            pwd = next(v for k, v in PASSWORDS.items() if username.startswith(k))
            r = client.post("/auth/login", json={"username": username, "password": pwd})
            assert r.status_code == 200, r.text
            cache[username] = {"Authorization": f"Bearer {r.json()['access_token']}"}
        return cache[username]

    h = client.get("/health").json()
    assert h["mode"] == "full" and h["database"] == "postgresql" and h["db_ok"], h
    step(f"health ok: {h['mode']} mode on {h['database']}")

    a, assessor = started_assessment(client, auth)
    assert a["status"] == "in_progress", a
    step(f"assessment {a['id']} started by {assessor}")

    dev = Device()
    dev.register(client, auth(assessor))
    ids = {}
    for i, shot in enumerate(("process", "product", "person")):
        data = jpeg_bytes(seed=1000 + i + int(time.time()) % 1000)
        r = dev.upload(client, auth(assessor), a, shot, data)
        assert r.status_code == 201, r.text
        ids[shot] = (r.json()["id"], data)
    step(f"3 signed shots uploaded: {sorted(ids)}")

    ev_id, data = ids["product"]
    img = client.get(f"/evidence/{ev_id}/image", headers=auth(assessor))
    assert img.status_code == 200 and img.content == data, img.status_code
    key = psql(f"SELECT file_path FROM evidence WHERE id = {ev_id}")
    listed = compose(
        "exec", "-T", "backend", "python", "-c",
        "from app.core.config import get_settings; from app.services.storage import make_storage;"
        f"s = make_storage(get_settings()); print(type(s).__name__, s.exists({key!r}))",
    )  # fmt: skip
    assert listed == "S3Storage True", listed
    step(f"image read back byte-for-byte; object {key} is in the S3 store")

    for _ in range(60):
        n = int(psql(f"SELECT count(*) FROM ai_analyses WHERE evidence_id = {ev_id}") or 0)
        if n:
            break
        time.sleep(1)
    else:
        raise SystemExit("no ai_analyses row after 60 s; check `docker compose logs worker`")
    logs = compose("logs", "worker")
    assert f"analysed evidence {ev_id}" in logs, "worker log does not mention the task"
    step("Celery worker wrote the shadow-rater analysis")

    pgvector_check = "\n".join(
        [
            "from sqlalchemy import text",
            "from app.core.config import get_settings",
            "from app.core.db import make_engine",
            "from app.services.vector_index import PgVectorIndex",
            "e = make_engine(get_settings())",
            "ix = PgVectorIndex(e, 3, table='smoke_vectors')",
            "ix.add('a', [1, 0, 0]); ix.add('b', [0, 1, 0]); ix.add('a', [0.9, 0.1, 0])",
            "r = ix.search([1, 0, 0], k=2)",
            "print(len(ix), r[0][0], round(r[0][1], 3))",
            "with e.begin() as c:",
            "    c.execute(text('DROP TABLE smoke_vectors'))",
        ]
    )
    vec = compose("exec", "-T", "backend", "python", "-c", pgvector_check)
    n, top, sim = vec.split()
    assert n == "2" and top == "a" and float(sim) > 0.99, vec
    step(f"pgvector ok: upsert kept 2 rows, nearest 'a' (cosine {sim})")

    chain = client.get("/audit/verify", headers=auth("admin")).json()
    assert chain["valid"], chain
    step(f"audit chain valid on Postgres: {chain['entries']} entries")
    step("ALL CHECKS PASSED")


if __name__ == "__main__":
    main()
