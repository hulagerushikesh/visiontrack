"""Reliability Lab variants replay one verified detection stream."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from visiontrack.lab import (
    DetectionRecord,
    ExperimentManifest,
    SourceManifest,
    create_experiment_bundle,
    detection_payload_sha256,
    load_experiment_bundle,
    read_track_jsonl,
    resolve_variant_config,
    run_comparison,
)

NOW = "2026-09-19T12:00:00Z"


def records() -> list[DetectionRecord]:
    return [
        DetectionRecord(
            frame_index=frame,
            source_frame=None,
            detection_index=0,
            xyxy=(10 + frame, 10, 30 + frame, 50),
            score=0.95,
            class_id=1,
        )
        for frame in range(6)
    ]


def make_bundle(tmp_path: Path) -> tuple[Path, ExperimentManifest, SourceManifest]:
    detection_records = records()
    source = SourceManifest.create(
        kind="synthetic",
        name="linear-object",
        detection_sha256=detection_payload_sha256(detection_records, frame_count=6),
        ground_truth_sha256=None,
        video_sha256=None,
        detector={"name": "fixture"},
        frame_count=6,
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
            {"name": "baseline", "preset": "bytetrack", "overrides": {"n_init": 2}},
            {
                "name": "patient",
                "preset": "bytetrack",
                "overrides": {"n_init": 2, "max_age": 60},
            },
        ),
        metrics=("track_count",),
        frame_range={"start": 2, "end": 6},
        visiontrack_version="0.2.0",
        git_revision="7c7122c",
        environment={"python": "3.12"},
        created_at=NOW,
    )
    return (
        create_experiment_bundle(tmp_path, experiment, source, detection_records),
        experiment,
        source,
    )


def test_bundle_loader_verifies_and_returns_one_immutable_stream(tmp_path: Path) -> None:
    bundle, expected_experiment, expected_source = make_bundle(tmp_path)
    experiment, source, detections = load_experiment_bundle(bundle)
    assert experiment == expected_experiment
    assert source == expected_source
    assert isinstance(detections, tuple)
    assert detections == tuple(records())


def test_comparison_runs_every_variant_on_same_frames_and_persists_results(
    tmp_path: Path,
) -> None:
    bundle, experiment, source = make_bundle(tmp_path)
    input_before = (bundle / "inputs/detections.jsonl").read_bytes()

    results = run_comparison(bundle)

    assert set(results) == {"baseline", "patient"}
    assert results["baseline"] == results["patient"]
    assert results["baseline"]
    assert {record.frame_index for record in results["baseline"]} == {3, 4, 5}
    assert (bundle / "inputs/detections.jsonl").read_bytes() == input_before

    for name, tracks in results.items():
        run_path = bundle / "runs" / name
        metadata = json.loads((run_path / "run.json").read_text())
        assert metadata["experiment_id"] == experiment.experiment_id
        assert metadata["source_id"] == source.source_id
        assert metadata["variant"] == name
        assert metadata["detection_sha256"] == source.detection_sha256
        assert metadata["observation_count"] == len(tracks)
        assert len(metadata["run_id"]) == 64
        assert read_track_jsonl(run_path / "tracks.jsonl", frame_count=6) == list(tracks)


def test_comparison_rerun_is_deterministic_and_idempotent(tmp_path: Path) -> None:
    bundle, _, _ = make_bundle(tmp_path)
    first = run_comparison(bundle)
    run_files = {
        path.relative_to(bundle): path.read_bytes()
        for path in bundle.glob("runs/*/*")
        if path.is_file()
    }
    second = run_comparison(bundle)
    assert second == first
    assert {
        path.relative_to(bundle): path.read_bytes()
        for path in bundle.glob("runs/*/*")
        if path.is_file()
    } == run_files


def test_comparison_refuses_conflicting_existing_result(tmp_path: Path) -> None:
    bundle, _, _ = make_bundle(tmp_path)
    run_comparison(bundle)
    (bundle / "runs/baseline/tracks.jsonl").write_text("", encoding="utf-8")
    with pytest.raises(FileExistsError, match="tracks.jsonl"):
        run_comparison(bundle)


def test_loader_rejects_tampered_input_and_wrong_directory(tmp_path: Path) -> None:
    bundle, _, _ = make_bundle(tmp_path)
    (bundle / "inputs/detections.jsonl").write_bytes(b"corrupt\n")
    with pytest.raises(ValueError, match="SHA-256"):
        load_experiment_bundle(bundle)

    valid_bundle, _, _ = make_bundle(tmp_path / "second")
    wrong_name = valid_bundle.with_name("wrong-name")
    valid_bundle.rename(wrong_name)
    with pytest.raises(ValueError, match="directory name"):
        load_experiment_bundle(wrong_name)


@pytest.mark.parametrize(
    ("variant", "message"),
    [
        ({"name": "../escape", "overrides": {}}, "safe"),
        ({"name": "test", "preset": "missing", "overrides": {}}, "configuration"),
        ({"name": "test", "overrides": {"unknown": True}}, "configuration"),
        ({"name": "test", "overrides": {"w_app": 0.5}}, "appearance"),
        (
            {"name": "test", "overrides": {"motion_residual_path": "model.npz"}},
            "motion residual",
        ),
        ({"name": "test", "overrides": {"use_gmc": True}}, "camera shifts"),
        ({"name": "test", "overrides": {}, "surprise": True}, "unknown variant"),
    ],
)
def test_variant_resolution_rejects_unsafe_or_unsupported_configurations(
    variant, message
) -> None:
    with pytest.raises(ValueError, match=message):
        resolve_variant_config(variant)


def test_runner_rejects_feature_references_until_payload_support_exists(
    tmp_path: Path,
) -> None:
    feature_records = [
        DetectionRecord(0, None, 0, (0, 0, 10, 20), 0.9, 1, feature_ref="features:0")
    ]
    source = SourceManifest.create(
        kind="synthetic",
        name="features",
        detection_sha256=detection_payload_sha256(feature_records, frame_count=1),
        ground_truth_sha256=None,
        video_sha256=None,
        detector={"name": "fixture"},
        frame_count=1,
        width=20,
        height=20,
        fps=None,
        coordinate_space="pixel_xyxy",
        created_at=NOW,
    )
    experiment = ExperimentManifest.create(
        source_id=source.source_id,
        baseline="baseline",
        variants=({"name": "baseline", "overrides": {}},),
        metrics=("track_count",),
        frame_range={"start": 0, "end": 1},
        visiontrack_version="0.2.0",
        git_revision=None,
        environment={"python": "3.12"},
        created_at=NOW,
    )
    bundle = create_experiment_bundle(tmp_path, experiment, source, feature_records)
    with pytest.raises(ValueError, match="feature payload"):
        run_comparison(bundle)
