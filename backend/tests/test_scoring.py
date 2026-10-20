import json

from app.core.config import REPO_ROOT
from app.services.qp_store import iter_pcs, load_corpus
from tests.helpers import WELDING, Device, started_assessment

POROSITY_SAMPLE = REPO_ROOT / "frontend" / "public" / "samples" / "weld_04_porosity.jpg"
GOOD_SAMPLE = REPO_ROOT / "frontend" / "public" / "samples" / "weld_00_good.jpg"
IMAGE_PC = "ASC-N3125.PC1"  # ai_signal = porosity
LIVE_PC = "ASC-N3124.PC3"  # critical, observe: no image opinion


def _with_product_photo(client, auth, sample=POROSITY_SAMPLE, worker="worker1"):
    a, assessor = started_assessment(client, auth, worker=worker)
    h = auth(assessor)
    dev = Device()
    dev.register(client, h)
    r = dev.upload(client, h, a, "product", sample.read_bytes())
    assert r.status_code == 201, r.text
    return a, assessor, h


def _contains_ai(obj) -> bool:
    text = json.dumps(obj)
    return any(k in text for k in ('"ai_level"', '"defect_probs"', '"level_probs"', '"ai_explanation"'))


def test_ai_cannot_be_seen_before_the_blind_score(client, auth):
    a, _, h = _with_product_photo(client, auth)
    # nothing revealed yet, via any route
    assert client.get(f"/assessments/{a['id']}/ai-suggestions", headers=h).json() == []
    r = client.get(f"/assessments/{a['id']}/ai-suggestions?pc_id={IMAGE_PC}", headers=h)
    assert r.status_code == 403 and "Blind-first" in r.json()["detail"]
    for path in (
        f"/assessments/{a['id']}",
        f"/assessments/{a['id']}/plan",
        f"/assessments/{a['id']}/evidence",
        f"/assessments/{a['id']}/scores",
        "/assessor/queue",
    ):
        assert not _contains_ai(client.get(path, headers=h).json()), path


def test_reveal_after_blind_score_and_reason_code_for_big_gap(client, auth):
    a, _, h = _with_product_photo(client, auth)
    r = client.post(f"/assessments/{a['id']}/scores", json={"pc_id": IMAGE_PC, "score": 3}, headers=h)
    assert r.status_code == 201
    body = r.json()
    assert body["score"]["blind_score"] == 3
    ai = body["ai"]
    assert ai["status"] == "ok" and ai["level"] <= 1  # porous weld: the AI disagrees with a 3
    assert ai["gap"] == 3 - ai["level"] and ai["reason_required"] is True
    assert "synthetic" in ai["model_label"].lower()

    # now visible through the gated endpoint, for this PC only
    sugg = client.get(f"/assessments/{a['id']}/ai-suggestions", headers=h).json()
    assert [s["pc_id"] for s in sugg] == [IMAGE_PC]
    assert client.get(f"/assessments/{a['id']}/ai-suggestions?pc_id={IMAGE_PC}", headers=h).status_code == 200

    # big gap: a reason is mandatory; 'other' needs a note
    assert (
        client.patch(
            f"/assessments/{a['id']}/scores/{IMAGE_PC}", json={"final_score": 2}, headers=h
        ).status_code
        == 422
    )
    assert (
        client.patch(
            f"/assessments/{a['id']}/scores/{IMAGE_PC}", json={"reason_code": "other"}, headers=h
        ).status_code
        == 422
    )
    ok = client.patch(
        f"/assessments/{a['id']}/scores/{IMAGE_PC}",
        json={"final_score": 2, "reason_code": "observed_live_differently"},
        headers=h,
    )
    assert ok.status_code == 200
    assert ok.json()["blind_score"] == 3 and ok.json()["final_score"] == 2  # original kept

    ledger = client.get("/audit/entries?action=score.blind", headers=auth("qa1")).json()
    assert any(e["payload"]["pc_id"] == IMAGE_PC and e["payload"]["score"] == 3 for e in ledger)
    assert client.get("/audit/verify", headers=auth("qa1")).json()["valid"] is True


def test_blind_score_is_immutable(client, auth):
    a, _, h = _with_product_photo(client, auth)
    first = client.post(f"/assessments/{a['id']}/scores", json={"pc_id": IMAGE_PC, "score": 1}, headers=h)
    same = client.post(f"/assessments/{a['id']}/scores", json={"pc_id": IMAGE_PC, "score": 1}, headers=h)
    assert same.status_code == 201 and same.json()["score"]["id"] == first.json()["score"]["id"]
    changed = client.post(f"/assessments/{a['id']}/scores", json={"pc_id": IMAGE_PC, "score": 3}, headers=h)
    assert changed.status_code == 409


