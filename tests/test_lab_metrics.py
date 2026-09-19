"""Lab metrics are calculated only from verified bundle evidence."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from visiontrack.lab import (
    DetectionRecord,
    ExperimentManifest,
    GroundTruthRecord,
    SourceManifest,
    calculate_bundle_metrics,
    create_comparison_summary,
    create_experiment_bundle,
    detection_payload_sha256,
    ground_truth_payload_sha256,
    run_comparison,
    sha256_json,
)

NOW = "2026-09-19T18:00:00Z"


def make_metric_bundle(tmp_path: Path, *, with_ground_truth: bool = True) -> Path:
    detections: list[DetectionRecord] = []
    ground_truth: list[GroundTruthRecord] = []
    for frame in range(4):
        detections.extend(
            [
                DetectionRecord(frame, None, 0, (10 + frame, 10, 30 + frame, 50), 0.95, 1),
                DetectionRecord(frame, None, 1, (60, 10, 80, 50), 0.95, 7),
            ]
        )
        ground_truth.extend(
            [
                GroundTruthRecord(
                    frame,
                    frame + 1,
                    1,
                    (10 + frame, 10, 30 + frame, 50),
                    1,
                    1.0,
                    frame == 0,
                ),
                GroundTruthRecord(frame, frame + 1, 2, (60, 10, 80, 50), 7, 1.0, False),
            ]
        )
    gt_hash = (
        ground_truth_payload_sha256(ground_truth, frame_count=4)
        if with_ground_truth
        else None
    )
    source = SourceManifest.create(
        kind="mot" if with_ground_truth else "synthetic",
        name="metric-fixture",
        detection_sha256=detection_payload_sha256(detections, frame_count=4),
        ground_truth_sha256=gt_hash,
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
        metrics=("HOTA", "IDF1", "MOTA", "MOTP", "IDSW", "Frag"),
        frame_range={"start": 0, "end": 4},
        visiontrack_version="0.2.0",
        git_revision="2003fb1",
        environment={"python": "3.12"},
        created_at=NOW,
    )
    bundle = create_experiment_bundle(
        tmp_path,
        experiment,
        source,
        detections,
        ground_truth if with_ground_truth else None,
    )
    run_comparison(bundle)
    return bundle


def test_metrics_reuse_mot_preprocessing_and_are_content_addressed(tmp_path: Path) -> None:
    bundle = make_metric_bundle(tmp_path)
    artifacts = calculate_bundle_metrics(bundle)

    assert set(artifacts) == {"baseline", "patient"}
    for name, artifact in artifacts.items():
        values = artifact["values"]
        assert values["HOTA"] == 1.0
        assert values["IDF1"] == 1.0
        assert values["MOTA"] == 1.0
        assert values["MOTP"] > 0.95
        assert values["IDSW"] == 0
        assert values["Frag"] == 0
        assert artifact["variant"] == name
        assert artifact["preprocessing"] == "visiontrack.eval.mot17.preprocess_frame"
        content = dict(artifact)
        metric_id = content.pop("metric_id")
        assert metric_id == sha256_json(content)
        assert json.loads((bundle / "runs" / name / "metrics.json").read_text()) == artifact


def test_metric_calculation_is_idempotent_and_refuses_conflicts(tmp_path: Path) -> None:
    bundle = make_metric_bundle(tmp_path)
    first = calculate_bundle_metrics(bundle)
    stored = (bundle / "runs/baseline/metrics.json").read_bytes()
    assert calculate_bundle_metrics(bundle) == first
    assert (bundle / "runs/baseline/metrics.json").read_bytes() == stored

    (bundle / "runs/baseline/metrics.json").write_text("{}\n", encoding="utf-8")
    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        calculate_bundle_metrics(bundle)


def test_metrics_require_ground_truth_and_precede_sealed_summary(tmp_path: Path) -> None:
    without_gt = make_metric_bundle(tmp_path / "without", with_ground_truth=False)
    with pytest.raises(ValueError, match="ground truth is required"):
        calculate_bundle_metrics(without_gt)

    sealed = make_metric_bundle(tmp_path / "sealed")
    create_comparison_summary(sealed)
    with pytest.raises(ValueError, match="already seals"):
        calculate_bundle_metrics(sealed)


def test_measured_summary_replaces_insufficient_evidence_but_not_decision(
    tmp_path: Path,
) -> None:
    bundle = make_metric_bundle(tmp_path)
    calculate_bundle_metrics(bundle)
    summary = create_comparison_summary(bundle)

    assert summary["evidence"]["ground_truth_status"] == "available_measured"
    assert summary["insufficient_evidence"] == []
    assert summary["metrics"]["baseline"]["HOTA"] == 1.0
    assert summary["metric_deltas_vs_baseline"]["baseline"]["HOTA"] == 0.0
    assert summary["metric_deltas_vs_baseline"]["patient"]["HOTA"] == 0.0
    assert summary["decision"]["accepted_variant"] is None
    assert summary["decision"]["status"] == "not_selected"
    assert summary["decision"]["reason"] == "requires_human_acceptance_decision"


def test_summary_rejects_partial_or_corrupt_metric_evidence(tmp_path: Path) -> None:
    partial = make_metric_bundle(tmp_path / "partial")
    calculate_bundle_metrics(partial)
    (partial / "runs/patient/metrics.json").unlink()
    with pytest.raises(ValueError, match="every declared variant"):
        create_comparison_summary(partial)

    corrupt = make_metric_bundle(tmp_path / "corrupt")
    calculate_bundle_metrics(corrupt)
    path = corrupt / "runs/baseline/metrics.json"
    artifact = json.loads(path.read_text())
    artifact["values"]["HOTA"] = 0.5
    path.write_text(json.dumps(artifact), encoding="utf-8")
    with pytest.raises(ValueError, match="metric_id"):
        create_comparison_summary(corrupt)
