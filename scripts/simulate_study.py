"""SIMULATED crossover (AB/BA) consistency study: unassisted vs assisted RPL scoring.

Everything here is a SIMULATION. The size of any improvement is driven by the ASSUMED
effect sizes below; the point is to show the measurement pipeline (Krippendorff's alpha,
decision agreement, decision flips) and how sensitive the conclusion is to the
assumptions. It is not evidence: real evidence needs the live study mode with real raters.

Design
  30 packets x 14 photo-judged PCs (Welding QP), 8 raters with a personal bias
  (leniency/severity) and noise. Raters are split into groups A and B. Packets 1-15 are
  scored by A unassisted and by B assisted; packets 16-30 the other way round
  (AB/BA crossover, so every rater works in both conditions and no packet is seen twice
  by the same rater). A small period (learning) effect is applied to the second half.

Assistance (assumptions)
  rubric anchors   rater bias x ANCHOR_BIAS, rater noise x ANCHOR_NOISE
  blind-first AI   AI suggestion = truth + N(0, AI_SD); after the blind score the rater
                   moves ADJUST_WEIGHT of the way towards the AI when |gap| >= 1 (rounded)

Outputs
  docs/results/consistency_study.md / .json and PNG charts in docs/results/

Usage:  python scripts/simulate_study.py [--reps 200] [--seed 26242]
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, replace
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.krippendorff import alpha

OUT = ROOT / "docs" / "results"
FRACTION = np.array([0.0, 0.4, 0.8, 1.0])


@dataclass(frozen=True)
class Assumptions:
    packets: int = 30
    pcs: int = 14
    raters: int = 8
    rater_bias_sd: float = 0.6  # latent-scale leniency/severity spread between raters
    rater_noise_lo: float = 0.5
    rater_noise_hi: float = 1.0
    anchor_bias: float = 0.6  # anchors keep 60% of a rater's bias
    anchor_noise: float = 0.7  # anchors keep 70% of a rater's noise
    ai_sd: float = 0.5  # AI error on the latent scale (~ our demo model's level accuracy)
    adjust_weight: float = 0.4  # how far raters move towards the AI after a gap >= 1
    period_effect: float = 0.1  # second-half noise reduction from practice (both arms)
    seconds_per_pc: float = 20.0  # time proxy: unassisted seconds per PC
    reveal_seconds: float = 6.0  # time proxy: reading the AI reveal
    reason_seconds: float = 15.0  # time proxy: entering a reason code (gap >= 2)


def candidate_truth(rng: np.random.Generator, a: Assumptions) -> np.ndarray:
    """Latent true levels: a candidate ability plus PC-level variation, on the 0-3 scale."""
    ability = rng.choice([0.8, 1.6, 2.2, 2.7], size=a.packets, p=[0.15, 0.25, 0.35, 0.25])
    latent = ability[:, None] + rng.normal(0, 0.45, (a.packets, a.pcs))
    return np.clip(latent, 0, 3)


def score(latent: np.ndarray, bias: float, noise: float, rng: np.random.Generator) -> np.ndarray:
    return np.clip(np.rint(latent + bias + rng.normal(0, noise, latent.shape)), 0, 3).astype(int)


def run_once(a: Assumptions, rng: np.random.Generator) -> dict:
    truth = candidate_truth(rng, a)
    true_levels = np.clip(np.rint(truth), 0, 3).astype(int)
    bias = rng.normal(0, a.rater_bias_sd, a.raters)
    noise = rng.uniform(a.rater_noise_lo, a.rater_noise_hi, a.raters)
    group_a = set(range(a.raters // 2))
    half = a.packets // 2
    scores = {"unassisted": {}, "assisted": {}}  # cond -> {(packet, rater): levels[pcs]}
    time = {"unassisted": 0.0, "assisted": 0.0}
    adjustments = 0
    for r in range(a.raters):
        for p in range(a.packets):
            first_half = p < half
            assisted = (r in group_a) != first_half  # AB for group A, BA for group B
            period = 1.0 - (a.period_effect if not first_half else 0.0)
            if not assisted:
                s = score(truth[p], bias[r], noise[r] * period, rng)
                scores["unassisted"][(p, r)] = s
                time["unassisted"] += a.seconds_per_pc * a.pcs
            else:
                blind = score(truth[p], bias[r] * a.anchor_bias, noise[r] * a.anchor_noise * period, rng)
                ai = np.clip(np.rint(truth[p] + rng.normal(0, a.ai_sd, a.pcs)), 0, 3)
                gap = ai - blind
                move = np.abs(gap) >= 1
                final = np.where(move, np.clip(np.rint(blind + a.adjust_weight * gap), 0, 3), blind).astype(
                    int
                )
                adjustments += int((final != blind).sum())
                scores["assisted"][(p, r)] = final
                time["assisted"] += a.pcs * (a.seconds_per_pc + a.reveal_seconds) + a.reason_seconds * int(
                    (np.abs(gap) >= 2).sum()
                )

    out = {}
    for cond, cs in scores.items():
        raters_of = {}
        for (p, r), s in cs.items():
            raters_of.setdefault(p, {})[r] = s
        units = [
            [raters_of[p][r][k] if r in raters_of[p] else None for r in range(a.raters)]
            for p in raters_of
            for k in range(a.pcs)
        ]
        per_pc = [
            alpha(
                [
                    [raters_of[p][r][k] if r in raters_of[p] else None for r in range(a.raters)]
                    for p in raters_of
                ],
                "ordinal",
            )
            for k in range(a.pcs)
        ]
        decisions = {
            p: {r: int(FRACTION[s].mean() >= 0.7) for r, s in rs.items()} for p, rs in raters_of.items()
        }
        dec_units = [[d.get(r) for r in range(a.raters)] for d in decisions.values()]
        true_pass = {p: int(FRACTION[true_levels[p]].mean() >= 0.7) for p in raters_of}
        flips = np.mean([len(set(d.values())) > 1 for d in decisions.values()])
        correct = np.mean([v == true_pass[p] for p, d in decisions.items() for v in d.values()])
        mae = np.mean([np.abs(s - true_levels[p]).mean() for (p, _), s in cs.items()])
        out[cond] = {
            "alpha": alpha(units, "ordinal"),
            "alpha_per_pc_mean": float(np.nanmean([x for x in per_pc if x is not None])),
            "alpha_decision": alpha(dec_units, "nominal"),
            "decision_flip_rate": float(flips),
            "decision_accuracy": float(correct),
            "mae_vs_truth": float(mae),
            "seconds_per_packet": time[cond] / len(cs),
        }
    out["assisted"]["ai_adjusted_share"] = adjustments / (len(scores["assisted"]) * a.pcs)
    return out


def summarise(runs: list[dict]) -> dict:
    keys = [k for k in runs[0]["unassisted"] if k != "ai_adjusted_share"]
    res = {}
    for cond in ("unassisted", "assisted"):
        res[cond] = {}
        for k in keys + (["ai_adjusted_share"] if cond == "assisted" else []):
            vals = np.array([r[cond][k] for r in runs if r[cond][k] is not None], dtype=float)
            res[cond][k] = {
                "mean": float(vals.mean()),
                "p2_5": float(np.percentile(vals, 2.5)),
                "p97_5": float(np.percentile(vals, 97.5)),
            }
    deltas = np.array([r["assisted"]["alpha"] - r["unassisted"]["alpha"] for r in runs])
    res["alpha_gain"] = {
        "mean": float(deltas.mean()),
        "p2_5": float(np.percentile(deltas, 2.5)),
        "p97_5": float(np.percentile(deltas, 97.5)),
        "share_positive": float((deltas > 0).mean()),
    }
    return res


SCENARIOS = {
    "baseline (assumptions above)": {},
    "anchors have no effect (AI reveal only)": {"anchor_bias": 1.0, "anchor_noise": 1.0},
    "noisy AI (sd 1.2) with anchors": {"ai_sd": 1.2},
    "noisy AI (sd 1.2), no anchors": {"ai_sd": 1.2, "anchor_bias": 1.0, "anchor_noise": 1.0},
    "raters ignore the AI (weight 0)": {"adjust_weight": 0.0},
}


def charts(base: dict, scen: dict) -> list[str]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    blue, orange, ink, muted = "#2a78d6", "#eb6834", "#0b0b0b", "#52514e"
    files = []
    metrics = [
        ("alpha", "Krippendorff α (PC scores)"),
        ("alpha_decision", "α (pass/fail decision)"),
        ("decision_flip_rate", "Decision flip rate (lower is better)"),
    ]
    fig, axes = plt.subplots(1, 3, figsize=(11, 3.4))
    for ax, (k, title) in zip(axes, metrics, strict=True):
        for i, (cond, col) in enumerate((("unassisted", blue), ("assisted", orange))):
            m = base[cond][k]
            ax.bar(i, m["mean"], width=0.55, color=col, zorder=2)
            ax.errorbar(
                i,
                m["mean"],
                yerr=[[m["mean"] - m["p2_5"]], [m["p97_5"] - m["mean"]]],
                color=ink,
                capsize=4,
                lw=1.2,
                zorder=3,
            )
            ax.text(i, m["p97_5"] + 0.02, f"{m['mean']:.2f}", ha="center", color=ink, fontsize=9)
        ax.set_xticks([0, 1], ["Unassisted", "Assisted"], color=ink)
        ax.set_title(title, fontsize=10, color=ink)
        ax.set_ylim(0, 1.05)
        ax.grid(axis="y", color="#e3e9f7", zorder=0)
        ax.spines[["top", "right"]].set_visible(False)
        ax.tick_params(colors=muted)
    fig.suptitle(
        "SIMULATED crossover study — mean and 95% interval over replications", fontsize=10, color=muted
    )
    fig.tight_layout()
    f = OUT / "consistency_study_alpha.png"
    fig.savefig(f, dpi=150)
    plt.close(fig)
    files.append(f.name)

    fig, ax = plt.subplots(figsize=(8, 3.2))
    names = list(scen)
    gains = [scen[n]["alpha_gain"] for n in names]
    y = np.arange(len(names))[::-1]
    ax.axvline(0, color=muted, lw=1)
    for yi, g in zip(y, gains, strict=True):
        ax.plot([g["p2_5"], g["p97_5"]], [yi, yi], color=blue, lw=2)
        ax.plot(g["mean"], yi, "o", color=blue, ms=8)
        ax.text(g["p97_5"] + 0.01, yi, f"{g['mean']:+.2f}", va="center", fontsize=9, color=ink)
    ax.set_yticks(y, names, fontsize=9, color=ink)
    ax.set_xlabel("Change in α (assisted − unassisted)", color=muted)
    ax.set_title("SIMULATED sensitivity: the gain depends on the assumptions", fontsize=10, color=ink)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    f = OUT / "consistency_study_sensitivity.png"
    fig.savefig(f, dpi=150)
    plt.close(fig)
    files.append(f.name)
    return files


def pct(x: float) -> str:
    return f"{100 * x:.0f}%"


def write_report(a: Assumptions, reps: int, seed: int, base: dict, scen: dict, files: list[str]) -> None:
    def row(label, k, fmt):
        u, s = base["unassisted"][k], base["assisted"][k]
        return (
            f"| {label} | {fmt(u['mean'])} ({fmt(u['p2_5'])}–{fmt(u['p97_5'])}) | "
            f"{fmt(s['mean'])} ({fmt(s['p2_5'])}–{fmt(s['p97_5'])}) |"
        )

    f2 = lambda x: f"{x:.2f}"  # noqa: E731
    lines = (
        [
            "# Consistency study — SIMULATED",
            "",
            "> **This is a simulation, not evidence.** The improvement it shows comes from the assumed "
            "effect sizes "
            "listed below. Its purpose is to exercise the measurement (Krippendorff's α, decision "
            "agreement) and to "
            "show how the conclusion depends on the assumptions. Real evidence must come from the **live "
            "study mode** "
            "in the app, with real assessors scoring the same packets with assistance OFF and then ON.",
            "",
            f"Generated by `python scripts/simulate_study.py --reps {reps} --seed {seed}`.",
            "",
            "## Design",
            "",
            f"- Crossover AB/BA: {a.packets} packets × {a.pcs} photo-judged PCs (Welding QP), {a.raters} "
            "raters in two "
            "groups. Each rater scores every packet once: half unassisted, half assisted. The packet "
            "halves are swapped "
            "between groups, and a small practice effect is applied to the second half in both arms.",
            "- Unassisted: each rater has a personal bias (leniency or severity) and noise.",
            "- Assisted: the rubric anchors reduce bias and noise. After the blind score the AI suggestion "
            "is revealed "
            "and the rater moves part of the way towards it when the gap is ≥ 1.",
            f"- {reps} Monte-Carlo replications. Values are means with 95% intervals.",
            "",
            "## Assumptions",
            "",
            "| Parameter | Value |",
            "|---|---|",
        ]
        + [f"| `{k}` | {v} |" for k, v in asdict(a).items()]
        + [
            "",
            "## Results (baseline assumptions)",
            "",
            "| Metric | Unassisted | Assisted |",
            "|---|---|---|",
            row("Krippendorff α, PC scores (ordinal)", "alpha", f2),
            row("Mean per-PC α", "alpha_per_pc_mean", f2),
            row("α, pass/fail decision (nominal)", "alpha_decision", f2),
            row("Packets where raters disagree on pass/fail (flip rate)", "decision_flip_rate", pct),
            row("Decisions matching the simulated truth", "decision_accuracy", pct),
            row("Mean absolute error vs truth (levels)", "mae_vs_truth", f2),
            row("Time proxy, seconds per packet", "seconds_per_packet", lambda x: f"{x:.0f}"),
            "",
            f"Share of assisted PC scores changed after the AI reveal: "
            f"{pct(base['assisted']['ai_adjusted_share']['mean'])}.",
            f"Change in α: **{base['alpha_gain']['mean']:+.2f}** "
            f"(95% interval {base['alpha_gain']['p2_5']:+.2f} to {base['alpha_gain']['p97_5']:+.2f}); "
            "assisted was "
            f"higher in {pct(base['alpha_gain']['share_positive'])} of replications.",
            "",
            f"![alpha]({files[0]})",
            "",
            "## Sensitivity — when assistance would NOT help",
            "",
            "| Scenario | Change in α (mean, 95% interval) | Assisted better in |",
            "|---|---|---|",
        ]
        + [
            f"| {n} | {g['mean']:+.2f} ({g['p2_5']:+.2f} to {g['p97_5']:+.2f}) | {pct(g['share_positive'])} |"
            for n, g in ((n, s["alpha_gain"]) for n, s in scen.items())
        ]
        + [
            "",
            f"![sensitivity]({files[1]})",
            "",
            "## Honest reading",
            "",
            f"- Where the gain comes from (in these assumptions): with raters ignoring the AI the gain is "
            f"{scen['raters ignore the AI (weight 0)']['alpha_gain']['mean']:+.2f}, and with no anchor "
            "effect "
            f"it is {scen['anchors have no effect (AI reveal only)']['alpha_gain']['mean']:+.2f}. The AI "
            "reveal "
            f"changed only {pct(base['assisted']['ai_adjusted_share']['mean'])} of scores. Most of the "
            "modelled improvement comes from the shared rubric anchors, not from the AI.",
            "- With the baseline assumptions, assistance raises agreement and cuts pass/fail flips. The "
            "size of the "
            "effect is set by `anchor_*`, `ai_sd` and `adjust_weight`, all of which are assumptions.",
            "- Agreement is not accuracy. A noisy AI that raters follow can make them agree with each "
            "other *and* with "
            "the AI's errors. The noisy-AI rows show where the gain shrinks or reverses, which is why the "
            "UI shows the "
            "AI only after the blind score, keeps the blind score in the ledger, and asks for a reason on "
            "large gaps.",
            "- Assistance costs time (reading the reveal, reason codes) in this proxy. Real timing must be "
            "measured.",
            "- Next step: run the in-app live study (QA → Studies) with real assessors, OFF then ON, on "
            "the same "
            "packets.",
            "",
        ]
    )
    (OUT / "consistency_study.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=200)
    ap.add_argument("--seed", type=int, default=26242)
    args = ap.parse_args()
    base_a = Assumptions()
    OUT.mkdir(parents=True, exist_ok=True)
    scen = {}
    for name, over in SCENARIOS.items():
        rng = np.random.default_rng(args.seed)
        a = replace(base_a, **over)
        scen[name] = summarise([run_once(a, rng) for _ in range(args.reps)])
    base = scen["baseline (assumptions above)"]
    files = charts(base, scen)
    write_report(base_a, args.reps, args.seed, base, scen, files)
    (OUT / "consistency_study.json").write_text(
        json.dumps(
            {
                "simulated": True,
                "reps": args.reps,
                "seed": args.seed,
                "assumptions": asdict(base_a),
                "baseline": base,
                "scenarios": {k: v["alpha_gain"] for k, v in scen.items()},
            },
            indent=1,
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        f"alpha unassisted {base['unassisted']['alpha']['mean']:.3f} -> assisted "
        f"{base['assisted']['alpha']['mean']:.3f}"
        f"  (gain {base['alpha_gain']['mean']:+.3f})"
    )
    for n, s in scen.items():
        print(
            f"  {n:45s} gain {s['alpha_gain']['mean']:+.3f}  better in "
            f"{pct(s['alpha_gain']['share_positive'])}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
