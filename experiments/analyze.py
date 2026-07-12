"""Turn a results table into mean±std tables with paired significance tests.

Consumes the tidy parquet from ``run_matrix.py`` and emits a markdown report:

1. **Summary** — each variant's metrics as ``mean±std`` over all runs.
2. **Paired comparison vs baseline** — for every variant and metric, the mean
   difference from the baseline with its Wilcoxon signed-rank p-value and
   Cohen's d effect size. Because variants share sequences and seeds, cells are
   paired by ``(sequence, seed)`` before testing.

The baseline-vs-itself row is the sanity check: identical runs ⇒ Δ=0, p=1.

    python -m experiments.analyze --results results.parquet --baseline baseline
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(_ROOT), str(_ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from visiontrack.eval.stats import compare, summarize  # noqa: E402

_ID_COLS = {"experiment", "config_hash", "variant", "dataset", "sequence", "seed"}


def _metric_columns(df) -> list[str]:
    return [c for c in df.columns if c not in _ID_COLS]


def _paired(df, variant: str, baseline: str, metric: str):
    v = df[df.variant == variant].set_index(["sequence", "seed"])[metric].sort_index()
    b = df[df.variant == baseline].set_index(["sequence", "seed"])[metric].sort_index()
    idx = v.index.intersection(b.index)
    return v.loc[idx].to_numpy(dtype=float), b.loc[idx].to_numpy(dtype=float)


def build_report(df, baseline: str, metrics: list[str] | None = None) -> str:
    variants = list(dict.fromkeys(df["variant"].tolist()))
    metrics = metrics or _metric_columns(df)
    if baseline not in variants:
        baseline = variants[0]

    lines: list[str] = []
    exp_name = df["experiment"].iloc[0] if "experiment" in df else "experiment"
    chash = df["config_hash"].iloc[0] if "config_hash" in df else "?"
    n_runs = len(df[df.variant == baseline])
    lines.append(f"# Experiment report: {exp_name}")
    lines.append("")
    lines.append(f"- config hash: `{chash}`")
    lines.append(f"- variants: {', '.join(variants)}")
    lines.append(f"- runs per variant: {n_runs}  (baseline: `{baseline}`)")
    lines.append("")

    # -- Table 1: summary mean±std ---------------------------------------
    lines.append("## Summary (mean ± std)")
    lines.append("")
    header = "| variant | " + " | ".join(metrics) + " |"
    sep = "|" + "---|" * (len(metrics) + 1)
    lines.append(header)
    lines.append(sep)
    for var in variants:
        cells = []
        for m in metrics:
            s = summarize(df[df.variant == var][m].to_numpy(dtype=float))
            cells.append(f"{s.mean:.3f}±{s.std:.3f}")
        lines.append(f"| {var} | " + " | ".join(cells) + " |")
    lines.append("")

    # -- Table 2: paired comparison vs baseline --------------------------
    lines.append(f"## Paired comparison vs `{baseline}`  (Δ, Wilcoxon p, Cohen's d)")
    lines.append("")
    lines.append("Δ = variant − baseline, paired by (sequence, seed). "
                 "`*` marks p < 0.05.")
    lines.append("")
    header = "| variant | " + " | ".join(f"{m} Δ (p)" for m in metrics) + " |"
    sep = "|" + "---|" * (len(metrics) + 1)
    lines.append(header)
    lines.append(sep)
    for var in variants:
        cells = []
        for m in metrics:
            a, b = _paired(df, var, baseline, m)
            c = compare(a, b, seed=0)
            star = "*" if c.p_wilcoxon < 0.05 else ""
            cells.append(f"{c.delta:+.3f} (p={c.p_wilcoxon:.2f}{star})")
        lines.append(f"| {var} | " + " | ".join(cells) + " |")
    lines.append("")

    # -- Sanity note ------------------------------------------------------
    lines.append("### Sanity")
    a, b = _paired(df, baseline, baseline, metrics[0])
    c = compare(a, b, seed=0)
    lines.append(
        f"- baseline vs baseline on {metrics[0]}: Δ={c.delta:+.3f}, "
        f"p={c.p_wilcoxon:.3f} (expected Δ=0, p=1) — "
        + ("PASS" if abs(c.delta) < 1e-9 and c.p_wilcoxon >= 0.999 else "CHECK")
    )
    return "\n".join(lines)


def save_figure(df, baseline: str, metric: str, path: str) -> str:
    """Bar chart of ``metric`` per variant with std error bars (needs matplotlib)."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    variants = list(dict.fromkeys(df["variant"].tolist()))
    means = [summarize(df[df.variant == v][metric].to_numpy(dtype=float)).mean for v in variants]
    stds = [summarize(df[df.variant == v][metric].to_numpy(dtype=float)).std for v in variants]

    fig, ax = plt.subplots(figsize=(6, 4), dpi=110)
    colors = ["#4c9aff" if v == baseline else "#9aa4b2" for v in variants]
    ax.bar(range(len(variants)), means, yerr=stds, capsize=5, color=colors)
    ax.set_xticks(range(len(variants)))
    ax.set_xticklabels(variants, rotation=20, ha="right")
    ax.set_ylabel(f"{metric} (mean ± std)")
    ax.set_title(f"{metric} by variant")
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path


def main(argv: list[str] | None = None) -> int:
    import pandas as pd

    parser = argparse.ArgumentParser(description="Analyze an experiment results table")
    parser.add_argument("--results", default="results.parquet")
    parser.add_argument("--baseline", default="baseline")
    parser.add_argument("--out-md", default=None, help="also write the report to a markdown file")
    parser.add_argument("--out-fig", default=None, help="save a bar-chart figure to this path")
    parser.add_argument("--fig-metric", default=None, help="metric to plot (default: first)")
    args = parser.parse_args(argv)

    df = pd.read_parquet(args.results)
    report = build_report(df, args.baseline)
    print(report)
    if args.out_md:
        Path(args.out_md).write_text(report + "\n")
        print(f"\nwrote report -> {args.out_md}")
    if args.out_fig:
        metric = args.fig_metric or _metric_columns(df)[0]
        save_figure(df, args.baseline, metric, args.out_fig)
        print(f"wrote figure ({metric}) -> {args.out_fig}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
