from app.services.lexicon import load_seed_lexicon


def test_seed_lexicon_size_and_languages():
    entries = load_seed_lexicon()["entries"]
    assert len(entries) >= 150
    langs = {e["lang"] for e in entries}
    assert {"hi", "hinglish", "en"} <= langs
    cats = {e["category"] for e in entries}
    assert {"process", "tool", "defect", "safety"} <= cats


def test_key_vernacular_mappings():
    by_term = {e["term"]: e for e in load_seed_lexicon()["entries"]}
    assert by_term["argon ka kaam"]["canonical"] == "GTAW (141)"
    assert by_term["co2 welding"]["canonical"] == "GMAW (135)"
    assert by_term["electrode"]["canonical"] == "SMAW (111)"
    assert by_term["stick"]["canonical"] == "SMAW (111)"
    assert by_term["आर्गन"]["lang"] == "hi"


def test_assessor_can_add_term_and_it_is_served(client, auth):
    body = {"term": "argon wala jod", "canonical": "GTAW (141)", "expand": ["gtaw", "tig"]}
    assert client.post("/lexicon", json=body, headers=auth("worker1")).status_code == 403
    r = client.post("/lexicon", json=body, headers=auth("assessor1"))
    assert r.status_code == 201 and r.json()["lang"] == "hinglish"
    lex = client.get("/lexicon").json()
    added = [e for e in lex["entries"] if e["term"] == "argon wala jod"]
    assert added and added[0]["source"] == "assessor"
    assert lex["version"].endswith("+1")
    assert client.post("/lexicon", json=body, headers=auth("assessor2")).status_code == 409


def test_every_expansion_term_exists_in_qp_corpus():
    """Expansion terms must point at real QP vocabulary, otherwise they add nothing."""
    import json

    from app.services.qp_store import load_corpus

    text = json.dumps(list(load_corpus().values()), ensure_ascii=False).lower()
    missing = {x for e in load_seed_lexicon()["entries"] for x in e["expand"] if x.lower() not in text}
    assert not missing, missing
