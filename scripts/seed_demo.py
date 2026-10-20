"""One command -> a fully populated SkillSync demo (lite mode by default).

    backend/.venv/Scripts/python scripts/seed_demo.py            (Windows)
    backend/.venv/bin/python scripts/seed_demo.py                (macOS / Linux)
    ... scripts/seed_demo.py --reset     wipe the SQLite demo DB + evidence first

It drives the real API in-process (FastAPI TestClient), so every row goes through the
same validation, signatures and hash-chained audit ledger as a live session. It uses the
DATABASE_URL / STORAGE_DIR from .env. Stop the API server before --reset.

What you get (everything marked SYNTHETIC is generated, not real people or welds):
  - worker1 is left untouched for the live golden-path demo (consent -> Hindi declaration ...)
  - 6 SYNTHETIC workers (worker3..worker8) with Hindi / Hinglish / English declarations
  - assessments in every state: requested, in_progress (with a REUSED-photo flag),
    scored (awaiting sign-off) and signed_off with a W3C verifiable credential (worker2)
  - golden packets in every assessor's queue, scored so the QA dashboard shows alpha + drift
"""

from __future__ import annotations

import argparse
import importlib.util
import random
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import get_settings
from app.core.security import hash_password
from app.main import create_app
from app.models.audit import AuditEntry
from app.models.user import Role, User
from app.services import audit
from app.services.qp_store import iter_pcs, load_corpus
from tests.helpers import WELDING, Device, jpeg_bytes

SAMPLES = ROOT / "frontend" / "public" / "samples"
GTAW_NOS = "ASC/N3124"  # the demo's "GTAW gap" -> Partial + bridge module
PURPOSES = ["rpl_assessment", "evidence_capture"]


