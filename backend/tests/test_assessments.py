WELDING = "QG-4.5-AU-01811-2024-V1-ASDC"
GOLDEN = "CO2 aur argon dono welding karta hoon, grinding karke finishing deta hoon"


def _declare(client, auth, user="worker1", client_id=None):
    h = auth(user)
    client.post("/consents", json={"purposes": ["rpl_assessment"]}, headers=h)
    body = {"narrative": GOLDEN}
    if client_id:
        body["client_id"] = client_id
    return client.post("/declarations", json=body, headers=h).json()


def test_worker_confirms_qp_and_request_is_assigned(client, auth):
    d = _declare(client, auth)
    claimed = ["ASC-N3124.PC1", "ASC-N3124.PC5", "BOGUS.PC9"]
    r = client.post(
        "/assessments",
        json={"qp_id": WELDING, "declaration_id": d["id"], "claimed_pc_ids": claimed, "client_id": "req-1"},
        headers=auth("worker1"),
    )
    assert r.status_code == 201, r.text
    a = r.json()
    assert a["status"] == "requested"
    assert a["claimed_pc_ids"] == ["ASC-N3124.PC1", "ASC-N3124.PC5"]  # unknown PC ids dropped
    assert a["assessor_id"] is not None
    assert "is_golden" not in a and "challenge_code" not in a  # hidden from workers
    assert client.get(f"/declarations/{d['id']}", headers=auth("worker1")).json()["status"] == "confirmed"
    # idempotent retry
    again = client.post(
        "/assessments",
        json={"qp_id": WELDING, "declaration_id": d["id"], "client_id": "req-1"},
        headers=auth("worker1"),
    )
    assert again.json()["id"] == a["id"]
    assert [x["id"] for x in client.get("/assessments/mine", headers=auth("worker1")).json()] == [a["id"]]


def test_request_by_declaration_client_id_supports_offline_ordering(client, auth):
    _declare(client, auth, client_id="dev-decl-77")
    r = client.post(
        "/assessments",
        json={"qp_id": WELDING, "declaration_client_id": "dev-decl-77"},
        headers=auth("worker1"),
    )
    assert r.status_code == 201
    missing = client.post(
        "/assessments",
        json={"qp_id": WELDING, "declaration_client_id": "not-synced-yet"},
        headers=auth("worker1"),
    )
    assert missing.status_code == 404


def test_least_loaded_assessor_assignment(client, auth):
    ids = []
    for _ in range(3):
        d = _declare(client, auth)
        ids.append(
            client.post(
                "/assessments", json={"qp_id": WELDING, "declaration_id": d["id"]}, headers=auth("worker1")
            ).json()["assessor_id"]
        )
    assert len(set(ids)) == 3  # spread across assessor1..3


def test_cannot_request_on_someone_elses_declaration(client, auth):
    d = _declare(client, auth, user="worker1")
    r = client.post(
        "/assessments", json={"qp_id": WELDING, "declaration_id": d["id"]}, headers=auth("worker2")
    )
    assert r.status_code == 403


def test_pack_ships_consent_notices(client):
    pack = client.get("/packs/latest").json()
    assert set(pack["consent_notices"]) == {"en", "hi"}
    assert pack["tokenizer"]["hinglish_markers"]
