from app.services.signing import canonical_packet, sign_packet_for_tests, spki_b64, verify_packet
from tests.helpers import Device, jpeg_bytes, started_assessment


def test_canonical_packet_is_stable():
    p = {
        "assessment_id": 7,
        "shot": "product",
        "sha256": "AB" * 32,
        "captured_at": "2026-10-19T10:00:00.000Z",
        "device_id": "dev-1",
        "challenge_code": "QXW3AE",
        "gps": {"lat": 28.4, "lon": 77.31},
    }
    assert canonical_packet(p) == (
        "v1|7|product|" + "ab" * 32 + "|2026-10-19T10:00:00.000Z|dev-1|QXW3AE|28.400000|77.310000"
    )
    assert canonical_packet({**p, "gps": None}).endswith("|QXW3AE||")


def test_signature_roundtrip_and_tamper_detection():
    d = Device()
    p = {
        "assessment_id": 1,
        "shot": "person",
        "sha256": "0" * 64,
        "captured_at": "t",
        "device_id": d.device_id,
        "challenge_code": "AAAAAA",
        "gps": None,
    }
    sig = sign_packet_for_tests(d.key, p)
    pub = spki_b64(d.key.public_key())
    assert verify_packet(pub, p, sig)
    assert not verify_packet(pub, {**p, "challenge_code": "BBBBBB"}, sig)  # any field change breaks it
    assert not verify_packet(spki_b64(Device().key.public_key()), p, sig)  # other device's key
    assert not verify_packet(pub, p, "not-base64!!")


def test_valid_signed_upload_is_accepted(client, auth):
    a, assessor = started_assessment(client, auth)
    h = auth(assessor)
    dev = Device()
    dev.register(client, h)
    r = dev.upload(client, h, a, "product", jpeg_bytes(1))
    assert r.status_code == 201, r.text
    ev = r.json()
    assert ev["signature_valid"] is True and ev["shot"] == "product"
    assert ev["gps_lat"] == 28.4089
    # retrying the same packet (outbox) is idempotent
    again = dev.upload(client, h, a, "product", jpeg_bytes(1))
    assert again.json()["id"] == ev["id"]
    listing = client.get(f"/assessments/{a['id']}/evidence", headers=h).json()
    assert len(listing) == 1
    img = client.get(ev["image_url"], headers=h)
    assert img.status_code == 200 and img.content == jpeg_bytes(1)


def test_tampered_image_is_rejected(client, auth):
    a, assessor = started_assessment(client, auth)
    h = auth(assessor)
    dev = Device()
    dev.register(client, h)
    original = jpeg_bytes(2)
    packet = dev.packet(a, "product", original)
    r = dev.upload(client, h, a, "product", jpeg_bytes(3), packet=packet)  # different bytes, same packet
    assert r.status_code == 400 and "SHA-256" in r.json()["detail"]


def test_forged_signature_is_rejected(client, auth):
    a, assessor = started_assessment(client, auth)
    h = auth(assessor)
    dev = Device()
    dev.register(client, h)
    data = jpeg_bytes(4)
    forged = sign_packet_for_tests(Device().key, dev.packet(a, "process", data))  # signed by another key
    r = dev.upload(client, h, a, "process", data, signature=forged)
    assert r.status_code == 400 and "signature" in r.json()["detail"]


def test_unregistered_device_is_refused(client, auth):
    a, assessor = started_assessment(client, auth)
    r = Device().upload(client, auth(assessor), a, "process", jpeg_bytes(5))
    assert r.status_code == 403


def test_wrong_challenge_code_is_flagged(client, auth):
    a, assessor = started_assessment(client, auth)
    h = auth(assessor)
    dev = Device()
    dev.register(client, h)
    data = jpeg_bytes(6)
    r = dev.upload(
        client, h, a, "person", data, packet=dev.packet(a, "person", data, challenge_code="ZZZZZZ")
    )
    assert r.status_code == 201
    assert any(f["code"] == "challenge_mismatch" for f in r.json()["integrity_flags"])


def test_device_id_cannot_be_hijacked(client, auth):
    a, assessor = started_assessment(client, auth)
    dev = Device()
    dev.register(client, auth(assessor))
    other = next(u for u in ("assessor1", "assessor2", "assessor3") if u != assessor)
    r = client.post(
        "/devices",
        json={"device_id": dev.device_id, "public_key_spki": spki_b64(Device().key.public_key())},
        headers=auth(other),
    )
    assert r.status_code == 409


def test_workers_cannot_see_evidence(client, auth):
    a, assessor = started_assessment(client, auth)
    assert client.get(f"/assessments/{a['id']}/evidence", headers=auth("worker1")).status_code == 403


def test_evidence_needs_the_workers_evidence_capture_consent(client, auth):
    a, assessor = started_assessment(client, auth)
    h = auth(assessor)
    dev = Device()
    dev.register(client, h)
    # the worker withdraws photo consent after requesting the assessment
    w = auth("worker1")
    r = client.post("/consents", json={"purposes": ["evidence_capture"], "granted": False}, headers=w)
    assert r.status_code == 201, r.text
    r = dev.upload(client, h, a, "product", jpeg_bytes(seed=77))
    assert r.status_code == 409 and "consent" in r.json()["detail"]
    entries = client.get("/audit/entries?action=evidence.rejected", headers=auth("admin")).json()
    assert entries[0]["payload"]["reason"] == "no_consent"
    # consent given again: the same capture is accepted
    client.post("/consents", json={"purposes": ["evidence_capture"]}, headers=w)
    assert dev.upload(client, h, a, "product", jpeg_bytes(seed=77)).status_code == 201
