def test_notice_available_in_hindi_and_english(client):
    hi = client.get("/consents/notice?lang=hi").json()
    en = client.get("/consents/notice?lang=en").json()
    assert hi["language"] == "hi" and "सहमति" in hi["title"]
    assert en["version"] == hi["version"]
    assert hi["sha256"] != en["sha256"]


def test_consent_grant_and_withdraw_is_append_only(client, auth):
    h = auth("worker1")
    notice = client.get("/consents/notice?lang=hi").json()
    r = client.post(
        "/consents",
        json={
            "purposes": ["rpl_assessment", "evidence_capture"],
            "language": "hi",
            "notice_sha256": notice["sha256"],
        },
        headers=h,
    )
    assert r.status_code == 201 and len(r.json()) == 2
    state = client.get("/consents/me", headers=h).json()["state"]
    assert state["rpl_assessment"] is True and state["voice_processing"] is False

    client.post("/consents", json={"purposes": ["evidence_capture"], "granted": False}, headers=h)
    me = client.get("/consents/me", headers=h).json()
    assert me["state"]["evidence_capture"] is False
    assert len(me["history"]) == 3  # nothing was overwritten


def test_stale_notice_hash_is_rejected(client, auth):
    r = client.post(
        "/consents", json={"purposes": ["rpl_assessment"], "notice_sha256": "0" * 64}, headers=auth("worker1")
    )
    assert r.status_code == 409


def test_unknown_purpose_rejected(client, auth):
    r = client.post("/consents", json={"purposes": ["marketing"]}, headers=auth("worker1"))
    assert r.status_code == 422
