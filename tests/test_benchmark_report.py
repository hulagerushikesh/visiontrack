"""Contract tests for structured benchmark-report export."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from experiments.benchmark import BenchmarkReport
from visiontrack.benchmark_report import BenchmarkReportRecord, BenchmarkValue

_FIXTURE = Path("tests/fixtures/benchmark_report_v1.json")


def _structured_result() -> BenchmarkReport:
    """Small structured result; no rendered Markdown or HTML is involved."""
    return BenchmarkReport(
        dataset="synthetic",
        baseline="bytetrack",
        metrics=["MOTA", "IDSW"],
        leaderboard=[
            {
                "name": "bytetrack",
                "summary": {"MOTA": (0.7, 0.02), "IDSW": (8.0, 1.0)},
                "compare": {"MOTA": (0.0, 1.0), "IDSW": (0.0, 1.0)},
            },
            {
                "name": "candidate",
                "summary": {"MOTA": (0.73, 0.01), "IDSW": (6.5, 0.5)},
                "compare": {"MOTA": (0.03, 0.03125), "IDSW": (-1.5, 0.125)},
            },
        ],
        meta={
            "sequences": [1],
            "seeds": [0, 1],
            "runs_per_tracker": 2,
            "config_hash": "abcdef123456",
        },
    )


def test_structured_result_matches_shared_browser_fixture() -> None:
    record = _structured_result().to_browser_report()
    expected = json.loads(_FIXTURE.read_text(encoding="utf-8"))

    assert isinstance(record, BenchmarkReportRecord)
    assert json.loads(record.to_json()) == expected
    expected_canonical = json.dumps(
        expected, allow_nan=False, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    )
    assert record.to_bytes() == (expected_canonical + "\n").encode("utf-8")


def test_export_preserves_full_paired_statistics() -> None:
    record = _structured_result().to_browser_report()
    candidate = next(variant for variant in record.variants if variant.name == "candidate")

    assert candidate.values["MOTA"].std == 0.01
    assert candidate.values["MOTA"].p_value == 0.03125
    assert candidate.values["MOTA"].significant is True
    assert candidate.values["IDSW"].delta == -1.5


def test_benchmark_value_rejects_inconsistent_significance() -> None:
    with pytest.raises(ValueError, match="must match"):
        BenchmarkValue(mean=0.5, std=0.1, delta=0.1, p_value=0.2, significant=True)


def test_export_rejects_non_provenance_config_hash() -> None:
    result = _structured_result()
    result.meta["config_hash"] = "synthetic"

    with pytest.raises(ValueError, match="config_hash"):
        result.to_browser_report()
