# Phase 1 — Statistical-rigor harness (runbook)

Goal: stop reporting single numbers. Every result becomes **mean ± std over
seeds** with a **paired significance test**, so a claimed improvement is
defensible and a null result is provably null.

## What shipped

| Piece | Where | Role |
|-------|-------|------|
| Statistics library | [`eval/stats.py`](../src/visiontrack/eval/stats.py) | `summarize` (mean/std/SEM/CI), `paired_bootstrap`, `wilcoxon_pvalue`, `cohens_d_paired`, `compare` |
| Experiment config | [`experiments/config.py`](../experiments/config.py) | typed dataclass + YAML + **content hash** (a run is specified by its hash) |
| Cell runner | [`experiments/runner.py`](../experiments/runner.py) | `(variant, sequence, seed) → metrics`; synthetic + MOT17 |
| Sweep matrix | [`experiments/run_matrix.py`](../experiments/run_matrix.py) | runs all cells → tidy `results.parquet` (one row per run) |
| Analysis | [`experiments/analyze.py`](../experiments/analyze.py) | mean±std tables + paired p-values (+ optional bar figure) |
| Configs | [`experiments/configs/`](../experiments/configs) | `synth_baseline.yaml`, `mot17_frcnn.yaml` |

## Run it

```bash
pip install -e ".[experiments]"     # pandas, pyarrow, scipy, pyyaml, matplotlib

# 1. run the sweep -> tidy parquet (one row per variant×sequence×seed)
python -m experiments.run_matrix --config experiments/configs/synth_baseline.yaml --out results.parquet

# 2. analyze -> mean±std tables + paired significance, optional figure
python -m experiments.analyze --results results.parquet --baseline baseline \
    --out-md report.md --out-fig hota_by_variant.png --fig-metric HOTA
```

No config runs a built-in synthetic sweep. For real data, use
`experiments/configs/mot17_frcnn.yaml` (needs the Phase 0 cache).

## Acceptance (met)

`run_matrix.py` writes `results.parquet`; `analyze.py` emits a markdown table
with `mean±std` and a **p-value column**, and the baseline-vs-baseline sanity
holds (`p≈1`). Actual output on the synthetic sweep (15 runs/variant):

```
| variant       | MOTA Δ (p)      | IDF1 Δ (p)      | HOTA Δ (p)      |
| baseline      | +0.000 (p=1.00) | +0.000 (p=1.00) | +0.000 (p=1.00) |
| baseline_copy | +0.000 (p=1.00) | +0.000 (p=1.00) | +0.000 (p=1.00) |  <- null sanity
| no_recovery   | -0.003 (p=0.04*)| -0.002 (p=0.04*)| -0.002 (p=0.04*)|
| no_gating     | +0.002 (p=0.03*)| +0.001 (p=0.03*)| +0.002 (p=0.03*)|
```

Two things this demonstrates: the harness reports **p=1 for a null comparison**
(baseline vs itself and vs an identical copy), and the **paired** test detects
even small but *consistent* ablation effects that an unpaired test over such
high-variance scenes would miss.

## Design decisions

- **Pairing is the point.** Variants are scored on the *same* (sequence, seed)
  scenes, so metrics are paired; the paired bootstrap / Wilcoxon test is far
  more powerful than comparing two independent means. `analyze.py` pairs cells
  by `(sequence, seed)` before every test.
- **No Hydra/OmegaConf.** The plan suggested them, but a dataclass + PyYAML + a
  canonical SHA-256 delivers the same "a run is fully specified by its config
  hash" property (`ExperimentConfig.config_hash()`) without adopting a heavy,
  opinionated application framework. Fewer deps, nothing in `core`.
- **Reproducible.** Bootstrap resampling is seeded; synthetic scenes are
  deterministic in `(sequence, seed)`; the config hash pins the whole sweep.
- **Deterministic datasets.** On MOT17 the tracker is deterministic given cached
  detections, so `seeds` currently only labels cells — a hook for the
  stochastic components introduced later (RQ3's injected detector noise).

## Notes / limitations

- Heavy deps (`pandas`, `pyarrow`, `scipy`, `matplotlib`) live in the
  `[experiments]` extra and are lazily imported; the core package still needs
  only NumPy.
- The synthetic ablation effects are small because the default scene is easy;
  the harness is validated to *discriminate* (significant p) and to report
  *null* correctly. Larger/harder sweeps simply change the inputs, not the
  machinery.
