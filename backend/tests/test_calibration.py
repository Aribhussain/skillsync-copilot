from app.services.golden import load_packets


def _seed(client, auth, per_assessor=10):
    r = client.post("/calibration/golden/seed", json={"per_assessor": per_assessor}, headers=auth("qa1"))
    assert r.status_code == 201, r.text
    return r.json()["created"]


def _score_golden(client, auth, username, offset=0):
    """Score every golden PC in this assessor's queue at consensus + offset (clipped)."""
    packets = load_packets()
    h = auth(username)
    for card in client.get("/assessor/queue", headers=h).json():
        # the assessor can't see it is golden; the test looks the packet up via QA-only data
        a = client.get(f"/assessments/{card['id']}", headers=auth("qa1")).json()
        if not a.get("is_golden"):
            continue
        for pc_id, level in packets[a["golden_packet_id"]]["consensus"].items():
            client.post(
                f"/assessments/{card['id']}/scores",
                json={"pc_id": pc_id, "score": max(0, min(3, level + offset))},
                headers=h,
            )


def test_golden_packets_look_like_normal_assessments(client, auth):
    assert _seed(client, auth, per_assessor=3) == 9
    queue = client.get("/assessor/queue", headers=auth("assessor1")).json()
    assert len(queue) == 3
    for card in queue:
        assert "is_golden" not in card and "golden_packet_id" not in card
        assert card["candidate"] and card["status"] == "in_progress"
        ev = client.get(f"/assessments/{card['id']}/evidence", headers=auth("assessor1")).json()
        assert ev[0]["signature_valid"] is True and ev[0]["shot"] == "product"


def test_alpha_and_calibration_index(client, auth):
    _seed(client, auth, per_assessor=10)
    _score_golden(client, auth, "assessor1", offset=0)
    _score_golden(client, auth, "assessor2", offset=0)
    _score_golden(client, auth, "assessor3", offset=+1)  # lenient assessor

    s = client.get("/calibration/summary", headers=auth("qa1")).json()
    assert s["units"] == 140 and s["scores"] == 420
    # one drifting assessor pulls alpha well below perfect agreement
    assert 0 < s["alpha_blind"] < 0.9
    assert s["assessors"]["assessor1"]["index"] == 100.0 and s["assessors"]["assessor1"]["bias"] == 0
    lenient = s["assessors"]["assessor3"]
    assert lenient["index"] < 100 and lenient["bias"] > 0
    assert len(s["heatmap"]["assessors"]) == 3 and s["heatmap"]["nos"]
    assert s["trend"] and s["alpha_per_pc"]

    me = client.get("/calibration/me", headers=auth("assessor3")).json()
    assert me["assessor"] == "assessor3" and me["index"] == lenient["index"]


def test_calibration_visibility(client, auth):
    assert client.get("/calibration/summary", headers=auth("assessor1")).status_code == 403
    assert client.get("/calibration/summary", headers=auth("worker1")).status_code == 403
    assert client.get("/calibration/me", headers=auth("qa1")).status_code == 403
    assert client.post("/calibration/golden/seed", json={}, headers=auth("assessor1")).status_code == 403


def test_alpha_is_one_when_everyone_agrees(client, auth):
    _seed(client, auth, per_assessor=10)
    for u in ("assessor1", "assessor2", "assessor3"):
        _score_golden(client, auth, u, offset=0)
    s = client.get("/calibration/summary", headers=auth("qa1")).json()
    assert s["alpha_blind"] == 1.0 and s["alpha_decision"] in (1.0, None)
