"""Tests for the statistical-rigor primitives."""
import numpy as np
import pytest

from visiontrack.eval.stats import (
    cohens_d_paired,
    compare,
    paired_bootstrap,
    summarize,
    wilcoxon_pvalue,
)


def test_summarize_basic():
    s = summarize([1.0, 2.0, 3.0, 4.0, 5.0])
    assert s.mean == pytest.approx(3.0)
    assert s.std == pytest.approx(np.std([1, 2, 3, 4, 5], ddof=1))
    assert s.n == 5
    assert s.ci_low < s.mean < s.ci_high


def test_summarize_single_value_has_zero_spread():
    s = summarize([7.0])
    assert s.mean == 7.0 and s.std == 0.0 and s.sem == 0.0


def test_identical_samples_give_p_one():
    a = np.array([0.5, 0.6, 0.7, 0.8])
    delta, lo, hi, p = paired_bootstrap(a, a.copy())
    assert delta == 0.0 and p == 1.0
    assert wilcoxon_pvalue(a, a.copy()) == 1.0


def test_clearly_shifted_samples_are_significant():
    rng = np.random.default_rng(0)
    b = rng.uniform(0.4, 0.6, size=30)
    a = b + 0.2  # a is consistently higher by a clear margin
    delta, lo, hi, p_boot = paired_bootstrap(a, b, seed=1)
    assert delta == pytest.approx(0.2, abs=1e-6)
    assert lo > 0  # 95% CI excludes zero
    assert p_boot < 0.05
    assert wilcoxon_pvalue(a, b) < 0.05


def test_bootstrap_is_reproducible():
    rng = np.random.default_rng(2)
    a = rng.normal(0, 1, 40)
    b = rng.normal(0, 1, 40)
    r1 = paired_bootstrap(a, b, seed=123)
    r2 = paired_bootstrap(a, b, seed=123)
    assert r1 == r2  # same seed -> identical CI and p


def test_cohens_d_sign_and_magnitude():
    b = np.array([0.5, 0.5, 0.5, 0.5, 0.5])
    a = b + 0.1
    # constant +0.1 difference -> zero variance in d -> guarded to 0
    assert cohens_d_paired(a, b) == 0.0
    rng = np.random.default_rng(3)
    b2 = rng.normal(0, 1, 50)
    a2 = b2 + rng.normal(0.5, 0.2, 50)
    d = cohens_d_paired(a2, b2)
    assert d > 0.5  # a2 clearly larger


def test_compare_integration():
    rng = np.random.default_rng(4)
    b = rng.uniform(0.4, 0.7, 25)
    a = b - 0.05  # a slightly worse
    c = compare(a, b, seed=0)
    assert c.delta == pytest.approx(-0.05, abs=1e-6)
    assert c.n == 25
    assert c.cohens_d < 0
    d = c.as_dict()
    assert set(d) >= {"delta", "p_wilcoxon", "p_bootstrap", "cohens_d", "ci_low", "ci_high"}


def test_mismatched_shapes_raise():
    with pytest.raises(ValueError):
        paired_bootstrap(np.zeros(3), np.zeros(4))
