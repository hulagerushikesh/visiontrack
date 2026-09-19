"""Reliability Lab summaries report evidence without inventing quality claims."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from visiontrack.lab import (
    DetectionRecord,
    ExperimentManifest,
    SourceManifest,
    create_comparison_summary,
    create_experiment_bundle,
    detection_payload_sha256,
    run_comparison,
    sha256_json,
)

NOW = "2026-09-19T14:00:00Z"


def make_completed_bundle(tmp_path: Path) -> Path:
    detections = [
        DetectionRecord(frame, None, 0, (10 + frame, 10, 30 + frame, 50), 0.95, 1)
        for frame in range(4)
    ]
    source = SourceManifest.create(
        kind="synthetic",
        name="comparison-fixture",
        detection_sha256=detection_payload_sha256(detections, frame_count=4),
        ground_truth_sha256=None,
        video_sha256=None,
        detector={"name": "fixture"},
        frame_count=4,
        width=100,
        height=80,
        fps=30.0,
        coordinate_space="pixel_xyxy",
        created_at=NOW,
    )
    experiment = ExperimentManifest.create(
        source_id=source.source_id,
        baseline="baseline",
        variants=(
            {"name": "baseline", "overrides": {"n_init": 2}},
            {"name": "patient", "overrides": {"n_init": 2, "max_age": 60}},
        ),
        metrics=("HOTA", "IDF1"),
        frame_range={"start": 0, "end": 4},
        visiontrack_version="0.2.0",
        git_revision="648b358",
        environment={"python": "3.12"},
        created_at=NOW,
    )
    bundle = create_experiment_bundle(tmp_path, experiment, source, detections)
    run_comparison(bundle)
    return bundle


def test_summary_reports_diagnostics_deltas_and_no_automatic_winner(
    tmp_path: Path,
) -> None:
    bundle = make_completed_bundle(tmp_path)
    summary = create_comparison_summary(bundle)

    assert summary["baseline"] == "baseline"
    assert summary["requested_metrics"] == ["HOTA", "IDF1"]
    assert summary["diagnostics"]["baseline"] == {
        "observation_count": 3,
        "unique_track_count": 1,
        "active_frame_count": 3,
        "active_frame_fraction": 0.75,
        "first_active_frame": 1,
        "last_active_frame": 3,
    }
    assert summary["deltas_vs_baseline"]["baseline"] == {
        "observation_count": 0,
        "unique_track_count": 0,
        "active_frame_count": 0,
        "active_frame_fraction": 0.0,
    }
    assert summary["deltas_vs_baseline"]["patient"] == summary["deltas_vs_baseline"][
        "baseline"
    ]
    assert summary["decision"] == {
        "status": "not_selected",
        "accepted_variant": None,
        "reason": "diagnostic_counts_are_not_tracking_quality_metrics",
    }


def test_no_ground_truth_is_explicitly_insufficient_for_quality_metrics(
    tmp_path: Path,
) -> None:
    summary = create_comparison_summary(make_completed_bundle(tmp_path))
    assert summary["evidence"]["ground_truth_status"] == "absent"
    unavailable = {item["metric"]: item for item in summary["insufficient_evidence"]}
    assert set(unavailable) == {
        "HOTA",
        "IDF1",
        "MOTA",
        "identity_switches",
        "fragmentation",
    }
    assert all(item["status"] == "insufficient_evidence" for item in unavailable.values())
    assert all(item["reason"] == "ground_truth_absent" for item in unavailable.values())


def test_summary_is_content_addressed_and_idempotent(tmp_path: Path) -> None:
    bundle = make_completed_bundle(tmp_path)
    first = create_comparison_summary(bundle)
    stored = (bundle / "comparison.json").read_bytes()
    content = dict(first)
    comparison_id = content.pop("comparison_id")
    assert comparison_id == sha256_json(content)

    second = create_comparison_summary(bundle)
    assert second == first
    assert (bundle / "comparison.json").read_bytes() == stored


def test_summary_refuses_conflicting_existing_comparison(tmp_path: Path) -> None:
    bundle = make_completed_bundle(tmp_path)
    create_comparison_summary(bundle)
    (bundle / "comparison.json").write_text("{}\n", encoding="utf-8")
    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        create_comparison_summary(bundle)


def test_summary_rejects_corrupt_run_metadata_or_track_payload(tmp_path: Path) -> None:
    metadata_bundle = make_completed_bundle(tmp_path / "metadata")
    run_path = metadata_bundle / "runs/baseline/run.json"
    metadata = json.loads(run_path.read_text())
    metadata["observation_count"] += 1
    run_path.write_text(json.dumps(metadata), encoding="utf-8")
    with pytest.raises(ValueError, match="run_id"):
        create_comparison_summary(metadata_bundle)

    track_bundle = make_completed_bundle(tmp_path / "tracks")
    with (track_bundle / "runs/baseline/tracks.jsonl").open("ab") as stream:
        stream.write(b" ")
    with pytest.raises(ValueError, match="SHA-256"):
        create_comparison_summary(track_bundle)


def test_summary_requires_every_declared_variant_result(tmp_path: Path) -> None:
    bundle = make_completed_bundle(tmp_path)
    missing = bundle / "runs/patient/run.json"
    missing.unlink()
    with pytest.raises(ValueError, match="cannot read run metadata"):
        create_comparison_summary(bundle)
