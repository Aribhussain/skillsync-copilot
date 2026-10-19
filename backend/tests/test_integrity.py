import importlib.util
import io
from datetime import UTC, datetime, timedelta

import cv2
import numpy as np
from PIL import Image, ImageEnhance

from app.core.config import REPO_ROOT
from app.services.integrity import compute_phash, phash_distance
from tests.helpers import Device, jpeg_bytes, started_assessment


def _gen():
    spec = importlib.util.spec_from_file_location("gen", REPO_ROOT / "scripts" / "generate_synthetic.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def weld_jpeg(seed: int, defect="good", severity=0) -> bytes:
    img = _gen().draw_weld(np.random.default_rng(seed), defect, severity)
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 92])
    assert ok
    return buf.tobytes()


def edited(data: bytes) -> bytes:
    """'Slightly edited': brighter, resized to 80% and re-compressed at quality 70."""
    img = Image.open(io.BytesIO(data)).convert("RGB")
    img = ImageEnhance.Brightness(img).enhance(1.1)
    img = img.resize((int(img.width * 0.8), int(img.height * 0.8)))
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=70)
    return out.getvalue()


def _setup(client, auth, worker):
    a, assessor = started_assessment(client, auth, worker=worker)
    h = auth(assessor)
    dev = Device()
    dev.register(client, h)
    return a, h, dev


def _codes(resp):
    return {f["code"] for f in resp.json()["integrity_flags"]}


def test_reused_photo_for_another_candidate_is_flagged(client, auth):
    photo = weld_jpeg(11)
    a1, h1, d1 = _setup(client, auth, "worker1")
    first = d1.upload(client, h1, a1, "product", photo)
    assert "reused_image" not in _codes(first)

    a2, h2, d2 = _setup(client, auth, "worker2")
    second = d2.upload(client, h2, a2, "product", photo)  # exact same file, other candidate
    flag = next(f for f in second.json()["integrity_flags"] if f["code"] == "reused_image")
    assert flag["severity"] == "high"
    assert flag["matches"][0]["assessment_id"] == a1["id"] and flag["matches"][0]["exact"] is True


def test_slightly_edited_reused_photo_is_still_flagged(client, auth):
    photo = weld_jpeg(12)
    tweaked = edited(photo)
    assert phash_distance(compute_phash(photo), compute_phash(tweaked)) <= 6
    a1, h1, d1 = _setup(client, auth, "worker1")
    d1.upload(client, h1, a1, "product", photo)
    a2, h2, d2 = _setup(client, auth, "worker2")
    r = d2.upload(client, h2, a2, "product", tweaked)
    flag = next(f for f in r.json()["integrity_flags"] if f["code"] == "reused_image")
    assert flag["matches"][0]["exact"] is False and flag["matches"][0]["distance"] <= 6


def test_a_genuinely_different_photo_is_not_flagged(client, auth):
    a1, h1, d1 = _setup(client, auth, "worker1")
    d1.upload(client, h1, a1, "product", weld_jpeg(13))
    a2, h2, d2 = _setup(client, auth, "worker2")
    r = d2.upload(client, h2, a2, "product", jpeg_bytes(99))  # unrelated image
    assert "reused_image" not in _codes(r)


def test_same_picture_for_two_shots_in_one_assessment(client, auth):
    a, h, dev = _setup(client, auth, "worker1")
    photo = weld_jpeg(14)
    dev.upload(client, h, a, "process", photo)
    r = dev.upload(client, h, a, "product", photo)
    assert "duplicate_within_assessment" in _codes(r)


def test_timestamp_plausibility(client, auth):
    a, h, dev = _setup(client, auth, "worker1")
    future = (datetime.now(UTC) + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    data = jpeg_bytes(21)
    r = dev.upload(client, h, a, "process", data, packet=dev.packet(a, "process", data, captured_at=future))
    assert "future_timestamp" in _codes(r)

    before = (datetime.now(UTC) - timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    data2 = jpeg_bytes(22)
    r2 = dev.upload(
        client, h, a, "product", data2, packet=dev.packet(a, "product", data2, captured_at=before)
    )
    assert "captured_before_start" in _codes(r2)


def test_gps_checks_and_ocr_note(client, auth):
    a, h, dev = _setup(client, auth, "worker1")
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    d1, d2, d3 = jpeg_bytes(31), jpeg_bytes(32), jpeg_bytes(33)
    dev.upload(client, h, a, "process", d1, packet=dev.packet(a, "process", d1, captured_at=now))
    far = dev.packet(a, "product", d2, captured_at=now, gps={"lat": 19.076, "lon": 72.8777, "accuracy": 10})
    assert "gps_inconsistent" in _codes(dev.upload(client, h, a, "product", d2, packet=far))
    person = dev.upload(
        client, h, a, "person", d3, packet=dev.packet(a, "person", d3, captured_at=now, gps=None)
    )
    codes = _codes(person)
    assert "no_gps" in codes
    assert codes & {"ocr_skipped", "ocr_code_ok", "ocr_code_not_found"}  # pytesseract optional


def test_flags_are_visible_to_qa_for_review(client, auth):
    a, h, dev = _setup(client, auth, "worker1")
    dev.upload(client, h, a, "product", weld_jpeg(41))
    listing = client.get(f"/assessments/{a['id']}/evidence", headers=auth("qa1")).json()
    assert listing and "integrity_flags" in listing[0] and listing[0]["phash"]


def test_bundled_demo_samples_do_not_trigger_false_reuse_flags():
    """The 12 product samples shipped for demos must be pairwise above the reuse threshold."""
    from app.core.config import Settings

    threshold = Settings(_env_file=None).phash_hamming_threshold
    files = sorted((REPO_ROOT / "frontend" / "public" / "samples").glob("*.jpg"))
    hashes = [compute_phash(f.read_bytes()) for f in files]
    assert len(hashes) == 12
    closest = min(phash_distance(a, b) for i, a in enumerate(hashes) for b in hashes[i + 1 :])
    assert closest > threshold
