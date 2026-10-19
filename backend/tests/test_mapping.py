import numpy as np
import pytest

from app.services.lexicon import all_entries
from app.services.mapping import LexiconMatcher, QPMapper, detect_language, softmax
from app.services.qp_store import load_corpus
from app.services.text_norm import tokenize
from app.services.vector_index import NumpyVectorIndex

WELDING = "QG-4.5-AU-01811-2024-V1-ASDC"
GOLDEN = (
    "Main 6 saal se fabrication shop mein kaam karta hoon, CO2 aur argon dono welding karta hoon, "
    "plate aur pipe joint banata hoon, grinding karke finishing deta hoon"
)


@pytest.fixture(scope="module")
def mapper():
    return QPMapper(load_corpus(), all_entries())


def test_tokenizer_keeps_devanagari_and_drops_stopwords():
    assert tokenize("वेल्डिंग के बाद ग्राइंडर से घिसाई करता हूँ।") == ["वेल्डिंग", "ग्राइंडर", "घिसाई"]
    assert tokenize("I make joints on pipes and plates") == ["make", "joint", "pipe", "plate"]
    assert "glass" in tokenize("glass")  # 'ss' endings are not stemmed


def test_language_detection():
    assert detect_language("मैं वेल्डिंग करता हूँ") == "hi"
    assert detect_language("main welding karta hoon aur grinding bhi") == "hinglish"
    assert detect_language("I do TIG welding on stainless steel") == "en"


def test_lexicon_longest_match_first():
    m = LexiconMatcher(all_entries())
    found = m.match("co2 welding aur argon ka kaam")
    canon = [x["canonical"] for x in found]
    assert canon == ["GMAW (135)", "GTAW (141)"]  # 'welding' inside 'co2 welding' is consumed


def test_golden_path_narrative_maps_to_welding(mapper):
    r = mapper.map(GOLDEN)
    assert r["top"][0]["qp_id"] == WELDING
    assert len(r["top"]) == 3
    assert r["top"][0]["confidence"] > r["top"][1]["confidence"]
    assert sum(t["confidence"] for t in r["top"]) <= 1.0 + 1e-9
    terms = {m["term"].lower() for m in r["lexicon_matches"]}
    assert {"co2", "argon", "grinding"} <= terms
    assert r["language_detected"] == "hinglish"


def test_claims_follow_what_the_worker_said(mapper):
    claims = {c["pc_id"]: c for c in mapper.map(GOLDEN)["claims"][WELDING]}
    nos_claimed = {c["nos_id"] for c in claims.values() if c["claimed"]}
    assert {"ASC/N3122", "ASC/N3124", "ASC/N3125"} <= nos_claimed  # CO2, argon, grinding
    assert "ASC/N3123" not in nos_claimed  # never mentioned flux-cored
    assert "ASC/N9819" not in nos_claimed  # never mentioned safety/organisation
    assert claims["ASC-N3125.PC4"]["strength"] == "strong"  # 'dress welds' via grinding
    assert all(c["matched_terms"] for c in claims.values() if c["claimed"])  # explainable


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("मैं घर की वायरिंग और MCB बोर्ड लगाता हूँ", "DEMO-EL-DOMESTIC-L3"),
        ("silai ka kaam karti hoon, overlock machine chalati hoon", "DEMO-AMH-SMO-L4"),
        ("stud gun se deck sheet pe stud lagata hoon", "DEMO-AU-STUD-WELD-L3"),
        ("6G pipe welding, x-ray test pass hota hai, boiler ka kaam", "DEMO-CG-SR-WELDER-PIPE-L5"),
    ],
)
def test_other_trades_and_welding_variants(mapper, text, expected):
    assert mapper.map(text)["top"][0]["qp_id"] == expected


def test_softmax_is_a_distribution():
    p = softmax([1.0, 0.5, 0.2], 0.12)
    assert abs(sum(p) - 1) < 1e-9 and p[0] > p[1] > p[2]


def test_numpy_vector_index_cosine():
    idx = NumpyVectorIndex()
    idx.add("a", [1, 0, 0])
    idx.add("b", [0, 1, 0])
    idx.add("c", [1, 1, 0])
    top = idx.search(np.array([1.0, 0.1, 0.0]), k=2)
    assert [r for r, _ in top] == ["a", "c"]


class FakeEmbedder:
    """Deterministic stand-in for the sentence-transformer (keeps CI light)."""

    ready = True

    def encode(self, texts):
        out = []
        for t in texts:
            v = np.zeros(16, np.float32)
            for tok in tokenize(t):
                v[hash(tok) % 16] += 1
            out.append(v)
        return np.vstack(out)


def test_hybrid_path_uses_cosine_rerank():
    m = QPMapper(load_corpus(), all_entries())
    fake = FakeEmbedder()
    vecs = {q: fake.encode([q + " " + m.corpus[q]["title"]])[0].tolist() for q in m.qp_ids}
    m.attach_embeddings(fake, vecs)
    r = m.map(GOLDEN)
    assert r["engine"] == "hybrid"
    assert r["top"][0]["cosine"] is not None


# ---------------------------------------------------------------- API


def _consent(client, h):
    client.post("/consents", json={"purposes": ["rpl_assessment"], "language": "hi"}, headers=h)


def test_declaration_requires_consent(client, auth):
    r = client.post("/declarations", json={"narrative": GOLDEN}, headers=auth("worker1"))
    assert r.status_code == 403


def test_declare_and_map_end_to_end(client, auth):
    h = auth("worker1")
    _consent(client, h)
    r = client.post(
        "/declarations",
        json={"narrative": GOLDEN, "input_mode": "voice", "client_id": "dev-abc-1"},
        headers=h,
    )
    assert r.status_code == 201
    decl = r.json()
    assert decl["language"] == "hinglish"
    # idempotent retry from the outbox returns the same row
    again = client.post("/declarations", json={"narrative": GOLDEN, "client_id": "dev-abc-1"}, headers=h)
    assert again.json()["id"] == decl["id"]

    m = client.post(f"/declarations/{decl['id']}/map", headers=h).json()
    assert m["top"][0]["qp_id"] == WELDING
    assert m["engine"] == "bm25+lexicon"  # embeddings are disabled in tests
    assert "BM25" in m["embedding_note"]
    assert WELDING in m["claims"]
    stored = client.get(f"/declarations/{decl['id']}", headers=h).json()
    assert stored["status"] == "mapped" and stored["mapping"]["top"][0]["qp_id"] == WELDING


def test_worker_cannot_read_someone_elses_declaration(client, auth):
    h1 = auth("worker1")
    _consent(client, h1)
    d = client.post("/declarations", json={"narrative": GOLDEN}, headers=h1).json()
    assert client.get(f"/declarations/{d['id']}", headers=auth("worker2")).status_code == 403
    assert client.get(f"/declarations/{d['id']}", headers=auth("assessor1")).status_code == 200


def test_pack_is_versioned_and_complete(client, auth):
    p1 = client.get("/packs/latest").json()
    assert {d["qp_id"] for d in p1["bm25"]["docs"]} == {q["id"] for q in p1["qps"]}
    assert len(p1["lexicon"]) >= 150 and p1["lexicon"][0]["tokens"]
    assert client.get("/packs/latest").json()["pack_version"] == p1["pack_version"]
    client.post(
        "/lexicon",
        json={"term": "argon jodai", "canonical": "GTAW (141)", "expand": ["gtaw"]},
        headers=auth("assessor1"),
    )
    assert client.get("/packs/version").json()["pack_version"] != p1["pack_version"]
