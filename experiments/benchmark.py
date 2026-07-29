"""The honest MOT benchmarking tool — Horizon 3.

One command turns the study's machinery into a shareable product: run a set of
trackers on a dataset, and get back a single **reproducible report** that combines

1. a **leaderboard** (mean±std per metric),
2. **paired significance** vs a chosen baseline (Wilcoxon p + Cohen's d — because
   every tracker sees identical detections/seeds),
3. an **ID-switch error taxonomy** (why the baseline swaps identities), and
4. **reproducibility metadata** (dataset, sequences, seeds, config hash).

rendered to both markdown and a self-contained, theme-aware HTML page.

    python -m experiments.benchmark --dataset synthetic --out-html report.html
    python -m experiments.benchmark --trackers sort,bytetrack,bytetrack_reid

This is the zoo + analyze + error-taxonomy pieces unified behind one entry point —
the "drop in a tracker, get a rigorous comparison" flow.
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(_ROOT), str(_ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from experiments.config import ExperimentConfig, VariantSpec  # noqa: E402
from experiments.error_taxonomy import (  # noqa: E402
    _CROWD_THRESH,
    _FAST_THRESH,
    _OCC_THRESH,
    _rate,
    _run_frames,
    _synthetic_frames,
)
from experiments.run_matrix import run  # noqa: E402
from visiontrack.eval.stats import compare, summarize  # noqa: E402
from visiontrack.tracking.presets import PRESET_NAMES, preset_overrides  # noqa: E402

_METRICS = ["MOTA", "IDF1", "HOTA", "IDSW"]
# Metrics where higher is better (for best-in-column highlighting).
_HIGHER_BETTER = {"MOTA", "IDF1", "HOTA", "MT"}
_ZOO_SCENE = {
    "num_objects": 12, "num_frames": 100, "loc_noise_std": 8.0,
    "occlusion_iou": 0.30, "false_positive_rate": 0.6,
    "appearance_dim": 32, "appearance_diversity": 0.7,
}


@dataclass(slots=True)
class BenchmarkReport:
    dataset: str
    baseline: str
    metrics: list
    leaderboard: list = field(default_factory=list)   # per-tracker dicts
    taxonomy: list = field(default_factory=list)       # condition dicts
    meta: dict = field(default_factory=dict)

    def best(self, metric: str):
        """Name of the leading tracker on ``metric`` (direction-aware)."""
        higher = metric in _HIGHER_BETTER
        vals = [(r["name"], r["summary"][metric][0]) for r in self.leaderboard]
        return (max if higher else min)(vals, key=lambda kv: kv[1])[0]

    def to_markdown(self) -> str:
        return _render_markdown(self)

    def to_html(self) -> str:
        return _render_html(self)


def run_benchmark(
    dataset: str = "synthetic",
    tracker_names: list | None = None,
    baseline: str = "bytetrack",
    sequences: list | None = None,
    seeds: list | None = None,
) -> BenchmarkReport:
    """Run the trackers, score them, and assemble a :class:`BenchmarkReport`."""
    names = tracker_names or list(PRESET_NAMES)
    if baseline not in names:
        names = [baseline, *names]
    sequences = sequences or [1, 2, 3]
    seeds = seeds or [0, 1, 2, 3, 4]

    variants = [VariantSpec(n, preset_overrides(n)) for n in names]
    exp = ExperimentConfig(
        name=f"benchmark_{dataset}", dataset=dataset, sequences=sequences,
        seeds=seeds, baseline=baseline, metrics=_METRICS, scene=_ZOO_SCENE,
        variants=variants,
    )
    df = run(exp)

    # -- leaderboard: summary + paired comparison vs baseline ------------
    leaderboard = []
    for name in names:
        summ, comp = {}, {}
        for m in _METRICS:
            v = df[df.variant == name].set_index(["sequence", "seed"])[m].sort_index()
            b = df[df.variant == baseline].set_index(["sequence", "seed"])[m].sort_index()
            idx = v.index.intersection(b.index)
            s = summarize(v.loc[idx].to_numpy(float))
            summ[m] = (s.mean, s.std)
            c = compare(v.loc[idx].to_numpy(float), b.loc[idx].to_numpy(float), seed=0)
            comp[m] = (c.delta, c.p_wilcoxon)
        leaderboard.append({"name": name, "summary": summ, "compare": comp})

    # -- error taxonomy for the baseline --------------------------------
    frames = _synthetic_frames(baseline, sequences, seeds, _ZOO_SCENE)
    switches, background, idsw = _run_frames(frames, baseline)
    conds = [("occlusion", _OCC_THRESH), ("crowding", _CROWD_THRESH), ("motion", _FAST_THRESH)]
    taxonomy = []
    for key, thr in conds:
        p_sw, p_bg = _rate(switches, key, thr), _rate(background, key, thr)
        taxonomy.append({"condition": key, "pct_switch": p_sw, "pct_base": p_bg,
                         "lift": (p_sw / p_bg) if p_bg > 0 else float("nan")})

    meta = {
        "dataset": dataset, "baseline": baseline, "trackers": names,
        "sequences": sequences, "seeds": seeds,
        "runs_per_tracker": len(sequences) * len(seeds),
        "config_hash": exp.config_hash(), "idsw_classified": len(switches),
    }
    return BenchmarkReport(dataset, baseline, _METRICS, leaderboard, taxonomy, meta)


# -- rendering ---------------------------------------------------------------

def _render_markdown(rep: BenchmarkReport) -> str:
    m = rep.meta
    L = [f"# MOT benchmark — {rep.dataset}", "",
         f"- trackers: {', '.join(m['trackers'])}  (baseline: `{rep.baseline}`)",
         f"- {m['runs_per_tracker']} runs/tracker · sequences={m['sequences']} · "
         f"seeds={m['seeds']}", f"- config hash: `{m['config_hash']}`", "",
         "## Leaderboard (mean ± std; Δ vs baseline, Wilcoxon p)", "",
         "| tracker | " + " | ".join(rep.metrics) + " |",
         "|" + "---|" * (len(rep.metrics) + 1)]
    best = {mt: rep.best(mt) for mt in rep.metrics}
    for r in rep.leaderboard:
        cells = []
        for mt in rep.metrics:
            mean, std = r["summary"][mt]
            d, p = r["compare"][mt]
            star = "*" if p < 0.05 else ""
            tag = " 🏆" if best[mt] == r["name"] else ""
            base = r["name"] == rep.baseline
            cells.append(f"{mean:.3f}±{std:.3f}{tag}" if base
                         else f"{mean:.3f} ({d:+.3f}{star}){tag}")
        L.append(f"| {r['name']} | " + " | ".join(cells) + " |")
    L += ["", f"## Why the baseline (`{rep.baseline}`) swaps identities",
          f"({m['idsw_classified']} ID switches classified)", "",
          "| condition | % of switches | base rate | lift |", "|---|---|---|---|"]
    for t in rep.taxonomy:
        L.append(f"| {t['condition']} | {t['pct_switch']:.1%} | {t['pct_base']:.1%} "
                 f"| {t['lift']:.2f}× |")
    L += ["", "Lift > 1 = switches over-represented in that condition — the failure "
          "mode to attack. 🏆 marks the best tracker per metric."]
    return "\n".join(L)


def _render_html(rep: BenchmarkReport) -> str:
    from experiments._benchmark_html import render_html
    return render_html(rep)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the MOT benchmarking tool")
    parser.add_argument("--dataset", default="synthetic", choices=["synthetic"])
    parser.add_argument("--trackers", default=None,
                        help="comma-separated preset names (default: all)")
    parser.add_argument("--baseline", default="bytetrack")
    parser.add_argument("--out-md", default=None)
    parser.add_argument("--out-html", default=None)
    args = parser.parse_args(argv)

    names = args.trackers.split(",") if args.trackers else None
    print(f"benchmarking {args.dataset} …")
    rep = run_benchmark(args.dataset, names, args.baseline)
    print("\n" + rep.to_markdown())
    if args.out_md:
        Path(args.out_md).write_text(rep.to_markdown() + "\n")
        print(f"\nwrote {args.out_md}")
    if args.out_html:
        Path(args.out_html).write_text(rep.to_html())
        print(f"wrote {args.out_html}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
