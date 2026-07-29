"""Tests for the Horizon-3 benchmarking tool (experiments/benchmark.py)."""
from __future__ import annotations

import pytest

from experiments.benchmark import BenchmarkReport, run_benchmark


@pytest.fixture(scope="module")
def report():
    # Tiny but real end-to-end run (kept small for test speed).
    return run_benchmark("synthetic", ["sort", "bytetrack", "bytetrack_reid"],
                         "bytetrack", sequences=[1], seeds=[0, 1])


def test_report_structure(report):
    assert isinstance(report, BenchmarkReport)
    names = [r["name"] for r in report.leaderboard]
    assert names == ["sort", "bytetrack", "bytetrack_reid"]
    # every tracker has a summary + comparison for every metric
    for r in report.leaderboard:
        for m in report.metrics:
            assert m in r["summary"] and m in r["compare"]


def test_baseline_delta_is_zero(report):
    base = next(r for r in report.leaderboard if r["name"] == "bytetrack")
    for m in report.metrics:
        delta, p = base["compare"][m]
        assert abs(delta) < 1e-9
        assert p >= 0.999  # baseline vs itself


def test_taxonomy_has_three_conditions(report):
    conds = [t["condition"] for t in report.taxonomy]
    assert conds == ["occlusion", "crowding", "motion"]
    for t in report.taxonomy:
        assert 0.0 <= t["pct_switch"] <= 1.0


def test_best_is_direction_aware(report):
    # For IDSW lower is better; best() must not just take the max.
    idsw = {r["name"]: r["summary"]["IDSW"][0] for r in report.leaderboard}
    assert report.best("IDSW") == min(idsw, key=idsw.get)
    hota = {r["name"]: r["summary"]["HOTA"][0] for r in report.leaderboard}
    assert report.best("HOTA") == max(hota, key=hota.get)


def test_renders_markdown_and_html(report):
    md = report.to_markdown()
    assert "Leaderboard" in md and "lift" in md.lower()
    h = report.to_html()
    assert h.startswith("<!doctype html>")
    assert "<table>" in h and "config" in h


def test_metadata_present(report):
    m = report.meta
    assert m["baseline"] == "bytetrack"
    assert m["runs_per_tracker"] == 2  # 1 seq * 2 seeds
    assert len(m["config_hash"]) == 12
