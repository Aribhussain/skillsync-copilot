"""Evaluate the QP mapping engine and write docs/results/mapping_accuracy.md.

Datasets
  synthetic  60 template-generated narratives (data/synthetic/workers.json, seed 26242).
             Easy: we wrote the templates and the lexicon together.
  hard       30 held-out hand-written narratives (data/eval/hard_narratives.json), written
             before the first run and not used for tuning.

Engines
  bm25+lexicon         the default; the same algorithm runs on-device (mapper-lite)
  bm25 (no lexicon)    ablation: shows what the trade-vernacular lexicon contributes
  hybrid               bm25+lexicon with the multilingual embedding re-rank (if the model is available)

Usage
  python ml/eval_mapping.py                 # evaluate and write the report
  python ml/eval_mapping.py --calibrate     # also fit the softmax temperature on a separate
                                            # calibration split (synthetic, seed 7)
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import random
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import get_settings  # noqa: E402
from app.ml.embeddings import EmbeddingModel  # noqa: E402
from app.services import mapping as mapping_mod  # noqa: E402
from app.services.lexicon import all_entries  # noqa: E402
from app.services.mapping import QPMapper, qp_embedding_text  # noqa: E402
from app.services.qp_store import load_corpus  # noqa: E402

OUT_MD = ROOT / "docs" / "results" / "mapping_accuracy.md"
OUT_JSON = ROOT / "docs" / "results" / "mapping_accuracy.json"


def _generator():
    spec = importlib.util.spec_from_file_location("gen", ROOT / "scripts" / "generate_synthetic.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_sets() -> dict[str, list[dict]]:
    gen = _generator()
    synthetic = [
        {"id": w["id"], "lang": w["language"], "qp": w["ground_truth_qp"], "text": w["narrative"]}
        for w in gen.generate_workers(random.Random(26242))
    ]
    hard = json.loads((ROOT / "data" / "eval" / "hard_narratives.json").read_text(encoding="utf-8"))["items"]
    return {"synthetic": synthetic, "hard": hard}


def calibration_split() -> list[dict]:
    gen = _generator()
    return [
        {"qp": w["ground_truth_qp"], "text": w["narrative"]} for w in gen.generate_workers(random.Random(7))
    ]


def evaluate(mapper: QPMapper, items: list[dict]) -> dict:
    n = len(items)
    top1 = top3 = 0
    rr = 0.0
    by_lang: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    conf_bins: list[tuple[float, int]] = []
    errors = []
    for it in items:
        r = mapper.map(it["text"], top_n=len(mapper.qp_ids))
        ranked = [t["qp_id"] for t in r["top"]]
        rank = ranked.index(it["qp"]) + 1 if it["qp"] in ranked else None
        hit1 = rank == 1
        top1 += hit1
        top3 += bool(rank and rank <= 3)
        rr += 1 / rank if rank else 0
        by_lang[it["lang"]][0] += hit1
        by_lang[it["lang"]][1] += 1
        conf_bins.append((r["top"][0]["confidence"], int(hit1)))
        if not hit1:
            errors.append(
                {
                    "id": it.get("id"),
                    "expected": it["qp"],
                    "got": ranked[:3],
                    "text": it["text"],
                    "no_match": r["no_match"],
                }
            )
    return {
        "n": n,
        "top1": top1 / n,
        "top3": top3 / n,
        "mrr": rr / n,
        "ece": expected_calibration_error(conf_bins),
        "mean_top1_confidence": sum(c for c, _ in conf_bins) / n,
        "by_language": {k: {"top1": v[0] / v[1], "n": v[1]} for k, v in sorted(by_lang.items())},
        "errors": errors,
    }


def expected_calibration_error(pairs: list[tuple[float, int]], bins: int = 10) -> float:
    total = len(pairs)
    ece = 0.0
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        sel = [(c, y) for c, y in pairs if lo < c <= hi or (b == 0 and c == 0)]
        if sel:
            conf = sum(c for c, _ in sel) / len(sel)
            acc = sum(y for _, y in sel) / len(sel)
            ece += len(sel) / total * abs(conf - acc)
    return ece


def fit_temperature(mapper: QPMapper, items: list[dict]) -> float:
    """Grid-search T minimising negative log-likelihood of the true QP."""
    best_t, best_nll = None, math.inf
    for t in [0.03, 0.05, 0.08, 0.1, 0.12, 0.15, 0.2, 0.25, 0.3, 0.4, 0.5]:
        mapping_mod.SOFTMAX_TEMPERATURE = t
        nll = 0.0
        for it in items:
            r = mapper.map(it["text"], top_n=mapping_mod.TOP_K_SOFTMAX)
            p = next((x["confidence"] for x in r["top"] if x["qp_id"] == it["qp"]), 0.0)
            nll -= math.log(max(p, 1e-4))
        if nll < best_nll:
            best_t, best_nll = t, nll
    return best_t


def build_mappers(with_embeddings: bool) -> dict[str, QPMapper]:
    corpus = load_corpus()
    mappers = {
        "bm25+lexicon": QPMapper(corpus, all_entries()),
        "bm25 (no lexicon)": QPMapper(corpus, []),
    }
    if with_embeddings:
        s = get_settings()
        emb = EmbeddingModel(s.embedding_model, s.storage_path / "models" / "hf", enabled=True)
        emb.warm_up(block=True)
        if emb.ready:
            hybrid = QPMapper(corpus, all_entries())
            vecs = emb.encode([qp_embedding_text(corpus[q]) for q in hybrid.qp_ids])
            hybrid.attach_embeddings(emb, {q: v.tolist() for q, v in zip(hybrid.qp_ids, vecs, strict=True)})
            mappers["hybrid (bm25+lexicon+embeddings)"] = hybrid
        else:
            print(f"embedding model unavailable: {emb.error}")
    return mappers


def pct(x: float) -> str:
    return f"{100 * x:.1f}%"


def write_report(results: dict, temperature: float, calibrated: float | None) -> None:
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(results, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    lines = [
        "# QP mapping accuracy",
        "",
        "> Generated by `python ml/eval_mapping.py`. **All narratives are synthetic** (no real worker data).",
        "",
        "Two datasets:",
        "",
        "- **synthetic**: 60 template-generated narratives. This set is *easy* because the templates and the "
        "lexicon were written by the same team. Treat it as a sanity check, not as evidence.",
        "- **hard**: 30 held-out, hand-written narratives (`data/eval/hard_narratives.json`). They are short, "
        "vague or misspelled, use brand names and include cross-trade traps. They were written before the first "
        "evaluation run and **not** used for tuning. Ground truth is the team's judgement, and some items are "
        "genuinely ambiguous between the four welding QPs.",
        "",
        f"Confidence is a softmax over the top-{mapping_mod.TOP_K_SOFTMAX} scores with T = {temperature}.",
    ]
    if calibrated is not None:
        lines.append(
            f"The temperature fitted on a separate calibration split (synthetic, seed 7) is T = {calibrated}."
        )
    lines += [
        "",
        "| Engine | Dataset | n | Top-1 | Top-3 | MRR | Mean top-1 conf. | ECE |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for engine, sets in results["engines"].items():
        for ds, r in sets.items():
            lines.append(
                f"| {engine} | {ds} | {r['n']} | {pct(r['top1'])} | {pct(r['top3'])} | {r['mrr']:.3f} | "
                f"{pct(r['mean_top1_confidence'])} | {r['ece']:.3f} |"
            )
    lines += [
        "",
        "**Target:** at least 85% top-3. ECE is the expected calibration error of the top-1 confidence; lower is better.",
        "",
    ]
    lines += [
        "## Top-1 by language (bm25+lexicon)",
        "",
        "| Dataset | Language | n | Top-1 |",
        "|---|---|---|---|",
    ]
    for ds, r in results["engines"]["bm25+lexicon"].items():
        for lang, v in r["by_language"].items():
            lines.append(f"| {ds} | {lang} | {v['n']} | {pct(v['top1'])} |")
    for engine, sets in results["engines"].items():
        errs = sets["hard"]["errors"]
        lines += ["", f"## Misses on the hard set: {engine} ({len(errs)})", ""]
        if not errs:
            lines.append("None.")
        else:
            lines += ["| id | text | expected | got (top-3) |", "|---|---|---|---|"]
            for e in errs:
                lines.append(f"| {e['id']} | {e['text']} | {e['expected']} | {', '.join(e['got'])} |")
    default = results["engines"]["bm25+lexicon"]["hard"]
    no_match = [e for e in default["errors"] if e["no_match"]]
    welding_family = [
        e
        for e in default["errors"]
        if not e["no_match"] and "WELD" in e["expected"] and "WELD" in e["got"][0]
    ]
    other = [e for e in default["errors"] if e not in no_match and e not in welding_family]
    lex = (
        results["engines"]["bm25+lexicon"]["hard"]["top3"]
        - results["engines"]["bm25 (no lexicon)"]["hard"]["top3"]
    )
    lines += [
        "",
        "## Honest reading",
        "",
        "- The synthetic score is inflated by construction. The hard set is the better indicator, but it is small "
        "(n = 30) and also synthetic.",
        f"- The trade-vernacular lexicon adds {100 * lex:+.1f} points of top-3 accuracy on the hard set (ablation).",
        f"- Hard-set misses for the default engine: {len(default['errors'])}. Of these, {len(no_match)} had no "
        f"lexical match at all, {len(welding_family)} were confusions within the welding family, and "
        f"{len(other)} were cross-trade errors.",
        "- With no lexical match the mapper sets `no_match: true` and reports 0 confidence. The UI then asks the "
        "worker to say more or pick icon cards instead of showing arbitrary QPs.",
        "- Cross-trade errors come from shared words (e.g. 'पाइपलाइन' in a plumber's narrative) or slang the "
        "lexicon doesn't know yet (e.g. 'scooty', 'self start'). Assessor-confirmed lexicon additions are the "
        "intended fix.",
        "- The worker and the assessor always confirm the QP, so the top-3 list matters more than top-1.",
        "- A real evaluation needs narratives from actual RPL candidates, transcribed from speech.",
        "",
    ]
    if calibrated is not None:
        lines += [
            "## About the temperature",
            "",
            f"Fitting T on the calibration split gives T = {calibrated}. That split is template-generated and "
            "almost perfectly separable, so the likelihood keeps improving as T shrinks, which means maximum "
            f"over-confidence. We therefore keep the pre-set T = {temperature}, chosen before any evaluation. "
            "Proper calibration needs real narratives.",
            "",
        ]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--calibrate", action="store_true")
    ap.add_argument("--no-embeddings", action="store_true")
    args = ap.parse_args()

    sets = load_sets()
    mappers = build_mappers(with_embeddings=not args.no_embeddings)
    shipped_t = mapping_mod.SOFTMAX_TEMPERATURE
    calibrated = None
    if args.calibrate:
        calibrated = fit_temperature(mappers["bm25+lexicon"], calibration_split())
        print(f"fitted temperature on calibration split: {calibrated} (shipped: {shipped_t})")
    # Always evaluate with the temperature that ships in app/services/mapping.py.
    temperature = mapping_mod.SOFTMAX_TEMPERATURE = shipped_t
    results = {"temperature": temperature, "calibrated_temperature": calibrated, "engines": {}}
    for name, m in mappers.items():
        results["engines"][name] = {ds: evaluate(m, items) for ds, items in sets.items()}
        for ds, r in results["engines"][name].items():
            print(
                f"{name:36s} {ds:9s} top1={pct(r['top1']):>6s} top3={pct(r['top3']):>6s} ece={r['ece']:.3f}"
            )
    write_report(results, temperature, calibrated)
    print(f"wrote {OUT_MD.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
