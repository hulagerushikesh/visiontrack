"""Statistical rigor for tracking experiments.

Single-run metric numbers are not evidence. This module turns a set of
per-configuration runs (over seeds and sequences) into the machinery a reviewer
expects:

* **summaries** — mean ± std, standard error and a 95% confidence interval;
* **paired comparisons** — because two variants are evaluated on the *same*
  sequences and seeds, their metrics are paired, and a paired test is far more
  powerful than an unpaired one. We provide both a **paired bootstrap** (which
  makes no distributional assumption) and the non-parametric **Wilcoxon
  signed-rank** test, plus a **Cohen's d** effect size so significance is never
  reported without magnitude.

Everything is reproducible (bootstrap resampling is seeded) and depends only on
NumPy, with SciPy imported lazily only for the Wilcoxon test. Nothing here is
imported by ``core``.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

__all__ = ["Summary", "Comparison", "summarize", "paired_bootstrap", "wilcoxon_pvalue",
           "cohens_d_paired", "compare"]

_Z95 = 1.959963984540054  # standard-normal 97.5th percentile


@dataclass(slots=True)
class Summary:
    """Descriptive statistics for one metric across runs."""

    mean: float
    std: float
    sem: float
    n: int
    ci_low: float
    ci_high: float

    def __str__(self) -> str:  # pragma: no cover - presentation
        return f"{self.mean:.3f}±{self.std:.3f}"


def summarize(values) -> Summary:
    """Mean ± std, SEM and a 95% normal-approx CI for a set of values."""
    x = np.asarray(values, dtype=np.float64).ravel()
    n = int(x.size)
    if n == 0:
        return Summary(0.0, 0.0, 0.0, 0, 0.0, 0.0)
    mean = float(x.mean())
    std = float(x.std(ddof=1)) if n > 1 else 0.0
    sem = std / np.sqrt(n) if n > 0 else 0.0
    half = _Z95 * sem
    return Summary(mean, std, sem, n, mean - half, mean + half)


@dataclass(slots=True)
class Comparison:
    """Result of a paired comparison of variant ``a`` against baseline ``b``."""

    delta: float          # mean(a - b); positive => a is higher
    ci_low: float
    ci_high: float
    p_bootstrap: float
    p_wilcoxon: float
    cohens_d: float
    n: int

    @property
    def significant(self) -> bool:
        """Two-sided significance at α=0.05 by the Wilcoxon test."""
        return self.p_wilcoxon < 0.05

    def as_dict(self) -> dict[str, float]:
        return {
            "delta": round(self.delta, 4),
            "ci_low": round(self.ci_low, 4),
            "ci_high": round(self.ci_high, 4),
            "p_bootstrap": round(self.p_bootstrap, 4),
            "p_wilcoxon": round(self.p_wilcoxon, 4),
            "cohens_d": round(self.cohens_d, 4),
            "n": self.n,
        }


def paired_bootstrap(
    a, b, n_resamples: int = 10000, seed: int = 0
) -> tuple[float, float, float, float]:
    """Paired bootstrap of the mean difference ``a - b``.

    Returns ``(delta, ci_low, ci_high, p_value)`` where the CI is the 95%
    percentile interval of the resampled mean difference and the two-sided
    p-value is ``2·min(P(mean≤0), P(mean≥0))``. Identical inputs yield
    ``delta=0`` and ``p=1``.
    """
    a = np.asarray(a, dtype=np.float64).ravel()
    b = np.asarray(b, dtype=np.float64).ravel()
    if a.shape != b.shape:
        raise ValueError("paired inputs must have the same shape")
    d = a - b
    n = d.size
    if n == 0:
        return 0.0, 0.0, 0.0, 1.0
    delta = float(d.mean())
    if np.allclose(d, 0.0):
        return 0.0, 0.0, 0.0, 1.0

    rng = np.random.default_rng(seed)
    idx = rng.integers(0, n, size=(n_resamples, n))
    boot = d[idx].mean(axis=1)
    ci_low, ci_high = np.percentile(boot, [2.5, 97.5])
    p = 2.0 * min(float((boot <= 0).mean()), float((boot >= 0).mean()))
    return delta, float(ci_low), float(ci_high), min(1.0, p)


def wilcoxon_pvalue(a, b) -> float:
    """Two-sided Wilcoxon signed-rank p-value for paired samples.

    Returns ``1.0`` when the samples are identical (no difference to test) or
    when the test is undefined (e.g. all differences zero, too few pairs).
    """
    a = np.asarray(a, dtype=np.float64).ravel()
    b = np.asarray(b, dtype=np.float64).ravel()
    d = a - b
    if d.size == 0 or np.allclose(d, 0.0):
        return 1.0
    from scipy.stats import wilcoxon  # lazy: SciPy only needed here

    try:
        return float(wilcoxon(a, b).pvalue)
    except ValueError:
        return 1.0


def cohens_d_paired(a, b) -> float:
    """Cohen's d for paired samples: mean difference over its std."""
    a = np.asarray(a, dtype=np.float64).ravel()
    b = np.asarray(b, dtype=np.float64).ravel()
    d = a - b
    if d.size < 2:
        return 0.0
    sd = d.std(ddof=1)
    return float(d.mean() / sd) if sd > 0 else 0.0


def compare(a, b, n_resamples: int = 10000, seed: int = 0) -> Comparison:
    """Full paired comparison of ``a`` vs ``b`` (bootstrap + Wilcoxon + effect)."""
    delta, ci_low, ci_high, p_boot = paired_bootstrap(a, b, n_resamples, seed)
    return Comparison(
        delta=delta,
        ci_low=ci_low,
        ci_high=ci_high,
        p_bootstrap=p_boot,
        p_wilcoxon=wilcoxon_pvalue(a, b),
        cohens_d=cohens_d_paired(a, b),
        n=int(np.asarray(a).size),
    )