def test_live_observation_pc_gets_no_ai_opinion(client, auth):
    a, _, h = _with_product_photo(client, auth)
    r = client.post(f"/assessments/{a['id']}/scores", json={"pc_id": LIVE_PC, "score": 2}, headers=h).json()
    assert r["ai"]["status"] == "none" and r["ai"]["level"] is None and r["ai"]["reason_required"] is False


def test_image_pc_without_photo_waits(client, auth):
    a, assessor = started_assessment(client, auth)
    r = client.post(
        f"/assessments/{a['id']}/scores", json={"pc_id": IMAGE_PC, "score": 2}, headers=auth(assessor)
    ).json()
    assert r["ai"]["status"] == "awaiting_photo"


def test_only_the_assigned_assessor_can_score(client, auth):
    a, assessor, _ = _with_product_photo(client, auth)
    other = next(u for u in ("assessor1", "assessor2", "assessor3") if u != assessor)
    body = {"pc_id": IMAGE_PC, "score": 2}
    assert client.post(f"/assessments/{a['id']}/scores", json=body, headers=auth(other)).status_code == 403
    assert (
        client.post(f"/assessments/{a['id']}/scores", json=body, headers=auth("worker1")).status_code == 403
    )
    assert client.get(f"/assessments/{a['id']}/ai-suggestions", headers=auth("qa1")).status_code == 403


def test_scoring_requires_a_started_assessment(client, auth):
    h = auth("worker1")
    client.post("/consents", json={"purposes": ["rpl_assessment"]}, headers=h)
    d = client.post("/declarations", json={"narrative": "argon welding"}, headers=h).json()
    a = client.post("/assessments", json={"qp_id": WELDING, "declaration_id": d["id"]}, headers=h).json()
    users = client.get("/users?role=assessor", headers=auth("admin")).json()
    assessor = next(u["username"] for u in users if u["id"] == a["assessor_id"])
    r = client.post(
        f"/assessments/{a['id']}/scores", json={"pc_id": IMAGE_PC, "score": 2}, headers=auth(assessor)
    )
    assert r.status_code == 409


def test_status_becomes_scored_when_every_pc_is_scored(client, auth):
    a, _, h = _with_product_photo(client, auth, sample=GOOD_SAMPLE)
    for pc in iter_pcs(load_corpus()[WELDING]):
        client.post(f"/assessments/{a['id']}/scores", json={"pc_id": pc["id"], "score": 2}, headers=h)
    assert client.get(f"/assessments/{a['id']}", headers=h).json()["status"] == "scored"


def test_pending_analysis_resolves_via_ai_refresh(client, auth):
    """Full mode: the photo is synced but the Celery analysis has not run yet."""
    from sqlmodel import Session, delete, select

    from app.models.evidence import Evidence
    from app.models.scoring import AIAnalysis
    from app.services.ai_service import analyse_evidence

    a, _, h = _with_product_photo(client, auth)
    st = client.app.state
    with Session(st.engine) as s:
        s.exec(delete(AIAnalysis).where(AIAnalysis.assessment_id == a["id"]))
        s.commit()
        ev_id = s.exec(select(Evidence.id).where(Evidence.assessment_id == a["id"])).first()

    url = f"/assessments/{a['id']}/scores/{IMAGE_PC}/ai-refresh"
    assert client.post(url, headers=h).status_code == 403  # blind-first: no score yet

    r = client.post(f"/assessments/{a['id']}/scores", json={"pc_id": IMAGE_PC, "score": 3}, headers=h).json()
    assert r["ai"]["status"] == "pending" and r["ai"]["level"] is None
    assert client.post(url, headers=h).json()["ai"]["status"] == "pending"  # still running

    analyse_evidence(st.engine, st.storage, st.rater, ev_id)  # the worker finishes
    ai = client.post(url, headers=h).json()["ai"]
    assert ai["status"] == "ok" and ai["level"] <= 1
    assert ai["gap"] == 3 - ai["level"] and ai["reason_required"] is True
    mine = next(
        x for x in client.get(f"/assessments/{a['id']}/scores", headers=h).json() if x["pc_id"] == IMAGE_PC
    )
    assert mine["ai_status"] == "ok" and mine["blind_score"] == 3  # the blind score never moves
    entries = client.get("/audit/entries?action=ai.revealed&limit=5", headers=auth("admin")).json()
    assert any(e["action"] == "ai.revealed" and e["payload"].get("late") for e in entries)
