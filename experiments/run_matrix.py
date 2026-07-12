"""Run an experiment sweep and write a tidy results table.

Every (variant × sequence × seed) cell is evaluated and emitted as one row of a
long-format DataFrame, serialized to parquet. That tidy table is the durable
artifact the analysis step (``analyze.py``) consumes — one row per run, so any
grouping / pairing / significance test can be recomputed without re-running the
tracker.

    python -m experiments.run_matrix --config experiments/configs/synth_baseline.yaml
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Support both `python -m experiments.run_matrix` and `python experiments/run_matrix.py`.
_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(_ROOT), str(_ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from experiments.config import ExperimentConfig, VariantSpec  # noqa: E402
from experiments.runner import evaluate_cell  # noqa: E402

_ID_COLS = ["experiment", "config_hash", "variant", "dataset", "sequence", "seed"]


def default_config() -> ExperimentConfig:
    """A small, fast synthetic sweep that exercises the whole harness.

    Includes ``baseline_copy`` (identical to ``baseline``) so analysis shows the
    baseline-vs-baseline sanity (p≈1), plus two real ablations that should move
    the metrics.
    """
    return ExperimentConfig(
        name="synth_baseline",
        dataset="synthetic",
        sequences=[1, 2, 3],
        seeds=[0, 1, 2, 3, 4],
        baseline="baseline",
        metrics=["MOTA", "IDF1", "HOTA", "IDSW"],
        scene={"num_objects": 8, "num_frames": 80, "occlusion_iou": 0.35,
               "false_positive_rate": 0.5},
        variants=[
            VariantSpec("baseline", {}),
            VariantSpec("baseline_copy", {}),
            VariantSpec("no_recovery", {"low_score_thresh": 0.5}),
            VariantSpec("no_gating", {"use_mahalanobis_gating": False}),
        ],
    )


def run(exp: ExperimentConfig):
    import pandas as pd

    chash = exp.config_hash()
    total = len(exp.variants) * len(exp.sequences) * len(exp.seeds)
    rows = []
    i = 0
    for variant in exp.variants:
        for sequence in exp.sequences:
            for seed in exp.seeds:
                i += 1
                metrics = evaluate_cell(exp, variant, sequence, seed)
                row = {
                    "experiment": exp.name,
                    "config_hash": chash,
                    "variant": variant.name,
                    "dataset": exp.dataset,
                    "sequence": sequence,
                    "seed": seed,
                }
                row.update({k: metrics.get(k) for k in exp.metrics})
                rows.append(row)
                shown = " ".join(
                    f"{k}={metrics.get(k):.3f}"
                    for k in exp.metrics
                    if isinstance(metrics.get(k), (int, float))
                )
                print(f"[{i:>3}/{total}] {variant.name:<14} seq={sequence} seed={seed}  {shown}")
    return pd.DataFrame(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run an experiment sweep")
    parser.add_argument("--config", default=None, help="experiment YAML (default: synth sweep)")
    parser.add_argument("--out", default="results.parquet", help="output parquet path")
    args = parser.parse_args(argv)

    exp = ExperimentConfig.from_yaml(args.config) if args.config else default_config()
    print(f"experiment '{exp.name}'  dataset={exp.dataset}  config_hash={exp.config_hash()}")
    print(f"variants={exp.variant_names()}  sequences={exp.sequences}  seeds={exp.seeds}\n")

    df = run(exp)
    out = Path(args.out)
    df.to_parquet(out, index=False)
    print(f"\nwrote {len(df)} rows -> {out}")
    print(f"next: python -m experiments.analyze --results {out} --baseline {exp.baseline}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
