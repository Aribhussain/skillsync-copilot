"""Export the seed QP pack and the Python mapper's results for a set of narratives, so the
TypeScript mapper-lite unit tests can prove they produce the same BM25 + lexicon output.

Writes frontend/public/packs/seed-pack.json (also bundled into the PWA as the offline
fallback pack for devices that have never reached the server) and
frontend/src/lib/mapper/__fixtures__/parity.json. A backend test fails if they are stale.
Re-run this script after changing the corpus, the lexicon or the tokenizer.

Usage:  python scripts/export_parity_fixture.py
"""

from __future__ import annotations

import importlib.util
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.api.packs import pack_content  # noqa: E402
from app.services.evidence_plan import build_plan  # noqa: E402
from app.services.lexicon import all_entries  # noqa: E402
from app.services.mapping import QPMapper  # noqa: E402
from app.services.qp_store import load_corpus  # noqa: E402

OUT = ROOT / "frontend" / "src" / "lib" / "mapper" / "__fixtures__"
SEED_PACK = ROOT / "frontend" / "public" / "packs" / "seed-pack.json"
GOLDEN = (
    "Main 6 saal se fabrication shop mein kaam karta hoon, CO2 aur argon dono welding karta hoon, "
    "plate aur pipe joint banata hoon, grinding karke finishing deta hoon"
)


def narratives() -> list[str]:
    spec = importlib.util.spec_from_file_location("gen", ROOT / "scripts" / "generate_synthetic.py")
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    synthetic = [w["narrative"] for w in gen.generate_workers(random.Random(26242))][:30]
    hard = json.loads((ROOT / "data" / "eval" / "hard_narratives.json").read_text(encoding="utf-8"))["items"]
    edge = ["", "hoon karta", "वेल्डिंग।", "TIG_welding on SS sheets", "Welding!!! CO2, MIG; argon-TIG."]
    return [GOLDEN, *synthetic, *[h["text"] for h in hard], *edge]


def build() -> tuple[dict, dict]:
    entries = all_entries()  # seed lexicon only (no DB additions)
    mapper = QPMapper(load_corpus(), entries)
    pack = pack_content(mapper, entries)
    cases = []
    for text in narratives():
        r = mapper.map(text, top_n=3)
        cases.append(
            {
                "text": text,
                "no_match": r["no_match"],
                "top": [
                    {"qp_id": t["qp_id"], "bm25": t["bm25"], "confidence": t["confidence"]} for t in r["top"]
                ],
                "lexicon_terms": [m["term"] for m in r["lexicon_matches"]],
                "claimed_pc_ids": sorted(
                    c["pc_id"] for c in r["claims"][r["top"][0]["qp_id"]] if c["claimed"]
                ),
            }
        )
    # Evidence-plan parity: every QP with nothing claimed, and with every PC claimed.
    plans = []
    for qp in load_corpus().values():
        all_ids = [p["id"] for n in qp["nos"] for p in n["pcs"]]
        for claimed in ([], all_ids):
            plan = build_plan(qp, claimed)
            plans.append(
                {
                    "qp_id": qp["id"],
                    "claimed": claimed,
                    "routes": {
                        p["pc_id"]: [p["route"], p["locked"], p["rule"]] for n in plan for p in n["pcs"]
                    },
                }
            )
    return pack, {"pack_version": pack["pack_version"], "cases": cases, "plans": plans}


def main() -> None:
    pack, parity = build()
    OUT.mkdir(parents=True, exist_ok=True)
    SEED_PACK.parent.mkdir(parents=True, exist_ok=True)
    SEED_PACK.write_text(json.dumps(pack, ensure_ascii=False) + "\n", encoding="utf-8")
    (OUT / "parity.json").write_text(
        json.dumps(parity, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    print(f"pack {pack['pack_version']}: {len(parity['cases'])} parity cases -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