def load_generator():
    spec = importlib.util.spec_from_file_location(
        "generate_synthetic", ROOT / "scripts" / "generate_synthetic.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["generate_synthetic"] = mod
    spec.loader.exec_module(mod)
    return mod


class Demo:
    def __init__(self, client: TestClient, settings) -> None:
        self.c, self.settings, self._tokens = client, settings, {}

    def h(self, username: str) -> dict:
        if username not in self._tokens:
            pwd = {
                "worker": self.settings.demo_password_worker,
                "assessor": self.settings.demo_password_assessor,
                "qa": self.settings.demo_password_qa,
                "admin": self.settings.demo_password_admin,
            }[next(k for k in ("worker", "assessor", "qa", "admin") if username.startswith(k))]
            r = self.c.post("/auth/login", json={"username": username, "password": pwd})
            r.raise_for_status()
            self._tokens[username] = {"Authorization": f"Bearer {r.json()['access_token']}"}
        return self._tokens[username]

    def ok(self, r, *codes):
        if r.status_code not in (codes or (200, 201)):
            raise SystemExit(f"[seed] {r.request.method} {r.request.url.path} -> {r.status_code}: {r.text}")
        return r.json()

    def declare(self, worker: str, narrative: str, language: str, mode: str = "voice") -> tuple[dict, dict]:
        self.ok(self.c.post("/consents", json={"purposes": PURPOSES}, headers=self.h(worker)))
        d = self.ok(
            self.c.post(
                "/declarations",
                json={"narrative": narrative, "language": language, "input_mode": mode},
                headers=self.h(worker),
            )
        )
        m = self.ok(self.c.post(f"/declarations/{d['id']}/map", headers=self.h(worker)))
        return d, m

    def request(self, worker: str, decl: dict, mapping: dict, qp_id: str | None = None) -> dict:
        qp_id = qp_id or mapping["top"][0]["qp_id"]
        claimed = [c["pc_id"] for c in mapping.get("claims", {}).get(qp_id, []) if c["claimed"]]
        body = {"qp_id": qp_id, "declaration_id": decl["id"], "claimed_pc_ids": claimed}
        return self.ok(self.c.post("/assessments", json=body, headers=self.h(worker)))

    def assessor_of(self, a: dict) -> str:
        users = self.ok(self.c.get("/users?role=assessor", headers=self.h("admin")))
        return next(u["username"] for u in users if u["id"] == a["assessor_id"])

    def start(self, a: dict) -> tuple[dict, str]:
        assessor = self.assessor_of(a)
        return self.ok(self.c.post(f"/assessments/{a['id']}/start", headers=self.h(assessor))), assessor

    def capture(self, a: dict, assessor: str, product: bytes, seed: int) -> list[dict]:
        dev = Device()
        dev.register(self.c, self.h(assessor))
        out = []
        for shot, data in (
            ("process", jpeg_bytes(seed)),
            ("product", product),
            ("person", jpeg_bytes(seed + 1)),
        ):
            out.append(self.ok(dev.upload(self.c, self.h(assessor), a, shot, data), 201))
        return out

    def score(self, a: dict, assessor: str, level_for) -> None:
        for pc in iter_pcs(load_corpus()[a["qp_id"]]):
            self.ok(
                self.c.post(
                    f"/assessments/{a['id']}/scores",
                    json={"pc_id": pc["id"], "score": level_for(pc)},
                    headers=self.h(assessor),
                ),
                200,
                201,
            )
        rows = self.ok(self.c.get(f"/assessments/{a['id']}/scores", headers=self.h(assessor)))
        for row in rows:  # big human/AI gaps need a reason code before sign-off
            if row["reason_required"] and not row["reason_code"]:
                self.ok(
                    self.c.patch(
                        f"/assessments/{a['id']}/scores/{row['pc_id']}",
                        json={"reason_code": "observed_live_differently"},
                        headers=self.h(assessor),
                    )
                )


def add_synthetic_workers(session: Session, settings, workers: list[dict]) -> None:
    for i, w in enumerate(workers, start=3):
        username = f"worker{i}"
        if session.exec(select(User).where(User.username == username)).first():
            continue
        session.add(
            User(
                username=username,
                full_name=w["name"],  # already ends with "(synthetic)"
                role=str(Role.worker),
                centre="Synthetic cohort",
                password_hash=hash_password(settings.demo_password_worker),
            )
        )
        audit.record(
            session, "system", "user.seeded", {"username": username, "role": "worker", "synthetic": True}
        )
    session.commit()


def reset(settings) -> None:
    url = settings.resolved_database_url
    if not url.startswith("sqlite:///"):
        raise SystemExit("[seed] --reset only wipes the SQLite demo DB; drop other databases yourself")
    db = Path(url[len("sqlite:///") :])
    for p in (db, db.with_name(db.name + "-wal"), db.with_name(db.name + "-shm")):
        p.unlink(missing_ok=True)
    for sub in ("evidence", "uploads"):
        shutil.rmtree(settings.storage_path / sub, ignore_errors=True)
    print(f"[seed] reset {db.name} and evidence storage (issuer key kept)")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--reset", action="store_true", help="wipe the SQLite demo DB and evidence first")
    args = ap.parse_args()
    settings = get_settings()
    if args.reset:
        reset(settings)

    app = create_app(settings)
    with TestClient(app) as client:
        with Session(app.state.engine) as s:
            if s.exec(select(AuditEntry).where(AuditEntry.action == "demo.seeded")).first():
                print("[seed] demo data already present (use --reset for a fresh demo)")
                return
        demo = Demo(client, settings)
        gen = load_generator()
        pool = gen.generate_workers(random.Random(26242))
        welders = [w for w in pool if w["ground_truth_qp"] == WELDING]
        others = [w for w in pool if w["ground_truth_qp"] != WELDING]
        synthetic = welders[:4] + others[:2]  # worker3..worker8
        with Session(app.state.engine) as s:
            add_synthetic_workers(s, settings, synthetic)
        print(f"[seed] {len(synthetic)} SYNTHETIC workers: worker3..worker{2 + len(synthetic)}")

        good = (SAMPLES / "weld_00_good.jpg").read_bytes()
        porous = (SAMPLES / "weld_05_porosity.jpg").read_bytes()
        summary = []

        # signed_off + credential: worker2 (Salma), Welding, GTAW gap -> Partial
        d, m = demo.declare(
            "worker2",
            "8 saal se MIG aur stick welding karti hoon, plate fit-up, grinding aur finishing bhi",
            "hinglish",
        )
        a, assessor = demo.start(demo.request("worker2", d, m, WELDING))
        demo.capture(a, assessor, good, seed=2001)
        demo.score(a, assessor, lambda pc: 0 if pc["nos_id"] == GTAW_NOS else 3)
        prof = demo.ok(client.get(f"/assessments/{a['id']}/profile", headers=demo.h(assessor)))
        cred = demo.ok(
            client.post(
                f"/assessments/{a['id']}/signoff",
                json={
                    "password": settings.demo_password_assessor,
                    "decision": prof["recommendation"],
                    "confirm": True,
                },
                headers=demo.h(assessor),
            )
        )
        summary.append(
            (
                "worker2",
                a["id"],
                "signed_off",
                f"credential {cred['credential_id']} ({prof['recommendation']})",
            )
        )

        # in_progress with a REUSED product photo (same bytes as worker2's) -> flagged
        w = synthetic[0]
        d, m = demo.declare("worker3", w["narrative"], w["language"])
        a, assessor = demo.start(demo.request("worker3", d, m, WELDING))
        ev = demo.capture(a, assessor, good, seed=3001)
        flags = [f["code"] for e in ev for f in (e.get("integrity_flags") or [])]
        summary.append(("worker3", a["id"], "in_progress", f"evidence flags: {sorted(set(flags)) or 'none'}"))

        # scored, awaiting sign-off (porous product photo -> AI disagrees on PC1, reason filled)
        w = synthetic[1]
        d, m = demo.declare("worker4", w["narrative"], w["language"])
        a, assessor = demo.start(demo.request("worker4", d, m, WELDING))
        demo.capture(a, assessor, porous, seed=4001)
        demo.score(a, assessor, lambda pc: 2)
        summary.append(("worker4", a["id"], "scored", "awaiting assessor sign-off"))

        # requested (not started yet) for a welder and two other trades
        for username, w in (("worker5", synthetic[2]), ("worker7", synthetic[4]), ("worker8", synthetic[5])):
            d, m = demo.declare(username, w["narrative"], w["language"], mode="typed")
            a = demo.request(username, d, m)
            summary.append((username, a["id"], a["status"], f"{a['qp_id']} (top match)"))

        # declared only (mapped, no assessment requested yet)
        w = synthetic[3]
        d, m = demo.declare("worker6", w["narrative"], w["language"], mode="cards")
        summary.append(("worker6", "-", "declared", f"top match {m['top'][0]['qp_id']}"))

        # golden packets (SYNTHETIC consensus) in every queue, scored: assessor3 is lenient (+1)
        created = demo.ok(
            client.post("/calibration/golden/seed", json={"per_assessor": 4}, headers=demo.h("qa1"))
        )
        for assessor, offset in (("assessor1", 0), ("assessor2", 0), ("assessor3", 1)):
            for card in demo.ok(client.get("/assessor/queue", headers=demo.h(assessor))):
                full = demo.ok(client.get(f"/assessments/{card['id']}", headers=demo.h("admin")))
                if not full.get("is_golden"):
                    continue
                packets = {p["id"]: p for p in gen_packets()}
                consensus = packets[full["golden_packet_id"]]["consensus"]
                for pc_id, level in consensus.items():
                    client.post(
                        f"/assessments/{card['id']}/scores",
                        json={"pc_id": pc_id, "score": max(0, min(3, level + offset))},
                        headers=demo.h(assessor),
                    )
        summary.append(("assessors", "-", "golden", f"{created['created']} SYNTHETIC golden packets scored"))

        with Session(app.state.engine) as s:
            audit.record(s, "system", "demo.seeded", {"rows": len(summary)})
            s.commit()
        chain = demo.ok(client.get("/audit/verify", headers=demo.h("admin")))

    print("\n  user       assessment  state        note")
    for user, aid, state, note in summary:
        print(f"  {user:<10} {aid!s:<11} {state:<12} {note}")
    print(f"\n[seed] audit chain valid: {chain['valid']} ({chain['entries']} entries)")
    print(f"[seed] verify the credential: {settings.public_app_url}/verify/{cred['credential_id']}")
    print("[seed] live demo: log in as worker1 (left untouched) and follow docs/DEMO_SCRIPT.md")


def gen_packets() -> list[dict]:
    import json

    return json.loads((ROOT / "data" / "golden_packets" / "golden_packets.json").read_text(encoding="utf-8"))[
        "packets"
    ]


if __name__ == "__main__":
    main()
