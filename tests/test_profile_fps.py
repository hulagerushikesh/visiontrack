"""Tests for the throughput profiler (experiments/profile_fps.py)."""
from __future__ import annotations

from experiments.profile_fps import profile_load, report


def test_profile_load_returns_positive_fps():
    r = profile_load(num_objects=8, num_frames=20, warmup=2)
    assert r["objects"] == 8
    assert r["fps"] > 0
    assert r["mean_ms"] > 0
    assert r["p95_ms"] >= r["median_ms"] - 1e-9


def test_more_objects_cost_more_time():
    small = profile_load(num_objects=3, num_frames=30, warmup=3)
    big = profile_load(num_objects=30, num_frames=30, warmup=3)
    assert big["mean_ms"] > small["mean_ms"]  # monotone-ish load scaling


def test_report_renders_table():
    rows = [profile_load(4, 10, warmup=1)]
    text = report(rows)
    assert "FPS" in text and "objects" in text
