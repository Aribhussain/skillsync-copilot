from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from sqlmodel import Session

from app.core.db import get_session
from app.core.security import canonical_json, sha256_hex, utcnow_iso
from app.services.lexicon import all_entries
from app.services.qp_store import get_corpus, iter_pcs
from app.services.text_norm import DEVANAGARI_RANGE, STOPWORDS, phrase_tokens, tokenize

router = APIRouter(prefix="/packs", tags=["offline packs"])


def build_pack(request: Request, session: Session) -> dict:
    """Everything mapper-lite needs offline. Lexicon phrases, expansions and PC texts
    are shipped pre-tokenised, so the device only has to tokenise the narrative."""
    mapper = request.app.state.mapping.get_mapper(session)
    corpus = get_corpus()
    lexicon = [
        {
            "term": e["term"],
            "tokens": phrase_tokens(e["term"]),
            "canonical": e["canonical"],
            "category": e["category"],
            "expand_tokens": [t for x in e["expand"] for t in tokenize(x)],
            "source": e.get("source", "seed"),
        }
        for e in all_entries(session)
    ]
    content = {
        "kind": "skillsync.qp_pack",
        "tokenizer": {
            "stopwords": sorted(STOPWORDS),
            "stem": "strip a trailing s from latin tokens longer than 3 chars that do not end in ss",
            "devanagari_range": list(DEVANAGARI_RANGE),
        },
        "bm25": mapper.export_bm25(),
        "claims": {
            "nos_terms": {q: {n: sorted(t) for n, t in d.items()} for q, d in mapper.nos_terms.items()},
            "pc_tokens": {
                p["id"]: sorted(set(tokenize(p["text"]))) for qp in corpus.values() for p in iter_pcs(qp)
            },
        },
        "lexicon_version": mapper.lexicon_version,
        "lexicon": lexicon,
        "qps": list(corpus.values()),
    }
    version = sha256_hex(canonical_json(content))[:16]
    return {"pack_version": version, "generated_at": utcnow_iso(), **content}


@router.get("/latest")
def latest_pack(request: Request, response: Response, session: Session = Depends(get_session)) -> dict:
    """QP pack for the device: QPs + BM25 stats + lexicon, for the offline mapper-lite."""
    pack = build_pack(request, session)
    response.headers["ETag"] = f'"{pack["pack_version"]}"'
    return pack


@router.get("/version")
def pack_version(request: Request, session: Session = Depends(get_session)) -> dict:
    return {"pack_version": build_pack(request, session)["pack_version"]}
