"""Reliability Lab failures stay linked to verified metric correspondence."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path

import pytest

from visiontrack.lab import (
    DetectionRecord,
    ExperimentManifest,
    FailureEvent,
    GroundTruthRecord,
    SourceManifest,
    TrackObservationRecord,
    calculate_bundle_metrics,
    calculate_failure_events,
    create_comparison_summary,
    create_experiment_bundle,
    create_variant_run,
    detection_payload_sha256,
    ground_truth_payload_sha256,
    resolve_variant_config,
    serialize_track_jsonl,
    sha256_json,
)

NOW = "2026-09-19T20:00:00Z"


def _run_metadata(experiment, source, variant, tracks):
    config = asdict(resolve_variant_config(variant))
    track_sha256 = hashlib.sha256(
        serialize_track_jsonl(tracks, frame_count=source.frame_count)
    ).hexdigest()
    content = {
        "schema_version": 1,
        "experiment_id": experiment.experiment_id,
        "source_id": source.source_id,
        "variant": variant["name"],
        "config": config,
        "config_sha256": sha256_json(config),
        "detection_sha256": source.detection_sha256,
        "frame_range": experiment.frame_range,
        "track_sha256": track_sha256,
        "observation_count": len(tracks),
    }
    content["run_id"] = sha256_json(content)
    return content


def make_failure_bundle(tmp_path: Path, *, variants: int = 2) -> Path:
    detections = [
        DetectionRecord(frame, None, 0, (10, 10, 30, 50), 0.95, 1)
        for frame in range(3)
    ]
    ground_truth = [
        GroundTruthRecord(frame, frame, 1, (10, 10, 30, 50), 1, 1.0, False)
        for frame in range(3)
    ]
    # This distractor and its overlapping hypothesis must disappear during the
    # exact same MOT preprocessing used by the metric artifact.
    ground_truth.append(
        GroundTruthRecord(0, 0, 2, (60, 10, 80, 50), 7, 1.0, False)
    )
    source = SourceManifest.create(
        kind="mot",
        name="failure-fixture",
        detection_sha256=detection_payload_sha256(detections, frame_count=3),
        ground_truth_sha256=ground_truth_payload_sha256(ground_truth, frame_count=3),
        video_sha256=None,
        detector={"name": "fixture"},
        frame_count=3,
        width=100,
        height=80,
        fps=30.0,
        coordinate_space="pixel_xyxy",
        created_at=NOW,
    )
    declared = (
        {"name": "baseline", "overrides": {"n_init": 2}},
        {"name": "patient", "overrides": {"n_init": 2, "max_age": 60}},
    )[:variants]
    experiment = ExperimentManifest.create(
        source_id=source.source_id,
        baseline="baseline",
        variants=declared,
        metrics=("HOTA", "IDF1", "MOTA", "IDSW", "Frag"),
        frame_range={"start": 0, "end": 3},
        visiontrack_version="0.2.0",
        git_revision="failure-test",
        environment={"python": "3.12"},
        created_at=NOW,
    )
    bundle = create_experiment_bundle(
        tmp_path, experiment, source, detections, ground_truth
    )
    tracks = [
        TrackObservationRecord(0, 10, (10, 10, 30, 50), 0.95, 1),
        TrackObservationRecord(0, 88, (60, 10, 80, 50), 0.95, 1),
        TrackObservationRecord(1, 20, (10, 10, 30, 50), 0.95, 1),
        TrackObservationRecord(2, 99, (70, 10, 90, 50), 0.95, 1),
    ]
    for variant in declared:
        create_variant_run(
            bundle,
            variant["name"],
            _run_metadata(experiment, source, variant, tracks),
            tracks,
            frame_count=source.frame_count,
        )
    calculate_bundle_metrics(bundle)
    return bundle


def test_failure_extraction_uses_metric_correspondence_and_evidence_links(
    tmp_path: Path,
) -> None:
    bundle = make_failure_bundle(tmp_path, variants=1)
    results = calculate_failure_events(bundle)
    events = results["baseline"]

    assert [event.event_type for event in events] == [
        "id_switch",
        "fragmentation",
        "miss",
        "false_positive",
    ]
    assert [event.frame_index for event in events] == [1, 2, 2, 2]
    assert events[0].track_ids == (10, 20)
    assert events[1].track_ids == (20,)
    assert events[2].ground_truth_ids == (1,)
    assert events[3].track_ids == (99,)
    assert all(88 not in event.track_ids for event in events)
    assert all(
        event.evidence_frames["start"] <= event.frame_index
        < event.evidence_frames["end"]
        for event in events
    )

    metric = json.loads((bundle / "runs/baseline/metrics.json").read_text())
    run = json.loads((bundle / "runs/baseline/run.json").read_text())
    for event in events:
        assert event.run_id == run["run_id"]
        assert event.context["metric_id"] == metric["metric_id"]
        assert event.context["track_sha256"] == run["track_sha256"]
        assert event.event_id == event.derive_event_id()


def test_failure_artifacts_are_idempotent_and_feed_diagnostic_summary(
    tmp_path: Path,
) -> None:
    bundle = make_failure_bundle(tmp_path)
    first = calculate_failure_events(bundle)
    stored = (bundle / "runs/baseline/failures.jsonl").read_bytes()
    assert calculate_failure_events(bundle) == first
    assert (bundle / "runs/baseline/failures.jsonl").read_bytes() == stored

    summary = create_comparison_summary(bundle)
    expected_counts = {
        "id_switch": 1,
        "fragmentation": 1,
        "miss": 1,
        "false_positive": 1,
    }
    assert summary["failure_counts"] == {
        "baseline": expected_counts,
        "patient": expected_counts,
    }
    assert summary["failure_sets"]["baseline"]["event_count"] == 4
    assert summary["failure_sets"]["baseline"]["metric_id"]
    assert summary["decision"]["accepted_variant"] is None

    with pytest.raises(ValueError, match="already seals"):
        calculate_failure_events(bundle)


def test_summary_rejects_partial_or_corrupt_failure_evidence(tmp_path: Path) -> None:
    partial = make_failure_bundle(tmp_path / "partial")
    calculate_failure_events(partial)
    (partial / "runs/patient/failures.jsonl").unlink()
    with pytest.raises(ValueError, match="every declared variant"):
        create_comparison_summary(partial)

    corrupt = make_failure_bundle(tmp_path / "corrupt", variants=1)
    calculate_failure_events(corrupt)
    path = corrupt / "runs/baseline/failures.jsonl"
    lines = path.read_text().splitlines()
    event = json.loads(lines[0])
    event["context"]["track_sha256"] = "0" * 64
    lines[0] = json.dumps(event, separators=(",", ":"), sort_keys=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="event_id"):
        create_comparison_summary(corrupt)


def test_failure_contract_rejects_non_content_addressed_event() -> None:
    event = FailureEvent.create(
        run_id="1" * 64,
        frame_index=3,
        event_type="miss",
        track_ids=(),
        ground_truth_ids=(4,),
        context={"metric_id": "2" * 64},
        evidence_frames={"start": 1, "end": 5},
    )
    data = event.to_dict()
    data["event_id"] = "0" * 64
    with pytest.raises(ValueError, match="does not match"):
        FailureEvent.from_dict(data)
