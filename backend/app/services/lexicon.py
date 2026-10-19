"""Trade-vernacular lexicon: seed file + assessor-confirmed additions from the DB."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from typing import Any

from sqlmodel import Session, select

from app.core.config import DATA_DIR
from app.models.lexicon import LexiconAddition

LEXICON_PATH = DATA_DIR / "lexicon" / "lexicon.json"
DEVANAGARI = re.compile(r"[ऀ-ॿ]")


@lru_cache
def load_seed_lexicon() -> dict[str, Any]:
    return json.loads(LEXICON_PATH.read_text(encoding="utf-8"))


def all_entries(session: Session | None = None) -> list[dict[str, Any]]:
    entries = [dict(e) for e in load_seed_lexicon()["entries"]]
    if session is not None:
        known = {e["term"].lower() for e in entries}
        for add in session.exec(select(LexiconAddition).order_by(LexiconAddition.id)):
            if add.term.lower() in known:
                continue
            entries.append(
                {
                    "term": add.term,
                    "lang": add.lang,
                    "canonical": add.canonical,
                    "category": add.category,
                    "expand": list(add.expand),
                    "source": "assessor",
                }
            )
    return entries


def lexicon_version(session: Session | None = None) -> str:
    base = load_seed_lexicon()["version"]
    if session is None:
        return base
    count = len(list(session.exec(select(LexiconAddition.id))))
    return f"{base}+{count}"


def detect_lang(term: str) -> str:
    return "hi" if DEVANAGARI.search(term) else "hinglish"
