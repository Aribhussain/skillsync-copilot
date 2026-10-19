from app.services.qp_store import iter_pcs, load_corpus

WELDING = "QG-4.5-AU-01811-2024-V1-ASDC"


def test_corpus_has_welding_and_competitors():
    corpus = load_corpus()
    assert WELDING in corpus
    assert len(corpus) >= 10
    welding_like = [q for q in corpus.values() if "weld" in q["title"].lower()]
    assert len(welding_like) >= 4  # real competition for the mapper


def test_welding_qp_matches_nqr_file():
    qp = load_corpus()[WELDING]
    assert qp["nsqf_level"] == 4.5 and qp["source_kind"] == "official"
    assert [n["id"] for n in qp["nos"]] == [
        "ASC/N9819",
        "ASC/N3120",
        "ASC/N3121",
        "ASC/N3122",
        "ASC/N3123",
        "ASC/N3124",
        "ASC/N3125",
    ]
    totals = {c: sum(n["marks"][c] for n in qp["nos"]) for c in ("theory", "practical", "viva")}
    assert totals == {"theory": 135, "practical": 225, "viva": 90}  # 30/50/20 of 450
    assert sum(len(n["pcs"]) for n in qp["nos"]) == 48


def test_pc_ids_unique_and_marks_consistent():
    seen = set()
    for qp in load_corpus().values():
        for pc in iter_pcs(qp):
            assert pc["id"] not in seen
            seen.add(pc["id"])
            assert pc["weight"] == sum(pc["marks"].values())


def test_every_qp_has_safety_or_critical_pcs():
    for qp in load_corpus().values():
        assert any(p["critical"] or p["safety"] for p in iter_pcs(qp)), qp["id"]


def test_qp_endpoints(client):
    listing = client.get("/qps").json()
    assert any(q["id"] == WELDING and q["total_marks"] == 450 for q in listing)
    assert client.get(f"/qps/{WELDING}").json()["title"] == "Welding"
    assert client.get("/qps/nope").status_code == 404
