"""M2 — NSQF QP mapping engine.

Hybrid retrieval:
  1. normalise the narrative (text_norm) and expand it with the trade-vernacular lexicon;
  2. BM25 (rank_bm25.BM25Okapi) over one field-weighted document per QP;
  3. optional cosine re-rank with a multilingual sentence-embedding model;
  4. softmax over the top-k combined scores gives the displayed confidence;
  5. per-PC claim prefill from lexical overlap (explainable: every claim lists the
     terms that triggered it).

The BM25 statistics, lexicon and tokenizer rules are exported in the device pack so
the TypeScript mapper-lite reproduces the BM25 + lexicon part offline.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from rank_bm25 import BM25Okapi

from app.services.qp_store import iter_pcs
from app.services.text_norm import DEVANAGARI_RANGE, STOPWORDS_HINGLISH, phrase_tokens, raw_tokens, tokenize
from app.services.vector_index import NumpyVectorIndex

BM25_K1 = 1.5
BM25_B = 0.5
# Field weights: how many times each field's tokens are repeated in the QP document.
FIELD_WEIGHTS = {"title": 3, "keywords": 2, "nos_title": 2, "nos_keywords": 1, "description": 1, "pc_text": 1}
HYBRID_BM25_WEIGHT = 0.6
TOP_K_SOFTMAX = 5
# Temperature for the confidence softmax. Fitted with ml/eval_mapping.py --calibrate on a
# calibration split generated with a different seed from the evaluation split.
SOFTMAX_TEMPERATURE = 0.12
GENERIC_PC_DF = 0.2  # tokens in more than 20% of a QP's PCs are too generic to justify a claim
# Words that appear across the whole welding family and say nothing about a specific NOS.
DOMAIN_GENERIC = {
    "weld",
    "welded",
    "welding",
    "welder",
    "work",
    "wire",
    "fit",
    "shop",
    "joint",
    "material",
    "steel",
    "carbon",
    "plate",
    "pipe",
    "sheet",
}


def detect_language(text: str) -> str:
    chars = [c for c in text if not c.isspace()]
    if not chars:
        return "en"
    dev = sum(1 for c in chars if DEVANAGARI_RANGE[0] <= ord(c) <= DEVANAGARI_RANGE[1])
    if dev / len(chars) > 0.3:
        return "hi"
    hinglish_hits = sum(1 for t in raw_tokens(text) if t in STOPWORDS_HINGLISH)
    return "hinglish" if hinglish_hits >= 2 else "en"


def qp_document(qp: dict[str, Any]) -> list[str]:
    w = FIELD_WEIGHTS
    toks: list[str] = []
    toks += tokenize(qp["title"]) * w["title"]
    toks += tokenize(" ".join(qp.get("keywords", []))) * w["keywords"]
    toks += tokenize(qp.get("description", "")) * w["description"]
    for nos in qp["nos"]:
        toks += tokenize(nos["title"]) * w["nos_title"]
        toks += tokenize(" ".join(nos.get("keywords", []))) * w["nos_keywords"]
        for pc in nos["pcs"]:
            toks += tokenize(pc["text"]) * w["pc_text"]
    return toks


def qp_embedding_text(qp: dict[str, Any]) -> str:
    nos_titles = "; ".join(n["title"] for n in qp["nos"])
    keywords = ", ".join(qp.get("keywords", []))
    return f"{qp['title']}. {qp.get('description', '')} Keywords: {keywords}. {nos_titles}"


@dataclass
class LexiconMatcher:
    entries: list[dict[str, Any]]
    _by_first: dict[str, list[tuple[tuple[str, ...], dict]]] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        for e in self.entries:
            toks = tuple(phrase_tokens(e["term"]))
            if toks:
                self._by_first.setdefault(toks[0], []).append((toks, e))
        for lst in self._by_first.values():
            lst.sort(key=lambda te: len(te[0]), reverse=True)

    def match(self, text: str) -> list[dict[str, Any]]:
        """Longest-match-first phrase matching; each token is consumed at most once."""
        toks = phrase_tokens(text)
        used = [False] * len(toks)
        found: list[tuple[int, int, dict]] = []
        # Longer phrases first across the whole text, so "co2 welding" beats "welding".
        max_len = max((len(t) for lst in self._by_first.values() for t, _ in lst), default=1)
        for length in range(max_len, 0, -1):
            for i in range(len(toks) - length + 1):
                if any(used[i : i + length]):
                    continue
                for phrase, entry in self._by_first.get(toks[i], ()):
                    if len(phrase) == length and tuple(toks[i : i + length]) == phrase:
                        found.append((i, length, entry))
                        for j in range(i, i + length):
                            used[j] = True
                        break
        found.sort(key=lambda f: f[0])
        return [
            {
                "term": e["term"],
                "canonical": e["canonical"],
                "category": e["category"],
                "expand": e["expand"],
                "source": e.get("source", "seed"),
            }
            for _, _, e in found
        ]


def softmax(xs: list[float], temperature: float) -> list[float]:
    if not xs:
        return []
    m = max(xs)
    exps = [math.exp((x - m) / temperature) for x in xs]
    s = sum(exps)
    return [e / s for e in exps]


class QPMapper:
    def __init__(
        self,
        corpus: dict[str, dict[str, Any]],
        lexicon_entries: list[dict[str, Any]],
        lexicon_version: str = "seed",
    ) -> None:
        self.corpus = corpus
        self.qp_ids = list(corpus)
        self.lexicon = LexiconMatcher(lexicon_entries)
        self.lexicon_version = lexicon_version
        self.docs = [qp_document(corpus[q]) for q in self.qp_ids]
        self.bm25 = BM25Okapi(self.docs, k1=BM25_K1, b=BM25_B)
        self.doc_sets = [set(d) for d in self.docs]
        self.generic = {q: self._generic_tokens(corpus[q]) for q in self.qp_ids}
        self.nos_terms = {q: self._nos_distinct_terms(corpus[q], self.generic[q]) for q in self.qp_ids}
        self.vector_index: NumpyVectorIndex | None = None
        self.embedder = None

    # ------------------------------------------------------------------ setup
    @staticmethod
    def _generic_tokens(qp: dict[str, Any]) -> set[str]:
        """Tokens too common to justify a PC claim on their own."""
        pcs = list(iter_pcs(qp))
        df = Counter(t for pc in pcs for t in set(tokenize(pc["text"])))
        frequent = {t for t, c in df.items() if len(pcs) >= 4 and c / len(pcs) > GENERIC_PC_DF}
        return frequent | set(tokenize(qp["title"])) | DOMAIN_GENERIC

    @staticmethod
    def _nos_distinct_terms(qp: dict[str, Any], generic: set[str]) -> dict[str, set[str]]:
        """Per NOS: keyword tokens used by at most 2 NOS of this QP (e.g. 'argon', 'tig')."""
        kw = {n["id"]: set(tokenize(" ".join(n.get("keywords", [])) + " " + n["title"])) for n in qp["nos"]}
        df = Counter(t for terms in kw.values() for t in terms)
        return {nid: {t for t in terms if df[t] <= 2 and t not in generic} for nid, terms in kw.items()}

    def attach_embeddings(self, embedder, vectors: dict[str, list[float]]) -> None:
        index = NumpyVectorIndex()
        for qp_id in self.qp_ids:
            if qp_id in vectors:
                index.add(qp_id, vectors[qp_id])
        if len(index) == len(self.qp_ids):
            self.vector_index = index
            self.embedder = embedder

    # ------------------------------------------------------------------ query
    def expand_query(self, narrative: str) -> tuple[list[str], list[dict[str, Any]]]:
        matches = self.lexicon.match(narrative)
        tokens = tokenize(narrative)
        for m in matches:
            for term in m["expand"]:
                tokens += tokenize(term)
        return tokens, matches

    def claims_for(self, qp_id: str, query_tokens: list[str]) -> list[dict[str, Any]]:
        """A NOS is claimed when the narrative hits one of its distinctive keywords.
        Inside a claimed NOS, a PC is 'strong' if its own text shares a non-generic
        term with the narrative, otherwise 'weak'. PCs of unclaimed NOS are 'none'."""
        qp = self.corpus[qp_id]
        q = set(query_tokens) - self.generic[qp_id]
        claims = []
        for nos in qp["nos"]:
            nos_hits = sorted(q & self.nos_terms[qp_id][nos["id"]])
            for pc in nos["pcs"]:
                pc_hits = sorted(q & set(tokenize(pc["text"]))) if nos_hits else []
                strength = "strong" if pc_hits else ("weak" if nos_hits else "none")
                claims.append(
                    {
                        "pc_id": pc["id"],
                        "nos_id": nos["id"],
                        "code": pc["code"],
                        "claimed": strength != "none",
                        "strength": strength,
                        "matched_terms": sorted(set(pc_hits) | set(nos_hits)),
                    }
                )
        return claims

    def map(self, narrative: str, top_n: int = 3) -> dict[str, Any]:
        query_tokens, matches = self.expand_query(narrative)
        bm25 = np.asarray(self.bm25.get_scores(query_tokens), dtype=np.float64)
        bm25_max = float(bm25.max()) if len(bm25) else 0.0
        bm25_norm = bm25 / bm25_max if bm25_max > 0 else np.zeros_like(bm25)

        cosine = None
        engine = "bm25+lexicon"
        if self.vector_index is not None and self.embedder is not None and narrative.strip():
            canon = " ".join(sorted({m["canonical"] for m in matches}))
            vec = self.embedder.encode([f"{narrative} {canon}".strip()])
            if vec is not None:
                sims = self.vector_index.similarity(vec[0])
                cosine = np.asarray([sims[q] for q in self.qp_ids], dtype=np.float64)
                engine = "hybrid"

        if cosine is not None:
            span = float(cosine.max() - cosine.min())
            cos_norm = (cosine - cosine.min()) / span if span > 0 else np.zeros_like(cosine)
            combined = HYBRID_BM25_WEIGHT * bm25_norm + (1 - HYBRID_BM25_WEIGHT) * cos_norm
        else:
            combined = bm25_norm

        order = sorted(range(len(self.qp_ids)), key=lambda i: combined[i], reverse=True)
        k = order[:TOP_K_SOFTMAX]
        # No lexical evidence at all (e.g. a misspelled one-liner): the ranking is not
        # meaningful, so report zero confidence and flag it instead of guessing.
        no_match = bm25_max <= 0
        conf = [] if no_match else softmax([float(combined[i]) for i in k], SOFTMAX_TEMPERATURE)
        idf = self.bm25.idf
        top = []
        for rank, i in enumerate(order[:top_n]):
            qp = self.corpus[self.qp_ids[i]]
            matched = sorted(
                {t for t in query_tokens if t in self.doc_sets[i]}, key=lambda t: (-idf.get(t, 0), t)
            )
            top.append(
                {
                    "rank": rank + 1,
                    "qp_id": qp["id"],
                    "title": qp["title"],
                    "title_hi": qp.get("title_hi"),
                    "sector": qp["sector"],
                    "nsqf_level": qp["nsqf_level"],
                    "source_kind": qp["source_kind"],
                    "score": round(float(combined[i]), 4),
                    "bm25": round(float(bm25[i]), 4),
                    "cosine": None if cosine is None else round(float(cosine[i]), 4),
                    # ranks outside the softmax window get 0 confidence
                    "confidence": round(conf[rank], 4) if rank < len(conf) else 0.0,
                    "matched_terms": matched[:10],
                }
            )
        return {
            "engine": engine,
            "no_match": no_match,
            "language_detected": detect_language(narrative),
            "query_terms": sorted(set(query_tokens)),
            "lexicon_matches": [{k2: v for k2, v in m.items() if k2 != "expand"} for m in matches],
            "top": top,
            "claims": {t["qp_id"]: self.claims_for(t["qp_id"], query_tokens) for t in top},
            "lexicon_version": self.lexicon_version,
            "confidence_note": f"softmax over top-{TOP_K_SOFTMAX} scores, T={SOFTMAX_TEMPERATURE}",
        }

    # ------------------------------------------------------------------ device pack
    def export_bm25(self) -> dict[str, Any]:
        return {
            "k1": BM25_K1,
            "b": BM25_B,
            "avgdl": self.bm25.avgdl,
            "idf": dict(self.bm25.idf),  # full precision: mapper-lite must reproduce scores exactly
            "docs": [
                {"qp_id": q, "len": len(d), "tf": dict(Counter(d))}
                for q, d in zip(self.qp_ids, self.docs, strict=True)
            ],
            "softmax_temperature": SOFTMAX_TEMPERATURE,
            "top_k_softmax": TOP_K_SOFTMAX,
            "generic_tokens": {q: sorted(g) for q, g in self.generic.items()},
        }
