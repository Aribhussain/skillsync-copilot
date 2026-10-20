"""Printable competency profile (reportlab) with a QR code to the public verify page."""

from __future__ import annotations

import io
from typing import Any

from reportlab.graphics import renderPDF
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

NAVY = colors.HexColor("#0b1f4d")
SAFFRON = colors.HexColor("#ff9933")
GREEN = colors.HexColor("#138808")


def _qr(url: str, size: float) -> Drawing:
    w = QrCodeWidget(url)
    x0, y0, x1, y1 = w.getBounds()
    d = Drawing(size, size, transform=[size / (x1 - x0), 0, 0, size / (y1 - y0), 0, 0])
    d.add(w)
    return d


def render_profile_pdf(
    profile: dict[str, Any],
    candidate: str,
    decision: str,
    credential_id: str,
    verify_url: str,
    assessor: str,
    signed_off_at: str,
) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    c.setFillColor(NAVY)
    c.rect(0, height - 30 * mm, width, 30 * mm, fill=1, stroke=0)
    c.setFillColor(SAFFRON)
    c.rect(0, height - 32 * mm, width, 2 * mm, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(15 * mm, height - 15 * mm, "NSQF Competency Profile")
    c.setFont("Helvetica", 10)
    c.drawString(15 * mm, height - 22 * mm, "SkillSync Co-Pilot - Recognition of Prior Learning (RPL)")

    y = height - 45 * mm
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(15 * mm, y, candidate)
    c.setFont("Helvetica", 10)
    y -= 6 * mm
    c.drawString(15 * mm, y, f"{profile['qp_title']}  ({profile['qp_id']}, NSQF {profile['nsqf_level']})")
    y -= 6 * mm
    c.drawString(
        15 * mm,
        y,
        f"Assessor decision: {decision.upper()}    System recommendation: "
        f"{profile['recommendation'].upper()}    Aggregate: {profile['aggregate_percent']}%",
    )
    y -= 6 * mm
    c.drawString(15 * mm, y, f"Signed off by {assessor} on {signed_off_at[:16].replace('T', ' ')} UTC")

    renderPDF.draw(_qr(verify_url, 32 * mm), c, width - 47 * mm, height - 80 * mm)
    c.setFont("Helvetica", 7)
    c.drawString(width - 50 * mm, height - 83 * mm, "Scan to verify the signature")

    y -= 14 * mm
    c.setFont("Helvetica-Bold", 10)
    for x, label in ((15, "NOS"), (120, "Theory"), (140, "Practical"), (163, "Viva"), (180, "Result")):
        c.drawString(x * mm, y, label)
    c.setStrokeColor(NAVY)
    c.line(15 * mm, y - 2 * mm, width - 15 * mm, y - 2 * mm)
    c.setFont("Helvetica", 9)
    for n in profile["nos"]:
        y -= 7 * mm
        c.setFillColor(colors.black)
        c.drawString(15 * mm, y, f"{n['nos_id']}  {n['title']}"[:62])
        e, m = n["earned"], n["marks"]
        c.drawString(120 * mm, y, f"{e['theory']:g}/{m['theory']}")
        c.drawString(140 * mm, y, f"{e['practical']:g}/{m['practical']}")
        c.drawString(163 * mm, y, f"{e['viva']:g}/{m['viva']}")
        c.setFillColor(
            GREEN if n["status"] == "competent" else SAFFRON if n["status"] == "partial" else colors.red
        )
        c.drawString(180 * mm, y, f"{n['status']} {n['percent']}%")
    if profile["bridge_modules"]:
        y -= 12 * mm
        c.setFillColor(colors.black)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(15 * mm, y, "Suggested bridge modules")
        c.setFont("Helvetica", 9)
        for b in profile["bridge_modules"]:
            y -= 6 * mm
            c.drawString(18 * mm, y, f"- {b['nos_id']}: {b['title']} ({b['hours']} h)"[:100])

    c.setFillColor(colors.HexColor("#52514e"))
    c.setFont("Helvetica", 7)
    c.drawString(15 * mm, 18 * mm, f"Credential {credential_id}  -  verify: {verify_url}")
    c.drawString(
        15 * mm,
        13 * mm,
        "PROTOTYPE - SYNTHETIC DEMO DATA - NOT AN OFFICIAL CERTIFICATE. "
        "The awarding body certifies; the AI only supported the assessor.",
    )
    c.showPage()
    c.save()
    return buf.getvalue()
