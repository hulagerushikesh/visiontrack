"""The local Lab report presents only fully verified bundle evidence."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from visiontrack.lab import (
    DetectionRecord,
    ExperimentManifest,
    GroundTruthRecord,
    SourceManifest,
    build_report_model,
    calculate_bundle_metrics,
    calculate_failure_events,
    canonical_json,
    create_comparison_summary,
    create_experiment_bundle,
    detection_payload_sha256,
    generate_local_report,
    ground_truth_payload_sha256,
    run_comparison,
    sha256_json,
    write_report_artifact,
)

NOW = "2026-09-20T08:00:00Z"


def make_report_bundle(
    tmp_path: Path,
    *,
    include_failures: bool = True,
    seal: bool = True,
) -> Path:
    detections = [
        DetectionRecord(frame, frame, 0, (10 + frame, 10, 30 + frame, 50), 0.95, 1)
        for frame in range(4)
    ]
    ground_truth = [
        GroundTruthRecord(
            frame,
            frame,
            1,
            (10 + frame, 10, 30 + frame, 50),
            1,
            1.0,
            False,
        )
        for frame in range(4)
    ]
    source = SourceManifest.create(
        kind="mot",
        name="Fixture <script>alert(1)</script>",
        detection_sha256=detection_payload_sha256(detections, frame_count=4),
        ground_truth_sha256=ground_truth_payload_sha256(ground_truth, frame_count=4),
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
        variants=({"name": "baseline", "overrides": {"n_init": 2}},),
        metrics=("HOTA", "IDF1", "MOTA", "IDSW", "Frag"),
        frame_range={"start": 0, "end": 4},
        visiontrack_version="0.2.0",
        git_revision="13fda34",
        environment={"python": "3.12"},
        created_at=NOW,
    )
    bundle = create_experiment_bundle(
        tmp_path, experiment, source, detections, ground_truth
    )
    run_comparison(bundle)
    calculate_bundle_metrics(bundle)
    if include_failures:
        calculate_failure_events(bundle)
    if seal:
        create_comparison_summary(bundle)
    return bundle


def test_report_model_is_content_addressed_and_bounded(tmp_path: Path) -> None:
    bundle = make_report_bundle(tmp_path)
    model = build_report_model(bundle)

    content = dict(model)
    report_id = content.pop("report_id")
    assert report_id == sha256_json(content)
    assert model["comparison_id"]
    assert model["experiment"]["baseline"] == "baseline"
    assert model["source"]["video_status"] == "not_declared"
    assert model["variants"][0]["metrics"]["HOTA"] > 0
    assert model["variants"][0]["failure_counts"]["miss"] == 1
    assert model["failure_event_total"] == 1
    assert model["failures"][0]["event_type"] == "miss"
    assert model["failures"][0]["evidence_frames"] == {"start": 0, "end": 3}
    assert model["decision"]["accepted_variant"] is None


def test_report_generation_is_standalone_accessible_and_idempotent(tmp_path: Path) -> None:
    bundle = make_report_bundle(tmp_path)
    path = generate_local_report(bundle)
    first_html = path.read_bytes()
    first_json = (bundle / "report/report.json").read_bytes()
    model = json.loads(first_json)
    html = first_html.decode()

    assert path == bundle / "report/index.html"
    assert first_json == (canonical_json(model) + "\n").encode()
    assert "<main id=\"content\">" in html
    assert "Skip to report content" in html
    assert '<caption>Value and delta relative to baseline</caption>' in html
    assert '<th scope="col">Ground truth</th>' in html
    assert f'href="#evidence-{model["failures"][0]["event_id"]}"' in html
    assert "Fixture &lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "<script>" not in html
    assert "https://" not in html

    assert generate_local_report(bundle) == path
    assert path.read_bytes() == first_html
    assert (bundle / "report/report.json").read_bytes() == first_json


def test_report_refuses_unsealed_incomplete_or_corrupt_evidence(tmp_path: Path) -> None:
    unsealed = make_report_bundle(tmp_path / "unsealed", seal=False)
    with pytest.raises(ValueError, match="comparison.json is required"):
        generate_local_report(unsealed)

    incomplete = make_report_bundle(
        tmp_path / "incomplete", include_failures=False, seal=True
    )
    with pytest.raises(ValueError, match="failure artifacts are required"):
        generate_local_report(incomplete)

    corrupt = make_report_bundle(tmp_path / "corrupt")
    with (corrupt / "runs/baseline/tracks.jsonl").open("ab") as stream:
        stream.write(b" ")
    with pytest.raises(ValueError, match="SHA-256"):
        generate_local_report(corrupt)


def test_report_artifacts_refuse_conflicts_and_path_traversal(tmp_path: Path) -> None:
    bundle = make_report_bundle(tmp_path)
    path = generate_local_report(bundle)
    path.write_text("changed", encoding="utf-8")
    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        generate_local_report(bundle)
    with pytest.raises(ValueError, match="artifact name"):
        write_report_artifact(bundle, "../outside.html", b"unsafe")

    preflight = make_report_bundle(tmp_path / "preflight")
    (preflight / "report/index.html").write_text("conflict", encoding="utf-8")
    with pytest.raises(FileExistsError, match="conflicting report files"):
        generate_local_report(preflight)
    assert not (preflight / "report/report.json").exists()
