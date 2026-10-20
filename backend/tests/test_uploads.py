import hashlib
import json
import math

from app.services.signing import sign_packet_for_tests
from app.services.uploads import CHUNK_SIZE
from tests.helpers import Device, jpeg_bytes, started_assessment


def _big_image() -> bytes:
    data = jpeg_bytes(7, size=(1600, 1200))
    assert len(data) > CHUNK_SIZE  # forces several chunks
    return data


def test_resumable_chunked_upload_completes_a_signed_packet(client, auth):
    a, assessor = started_assessment(client, auth)
    h = auth(assessor)
    dev = Device()
    dev.register(client, h)
    data = _big_image()
    sha = hashlib.sha256(data).hexdigest()
    n = math.ceil(len(data) / CHUNK_SIZE)

    st = client.post("/uploads", json={"sha256": sha, "size": len(data), "total_chunks": n}, headers=h).json()
    uid = st["upload_id"]
    # send all chunks except the last one, as if the connection dropped
    for i in range(n - 1):
        client.put(
            f"/uploads/{uid}/chunks/{i}", content=data[i * CHUNK_SIZE : (i + 1) * CHUNK_SIZE], headers=h
        )
    packet = dev.packet(a, "product", data)
    sig = sign_packet_for_tests(dev.key, packet)
    early = client.post(
        f"/assessments/{a['id']}/evidence",
        data={"packet": json.dumps(packet), "signature": sig, "upload_id": uid},
        headers=h,
    )
    assert early.status_code == 409 and "missing" in early.json()["detail"]

    # resume: init again returns the same upload and what the server already has
    again = client.post(
        "/uploads", json={"sha256": sha, "size": len(data), "total_chunks": n}, headers=h
    ).json()
    assert again["upload_id"] == uid and again["received"] == list(range(n - 1))
    client.put(f"/uploads/{uid}/chunks/{n - 1}", content=data[(n - 1) * CHUNK_SIZE :], headers=h)
    client.put(
        f"/uploads/{uid}/chunks/0", content=data[:CHUNK_SIZE], headers=h
    )  # duplicate chunk is harmless
    r = client.post(
        f"/assessments/{a['id']}/evidence",
        data={"packet": json.dumps(packet), "signature": sig, "upload_id": uid},
        headers=h,
    )
    assert r.status_code == 201, r.text
    assert r.json()["signature_valid"] is True and r.json()["size_bytes"] == len(data)
    assert client.get(r.json()["image_url"], headers=h).content == data


def test_corrupted_chunks_are_rejected(client, auth):
    a, assessor = started_assessment(client, auth)
    h = auth(assessor)
    data = _big_image()
    sha = hashlib.sha256(data).hexdigest()
    n = math.ceil(len(data) / CHUNK_SIZE)
    uid = client.post(
        "/uploads", json={"sha256": sha, "size": len(data), "total_chunks": n}, headers=h
    ).json()["upload_id"]
    for i in range(n):
        chunk = bytearray(data[i * CHUNK_SIZE : (i + 1) * CHUNK_SIZE])
        if i == 1:
            chunk[10] ^= 0xFF  # flip a byte in transit
        client.put(f"/uploads/{uid}/chunks/{i}", content=bytes(chunk), headers=h)
    dev = Device()
    dev.register(client, h)
    packet = dev.packet(a, "product", data)
    r = client.post(
        f"/assessments/{a['id']}/evidence",
        data={
            "packet": json.dumps(packet),
            "signature": sign_packet_for_tests(dev.key, packet),
            "upload_id": uid,
        },
        headers=h,
    )
    assert r.status_code == 400 and "SHA-256" in r.json()["detail"]


def test_uploads_are_private_and_bounded(client, auth):
    sha = "a" * 64
    uid = client.post(
        "/uploads", json={"sha256": sha, "size": 10, "total_chunks": 1}, headers=auth("assessor1")
    ).json()["upload_id"]
    assert client.get(f"/uploads/{uid}", headers=auth("assessor2")).status_code == 403
    assert client.put(f"/uploads/{uid}/chunks/5", content=b"x", headers=auth("assessor1")).status_code == 422
    too_big = {"sha256": sha, "size": 10**9, "total_chunks": 4000}
    assert client.post("/uploads", json=too_big, headers=auth("assessor1")).status_code == 413
    assert (
        client.post(
            "/uploads", json={"sha256": sha, "size": 1, "total_chunks": 1}, headers=auth("worker1")
        ).status_code
        == 403
    )


def test_retry_after_corruption_starts_clean(client, auth):
    """Regression: a corrupt reassembly must not leave chunks that make every retry fail."""
    _, assessor = started_assessment(client, auth)
    h = auth(assessor)
    data = b"x" * 10
    sha = hashlib.sha256(data).hexdigest()
    uid = client.post("/uploads", json={"sha256": sha, "size": 10, "total_chunks": 1}, headers=h).json()[
        "upload_id"
    ]
    client.put(f"/uploads/{uid}/chunks/0", content=b"y" * 10, headers=h)  # corrupt
    from app.services.uploads import UploadStore

    store = UploadStore(client.app.state.settings.storage_path / "uploads")
    user_id = client.get("/auth/me", headers=h).json()["id"]
    try:
        store.assemble(uid, user_id)
    except Exception as exc:  # HTTPException 400
        assert getattr(exc, "status_code", None) == 400
    fresh = client.post("/uploads", json={"sha256": sha, "size": 10, "total_chunks": 1}, headers=h).json()
    assert fresh["received"] == []
