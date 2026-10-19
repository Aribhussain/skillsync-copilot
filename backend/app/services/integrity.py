"""Evidence integrity checks. Every result is a FLAG for the assessor to review; nothing is
auto-rejected (the AI flags anomalies, the assessor decides).

Checks:
  - reused_image: exact copy (same SHA-256) or perceptual near-duplicate (pHash Hamming
    distance <= threshold) of evidence from ANOTHER assessment. This is the pattern the CAG
    PMKVY audit found: the same photos reused across candidates and states.
  - duplicate_within_assessment: the same picture used for two different shots.
  - captured_before_start / future_timestamp / stale_capture: timestamp plausibility.
  - exif_time_mismatch: camera EXIF time far from the signed capture time.
  - no_gps / gps_inconsistent: location plausibility within an assessment.
  - ocr_skipped: the challenge code on the slate is not OCR-checked (pytesseract absent).

Measured on our synthetic weld images (scripts in docs/DECISIONS.md): brightness, contrast,
JPEG re-compression and resizing move pHash by <= 4 bits, so the default threshold of 6
catches them. Crops >= 2% and rotations of a few degrees are NOT caught by pHash. Because
the synthetic welds share one template, about 1% of *different* synthetic images also fall
within 6 bits; real field photos are far more varied.
"""

from __future__ import annotations

import io
import math
from datetime import UTC, datetime, timedelta
from typing import Any

import imagehash
from PIL import ExifTags, Image
from sqlmodel import Session, select

from app.models.assessment import Assessment
from app.models.evidence import Evidence

EXIF_DATETIME_TAGS = (36867, 306)  # DateTimeOriginal, DateTime
FUTURE_TOLERANCE = timedelta(minutes=10)
STALE_AFTER = timedelta(days=7)
EXIF_MISMATCH = timedelta(hours=24)
GPS_INCONSISTENT_KM = 1.0


def compute_phash(data: bytes) -> str:
    with Image.open(io.BytesIO(data)) as img:
        return str(imagehash.phash(img.convert("RGB")))


def phash_distance(a: str, b: str) -> int:
    return int(imagehash.hex_to_hash(a) - imagehash.hex_to_hash(b))  # numpy int64 -> int (JSON)


def read_exif(data: bytes) -> dict[str, Any]:
    try:
        with Image.open(io.BytesIO(data)) as img:
            exif = img.getexif()
    except Exception:
        return {}
    out: dict[str, Any] = {}
    for tag in (271, 272, *EXIF_DATETIME_TAGS):  # Make, Model, DateTimeOriginal, DateTime
        if tag in exif:
            out[ExifTags.TAGS.get(tag, str(tag))] = str(exif[tag])
    if 34853 in exif:
        out["has_gps_ifd"] = True
    return out


def _parse_iso(ts: str) -> datetime | None:
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
    except ValueError:
        return None


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _flag(code: str, severity: str, detail: str, **extra: Any) -> dict[str, Any]:
    return {"code": code, "severity": severity, "detail": detail, **extra}


