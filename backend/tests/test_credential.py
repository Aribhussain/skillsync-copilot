import copy

from app.services.credential import verify_vc
from app.services.qp_store import iter_pcs, load_corpus
from tests.helpers import WELDING, started_assessment

PCS = [p for p in iter_pcs(load_corpus()[WELDING])]


def _score_all(client, h, aid, gtaw_level=2, other=2):
    for pc in PCS:
        level = gtaw_level if pc["nos_id"] == "ASC/N3124" else other
        client.post(f"/assessments/{aid}/scores", json={"pc_id": pc["id"], "score": level}, headers=h)


def _ready(client, auth, gtaw_level=0):
    a, assessor = started_assessment(client, auth)
    h = auth(assessor)
    _score_all(client, h, a["id"], gtaw_level=gtaw_level)
    return a, assessor, h


def _signoff(client, h, aid, **over):
    body = {"password": "assessor123", "decision": "partial", "confirm": True, **over}
    return client.post(f"/assessments/{aid}/signoff", json=body, headers=h)


def test_scoring_everything_never_signs_off_by_itself(client, auth):
    a, _, h = _ready(client, auth)
    assert client.get(f"/assessments/{a['id']}", headers=h).json()["status"] == "scored"
    client.get(f"/assessments/{a['id']}/profile", headers=h)
    assert client.get(f"/assessments/{a['id']}", headers=h).json()["status"] == "scored"  # still not signed


def test_signoff_requirements(client, auth):
    a, assessor, h = _ready(client, auth)
    assert _signoff(client, h, a["id"], password="wrong").status_code == 401
    assert _signoff(client, h, a["id"], confirm=False).status_code == 422
    # the recommendation is partial (GTAW gap); 'full' needs a justification
    assert _signoff(client, h, a["id"], decision="full").status_code == 422
    other = next(u for u in ("assessor1", "assessor2", "assessor3") if u != assessor)
    assert _signoff(client, auth(other), a["id"]).status_code == 403
    assert _signoff(client, auth("qa1"), a["id"]).status_code == 403


def test_signoff_blocked_by_unscored_pcs_and_missing_reasons(client, auth):
    a, assessor = started_assessment(client, auth)
    h = auth(assessor)
    client.post(f"/assessments/{a['id']}/scores", json={"pc_id": PCS[0]["id"], "score": 2}, headers=h)
    r = _signoff(client, h, a["id"])
    assert r.status_code == 409 and "not scored" in r.json()["detail"]


def test_signoff_issues_a_verifiable_credential(client, auth):
    a, _, h = _ready(client, auth)
    r = _signoff(client, h, a["id"])
    assert r.status_code == 201, r.text
    cred_id = r.json()["credential_id"]
    assert r.json()["verify_url"].endswith(f"/verify/{cred_id}")
    assert _signoff(client, h, a["id"]).status_code == 409  # only once

    vc = client.get(f"/credentials/{cred_id}").json()  # public
    assert vc["@context"] == ["https://www.w3.org/ns/credentials/v2"]
    assert vc["issuer"]["id"].startswith("did:key:z6Mk")
    assert vc["proof"]["cryptosuite"] == "eddsa-jcs-2022"
    assert vc["credentialSubject"]["achievement"]["result"] == "partial"
    assert "ASC/N3124" not in vc["credentialSubject"]["achievement"]["competentNOS"]

    v = client.get(f"/credentials/{cred_id}/verify").json()  # public
    assert v["valid"] is True and v["signature_valid"] and v["issuer_trusted"]
    forged = copy.deepcopy(vc)
    forged["credentialSubject"]["achievement"]["result"] = "full"
    assert verify_vc(forged, vc["issuer"]["id"])["signature_valid"] is False

    pdf = client.get(f"/credentials/{cred_id}/pdf", headers=h)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF") and len(pdf.content) > 2000
    assert client.get(f"/credentials/{cred_id}/pdf").status_code == 401

    # the worker now sees the profile and their credential
    assert client.get(f"/assessments/{a['id']}/profile", headers=auth("worker1")).status_code == 200
    mine = client.get("/credentials/mine/list", headers=auth("worker1")).json()
    assert [c["credential_id"] for c in mine] == [cred_id]

    sidh = client.get(f"/export/sidh/{a['id']}", headers=auth("qa1")).json()
    assert (
        sidh["mock"] is True
        and sidh["result"]["decision"] == "partial"
        and sidh["credential"]["id"] == cred_id
    )

    ledger = client.get("/audit/entries?action=credential.issued", headers=auth("qa1")).json()
    assert ledger and ledger[0]["payload"]["credential_id"] == cred_id
    assert client.get("/audit/verify", headers=auth("qa1")).json()["valid"] is True


def test_gap_decision_records_the_assessment_without_a_credential(client, auth):
    a, assessor = started_assessment(client, auth)
    h = auth(assessor)
    _score_all(client, h, a["id"], gtaw_level=0, other=0)
    r = _signoff(client, h, a["id"], decision="gap")
    assert r.status_code == 201 and r.json()["credential_id"] is None
    assert client.get(f"/assessments/{a['id']}", headers=h).json()["status"] == "signed_off"
    # scores are locked after sign-off
    pc = PCS[0]["id"]
    assert (
        client.patch(f"/assessments/{a['id']}/scores/{pc}", json={"final_score": 3}, headers=h).status_code
        == 409
    )


def test_unknown_credential(client):
    assert client.get("/credentials/nope/verify").status_code == 404
