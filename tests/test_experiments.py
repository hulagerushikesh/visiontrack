"""Smoke tests for the experiment harness (config, runner, matrix, analyze)."""
from experiments.config import ExperimentConfig, VariantSpec
from experiments.runner import evaluate_cell


def _tiny_config():
    return ExperimentConfig(
        name="test",
        dataset="synthetic",
        sequences=[1, 2],
        seeds=[0, 1],
        baseline="baseline",
        metrics=["MOTA", "IDF1", "HOTA"],
        scene={"num_objects": 4, "num_frames": 30},
        variants=[
            VariantSpec("baseline", {}),
            VariantSpec("baseline_copy", {}),
            VariantSpec("no_recovery", {"low_score_thresh": 0.5}),
        ],
    )


def test_config_hash_is_stable_and_sensitive():
    a = _tiny_config()
    b = _tiny_config()
    assert a.config_hash() == b.config_hash()
    c = _tiny_config()
    c.seeds = [0, 1, 2]
    assert c.config_hash() != a.config_hash()


def test_config_yaml_roundtrip(tmp_path):
    cfg = _tiny_config()
    p = tmp_path / "exp.yaml"
    cfg.to_yaml(str(p))
    loaded = ExperimentConfig.from_yaml(str(p))
    assert loaded.config_hash() == cfg.config_hash()
    assert loaded.variant_names() == cfg.variant_names()


def test_evaluate_cell_returns_metrics():
    cfg = _tiny_config()
    m = evaluate_cell(cfg, cfg.variants[0], sequence=1, seed=0)
    for key in ("MOTA", "IDF1", "HOTA"):
        assert key in m
        assert 0.0 <= m[key] <= 1.0


def test_identical_variants_produce_identical_cells():
    """baseline and baseline_copy must give bit-identical metrics on the same
    (sequence, seed) — the foundation of the p=1 baseline-vs-baseline sanity."""
    cfg = _tiny_config()
    base = evaluate_cell(cfg, VariantSpec("baseline", {}), sequence=2, seed=1)
    copy = evaluate_cell(cfg, VariantSpec("baseline_copy", {}), sequence=2, seed=1)
    for k in base:
        assert base[k] == copy[k], k


def test_run_matrix_and_analyze_end_to_end(tmp_path):
    import pandas as pd

    from experiments.analyze import build_report
    from experiments.run_matrix import run

    cfg = _tiny_config()
    df = run(cfg)
    # tidy shape: variants × sequences × seeds rows
    assert len(df) == 3 * 2 * 2
    assert set(["variant", "sequence", "seed", "MOTA", "HOTA"]).issubset(df.columns)

    # round-trip through parquet as the real pipeline does
    pq = tmp_path / "results.parquet"
    df.to_parquet(pq, index=False)
    df2 = pd.read_parquet(pq)

    report = build_report(df2, baseline="baseline")
    assert "Paired comparison" in report
    assert "PASS" in report  # baseline-vs-baseline sanity holds


def test_baseline_vs_baseline_is_not_significant():
    from experiments.analyze import _paired
    from experiments.run_matrix import run
    from visiontrack.eval.stats import compare

    cfg = _tiny_config()
    df = run(cfg)
    # baseline_copy is identical to baseline -> zero difference, p=1. This is
    # the foundational sanity: the harness must report "no effect" for a null
    # comparison. (Whether a real ablation *moves* a metric is scene-dependent
    # and is exercised on the harder default sweep, not asserted here.)
    a, b = _paired(df, "baseline_copy", "baseline", "HOTA")
    c = compare(a, b, seed=0)
    assert c.delta == 0.0
    assert c.p_wilcoxon == 1.0
    assert c.ci_low == 0.0 and c.ci_high == 0.0
