import pytest

from app.services.profile import build_profile
from app.services.qp_store import iter_pcs, load_corpus
from tests.helpers import WELDING, started_assessment


@pytest.fixture(scope="module")
def qp():
    return load_corpus()[WELDING]


def _all(qp, level):
    return {p["id"]: level for p in iter_pcs(qp)}


def test_all_competent_is_full(qp):
    p = build_profile(qp, _all(qp, 2))
    assert p["aggregate_percent"] == 80.0 and p["max_total"] == 450
    assert p["recommendation"] == "full" and not p["bridge_modules"]
    assert all(n["status"] == "competent" for n in p["nos"])


def test_marks_follow_each_pcs_theory_practical_viva_split(qp):
    p = build_profile(qp, _all(qp, 3))
    gtaw = next(n for n in p["nos"] if n["nos_id"] == "ASC/N3124")
    assert gtaw["earned"] == {"theory": 15.0, "practical": 25.0, "viva": 10.0}
    assert p["earned_total"] == 450.0


def test_gtaw_gap_gives_partial_with_bridge_module(qp):
    scores = _all(qp, 2)
    for pc in iter_pcs(qp):
        if pc["nos_id"] == "ASC/N3124":
            scores[pc["id"]] = 0
    p = build_profile(qp, scores)
    gtaw = next(n for n in p["nos"] if n["nos_id"] == "ASC/N3124")
    assert gtaw["status"] == "gap" and gtaw["percent"] == 0.0
    assert p["recommendation"] == "partial"
    assert "ASC/N3124 PC3" in p["critical_below_standard"]
    assert [b["nos_id"] for b in p["bridge_modules"]] == ["ASC/N3124"]
    assert "GTAW" in p["bridge_modules"][0]["title"]
    # aggregate still above 70% but a critical PC failed -> not Full
    assert p["aggregate_percent"] >= 70


def test_critical_pc_below_standard_blocks_full(qp):
    scores = _all(qp, 3)
    scores["ASC-N3120.PC1"] = 1  # critical: machine set-up
    p = build_profile(qp, scores)
    assert p["aggregate_percent"] > 90 and p["recommendation"] == "partial"


def test_all_weak_is_gap(qp):
    p = build_profile(qp, _all(qp, 1))
    assert p["aggregate_percent"] == 40.0 and p["recommendation"] == "gap"
    assert len(p["bridge_modules"]) == 7


def test_unassessed_pcs_prevent_full(qp):
    scores = _all(qp, 3)
    scores.pop("ASC-N9819.PC8")
    p = build_profile(qp, scores)
    assert p["unassessed_pcs"] == 1 and p["recommendation"] == "partial"


def test_profile_endpoint_and_readiness(client, auth):
    a, assessor = started_assessment(client, auth)
    h = auth(assessor)
    client.post(f"/assessments/{a['id']}/scores", json={"pc_id": "ASC-N3124.PC1", "score": 2}, headers=h)
    r = client.get(f"/assessments/{a['id']}/profile", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["readiness"]["scored"] == 1 and body["readiness"]["total"] == 48
    assert body["recommendation"] in ("partial", "gap")
    assert client.get(f"/assessments/{a['id']}/profile", headers=auth("qa1")).status_code == 200
    # workers only see it after sign-off
    assert client.get(f"/assessments/{a['id']}/profile", headers=auth("worker1")).status_code == 403