def check_evidence(
    session: Session,
    ev: Evidence,
    data: bytes,
    assessment: Assessment,
    threshold: int,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Compute pHash + EXIF on `ev` and return integrity flags (does not commit)."""
    now = now or datetime.now(UTC)
    flags: list[dict[str, Any]] = []
    ev.phash = compute_phash(data)
    ev.exif = read_exif(data)

    # --- reuse across assessments (exact or perceptual) and within this assessment
    others = session.exec(select(Evidence).where(Evidence.id != ev.id, Evidence.phash.is_not(None))).all()
    matches = []
    for o in others:
        exact = o.sha256 == ev.sha256
        dist = 0 if exact else phash_distance(ev.phash, o.phash)
        if dist > threshold:
            continue
        if o.assessment_id == ev.assessment_id:
            if o.shot != ev.shot:
                flags.append(
                    _flag(
                        "duplicate_within_assessment",
                        "medium",
                        f"Same picture also used as the {o.shot} shot",
                        evidence_id=o.id,
                    )
                )
            continue
        matches.append(
            {
                "evidence_id": o.id,
                "assessment_id": o.assessment_id,
                "shot": o.shot,
                "distance": dist,
                "exact": exact,
            }
        )
    if matches:
        matches.sort(key=lambda m: m["distance"])
        best = matches[0]
        kind = "an exact copy" if best["exact"] else f"a near-duplicate (pHash distance {best['distance']})"
        flags.append(
            _flag(
                "reused_image",
                "high",
                f"This photo is {kind} of evidence in assessment #{best['assessment_id']}",
                matches=matches[:5],
            )
        )

    # --- timestamps
    captured = _parse_iso(ev.captured_at)
    if captured is None:
        flags.append(
            _flag("timestamp_unparseable", "medium", f"Capture time '{ev.captured_at}' is not ISO 8601")
        )
    else:
        if captured > now + FUTURE_TOLERANCE:
            flags.append(_flag("future_timestamp", "high", "Capture time is in the future (device clock?)"))
        elif now - captured > STALE_AFTER:
            flags.append(_flag("stale_capture", "medium", "Captured more than 7 days before upload"))
        started = assessment.started_at
        if started is not None:
            started = started if started.tzinfo else started.replace(tzinfo=UTC)
            if captured < started - FUTURE_TOLERANCE:
                flags.append(
                    _flag(
                        "captured_before_start",
                        "high",
                        "Captured before the assessment (and its challenge code) existed",
                    )
                )
        exif_time = next((ev.exif.get(k) for k in ("DateTimeOriginal", "DateTime") if ev.exif.get(k)), None)
        if exif_time:
            try:
                et = datetime.strptime(exif_time, "%Y:%m:%d %H:%M:%S").replace(tzinfo=UTC)
                if abs(et - captured) > EXIF_MISMATCH:
                    flags.append(
                        _flag(
                            "exif_time_mismatch", "medium", f"Camera EXIF time {exif_time} differs by >24 h"
                        )
                    )
            except ValueError:
                pass

    # --- location
    if ev.gps_lat is None or ev.gps_lon is None:
        flags.append(_flag("no_gps", "info", "No GPS fix (permission denied or indoors)"))
    else:
        same = session.exec(
            select(Evidence).where(
                Evidence.assessment_id == ev.assessment_id,
                Evidence.id != ev.id,
                Evidence.gps_lat.is_not(None),
            )
        ).all()
        far = [
            o
            for o in same
            if _haversine_km(ev.gps_lat, ev.gps_lon, o.gps_lat, o.gps_lon) > GPS_INCONSISTENT_KM
        ]
        if far:
            flags.append(
                _flag(
                    "gps_inconsistent",
                    "medium",
                    f"More than {GPS_INCONSISTENT_KM:g} km from other shots of this assessment",
                )
            )

    # --- challenge code OCR (optional)
    if ev.shot == "person":
        flags.append(ocr_challenge_flag(data, ev.challenge_code))
    return flags


def ocr_challenge_flag(data: bytes, code: str) -> dict[str, Any]:
    try:
        import pytesseract  # optional, Apache-2.0; needs the Tesseract binary installed
    except ImportError:
        return _flag(
            "ocr_skipped",
            "info",
            "Challenge code not OCR-checked (pytesseract not installed): assessor confirms visually",
        )
    try:
        with Image.open(io.BytesIO(data)) as img:
            text = pytesseract.image_to_string(img.convert("L"), config="--psm 6")
    except Exception as exc:  # binary missing, etc.
        return _flag("ocr_skipped", "info", f"OCR unavailable: {type(exc).__name__}")
    found = code in text.replace(" ", "").upper()
    if found:
        return _flag("ocr_code_ok", "info", "Challenge code read from the slate")
    return _flag("ocr_code_not_found", "medium", "Challenge code could not be read on the slate")
