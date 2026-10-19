from sqlalchemy import text
from sqlmodel import Session

from app.services import audit


def test_chain_is_valid_after_normal_activity(client, auth):
    client.post("/consents", json={"purposes": ["rpl_assessment"], "language": "hi"}, headers=auth("worker1"))
    r = client.get("/audit/verify", headers=auth("qa1"))
    assert r.status_code == 200
    body = r.json()
    assert body["valid"] is True
    assert body["entries"] >= 9  # 7 seeded users + logins + consent


def test_tampering_with_one_row_breaks_verification(client, auth):
    headers = auth("qa1")
    client.post("/consents", json={"purposes": ["rpl_assessment"]}, headers=auth("worker1"))
    assert client.get("/audit/verify", headers=headers).json()["valid"] is True

    engine = client.app.state.engine
    with engine.begin() as conn:
        conn.execute(text("UPDATE audit_ledger SET actor = 'mallory' WHERE seq = 3"))
    body = client.get("/audit/verify", headers=headers).json()
    assert body["valid"] is False
    assert body["broken_at"] == 3


def test_payload_tampering_detected(client):
    engine = client.app.state.engine
    with Session(engine) as s:
        e = audit.record(s, "tester", "demo.write", {"score": 2})
        s.commit()
        seq = e.seq
    with engine.begin() as conn:
        conn.execute(text("UPDATE audit_ledger SET payload = '{\"score\": 3}' WHERE seq = :s"), {"s": seq})
    with Session(engine) as s:
        result = audit.verify_chain(s)
    assert result["valid"] is False and result["reason"] == "payload was modified"


def test_deleting_a_row_breaks_verification(client):
    engine = client.app.state.engine
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM audit_ledger WHERE seq = 2"))
    with Session(engine) as s:
        result = audit.verify_chain(s)
    assert result["valid"] is False and result["broken_at"] == 3


def test_audit_verify_requires_privileged_role(client, auth):
    assert client.get("/audit/verify", headers=auth("worker1")).status_code == 403
    assert client.get("/audit/entries", headers=auth("assessor1")).status_code == 403
    assert client.get("/audit/entries", headers=auth("admin")).status_code == 200
