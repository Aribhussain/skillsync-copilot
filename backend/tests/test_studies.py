import importlib.util
import random
import sys

from app.core.config import REPO_ROOT
from app.services.golden import load_packets


def _create(client, auth, **body):
    r = client.post("/studies", json={"name": "ITI pilot", **body}, headers=auth("qa1"))
    assert r.status_code == 201, r.text
    return r.json()


def _score_arm(client, auth, study, user, arm, noise, rng):
    packets = load_packets()
    h = auth(user)
    while True:
        task = client.get(f"/studies/{study['id']}/task?arm={arm}", headers=h).json()
        if task["packet_id"] is None:
            return
        for pc in task["pcs"]:
            if pc["done"]:
                continue
            truth = packets[task["packet_id"]]["consensus"][pc["pc_id"]]
            level = max(0, min(3, truth + rng.choice(noise)))
            r = client.post(
                f"/studies/{study['id']}/scores",
                json={"packet_id": task["packet_id"], "pc_id": pc["pc_id"], "arm": arm, "score": level},
                headers=h,
            )
            assert r.status_code == 201, r.text
            if arm == "off":
                assert r.json()["ai"] is None  # no AI at all in the OFF arm
            else:
                assert r.json()["ai"]["status"] == "ok"  # revealed after the blind score


def test_live_study_off_then_on_and_alpha(client, auth):
    study = _create(client, auth, packet_ids=["GP-01", "GP-03", "GP-05", "GP-09"])
    rng = random.Random(1)
    # ON is locked until OFF is complete
    assert client.get(f"/studies/{study['id']}/task?arm=on", headers=auth("assessor1")).status_code == 409
    for u in ("assessor1", "assessor2", "assessor3"):
        _score_arm(client, auth, study, u, "off", noise=[-2, -1, 0, 1, 2], rng=rng)  # noisy unassisted
    for u in ("assessor1", "assessor2", "assessor3"):
        _score_arm(client, auth, study, u, "on", noise=[0, 0, 0, 1], rng=rng)  # anchored
    res = client.get(f"/studies/{study['id']}/results", headers=auth("qa1")).json()
    assert res["scores"] == {"off": 4 * 14 * 3, "on": 4 * 14 * 3}
    assert res["alpha_on_blind"] > res["alpha_off"]
    assert res["alpha_on_final"] == res["alpha_on_blind"]  # nobody revised after the reveal


def test_study_permissions_and_validation(client, auth):
    study = _create(client, auth)
    assert len(study["packet_ids"]) == 10 and len(study["pc_ids"]) == 14
    assert client.post("/studies", json={"name": "x" * 5}, headers=auth("assessor1")).status_code == 403
    assert (
        client.post(
            "/studies", json={"name": "bad", "packet_ids": ["GP-99"]}, headers=auth("qa1")
        ).status_code
        == 422
    )
    assert client.get(f"/studies/{study['id']}/results", headers=auth("assessor1")).status_code == 403
    assert client.get("/studies", headers=auth("worker1")).status_code == 403
    img = client.get(f"/studies/{study['id']}/packets/GP-01/image", headers=auth("assessor2"))
    assert img.status_code == 200 and img.headers["content-type"] == "image/jpeg"


def test_simulation_script_runs():
    spec = importlib.util.spec_from_file_location("sim", REPO_ROOT / "scripts" / "simulate_study.py")
    sim = importlib.util.module_from_spec(spec)
    sys.modules["sim"] = sim  # dataclasses need the module registered before exec
    spec.loader.exec_module(sim)
    import numpy as np

    runs = [sim.run_once(sim.Assumptions(), np.random.default_rng(i)) for i in range(5)]
    summary = sim.summarise(runs)
    assert summary["assisted"]["alpha"]["mean"] > summary["unassisted"]["alpha"]["mean"]
    no_help = sim.Assumptions(anchor_bias=1.0, anchor_noise=1.0, adjust_weight=0.0)
    flat = sim.summarise([sim.run_once(no_help, np.random.default_rng(i)) for i in range(5)])
    assert abs(flat["alpha_gain"]["mean"]) < 0.15  # no assistance effect -> no systematic gain
