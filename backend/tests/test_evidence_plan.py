from app.services.evidence_plan import build_plan, plan_summary, route_for
from app.services.qp_store import iter_pcs, load_corpus

WELDING = "QG-4.5-AU-01811-2024-V1-ASDC"


def _request(client, auth, claimed=()):
    h = auth("worker1")
    client.post("/consents", json={"purposes": ["rpl_assessment"]}, headers=h)
    d = client.post("/declarations", json={"narrative": "argon ka kaam aur grinding"}, headers=h).json()
    return client.post(
        "/assessments",
        json={"qp_id": WELDING, "declaration_id": d["id"], "claimed_pc_ids": list(claimed)},
        headers=h,
    ).json()


def test_critical_and_safety_pcs_are_always_observe_and_locked():
    for qp in load_corpus().values():
        for claimed in (False, True):
            for pc in iter_pcs(qp):
                r = route_for(pc, claimed)
                if pc["critical"] or pc["safety"]:
                    assert r["route"] == "observe" and r["locked"] is True, pc["id"]
                else:
                    assert r["locked"] is False


def test_declaration_pcs_depend_on_the_claim():
    pc = {"critical": False, "safety": False, "evidence_hint": "declaration"}
    assert route_for(pc, True)["route"] == "declaration+spot-check"
    assert route_for(pc, False)["route"] == "viva"


def test_welding_plan_summary():
    qp = load_corpus()[WELDING]
    summary = plan_summary(build_plan(qp, []))
    assert summary["locked"] == sum(1 for p in iter_pcs(qp) if p["critical"] or p["safety"])
    assert summary["photo"] > 0 and summary["viva"] > 0
    assert sum(summary[r] for r in ("observe", "photo", "viva", "declaration+spot-check")) == 48


def test_plan_endpoint_and_locked_override_refused(client, auth):
    a = _request(client, auth, claimed=["ASC-N9819.PC8"])
    assessor = client.get("/users?role=assessor", headers=auth("admin")).json()
    username = next(u["username"] for u in assessor if u["id"] == a["assessor_id"])
    h = auth(username)

    body = client.get(f"/assessments/{a['id']}/plan", headers=h).json()
    pcs = {p["pc_id"]: p for n in body["plan"] for p in n["pcs"]}
    assert pcs["ASC-N9819.PC1"]["locked"] is True  # safety
    assert pcs["ASC-N3124.PC3"]["locked"] is True  # critical
    assert pcs["ASC-N9819.PC8"]["route"] == "declaration+spot-check"  # claimed declaration PC
    assert pcs["ASC-N9819.PC11"]["route"] == "viva"  # unclaimed declaration PC
    assert len(body["rubric"]["scale"]) == 4

    refused = client.patch(
        f"/assessments/{a['id']}/plan",
        json={"pc_id": "ASC-N3124.PC3", "route": "photo", "reason": "faster"},
        headers=h,
    )
    assert refused.status_code == 409

    ok = client.patch(
        f"/assessments/{a['id']}/plan",
        json={"pc_id": "ASC-N3124.PC1", "route": "observe", "reason": "photo unreliable here"},
        headers=h,
    )
    assert ok.status_code == 200
    pcs = {
        p["pc_id"]: p
        for n in client.get(f"/assessments/{a['id']}/plan", headers=h).json()["plan"]
        for p in n["pcs"]
    }
    assert pcs["ASC-N3124.PC1"]["route"] == "observe" and pcs["ASC-N3124.PC1"]["rule"] == "override"


def test_queue_start_and_challenge_code(client, auth):
    a = _request(client, auth)
    assessors = client.get("/users?role=assessor", headers=auth("admin")).json()
    username = next(u["username"] for u in assessors if u["id"] == a["assessor_id"])
    h = auth(username)
    queue = client.get("/assessor/queue", headers=h).json()
    assert any(q["id"] == a["id"] and q["candidate"] == "Ramesh Kumar" for q in queue)
    assert all("is_golden" not in q for q in queue)  # golden packets are indistinguishable

    started = client.post(f"/assessments/{a['id']}/start", headers=h).json()
    code = started["challenge_code"]
    assert started["status"] == "in_progress" and len(code) == 6
    assert not set(code) & set("0O1IL2Z5S8B")
    again = client.post(f"/assessments/{a['id']}/start", headers=h).json()
    assert again["challenge_code"] == code  # issued once

    other = next(u["username"] for u in assessors if u["id"] != a["assessor_id"])
    assert client.get(f"/assessments/{a['id']}/plan", headers=auth(other)).status_code == 403
    assert client.post(f"/assessments/{a['id']}/start", headers=auth("worker1")).status_code == 403
