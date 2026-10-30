"""Saved Python lifecycle bytes and run lineage shared with the browser importer."""
from __future__ import annotations

import json
from pathlib import Path

from visiontrack.lab import (
    DetectionRecord,
    ExperimentManifest,
    GroundTruthRecord,
    SourceManifest,
    build_initiation_trace,
    build_report_model,
    calculate_bundle_metrics,
    calculate_failure_events,
    canonical_json,
    create_comparison_summary,
    create_experiment_bundle,
    detection_payload_sha256,
    ground_truth_payload_sha256,
    run_comparison,
    sha256_json,
)

FIXTURE = Path(__file__).parent / "fixtures/lab_initiation_conformance.json"
PRODUCER = {
    "visiontrack": "0.3.0", "python": "fixture", "numpy": "fixture",
    "implementation_sha256": {"lab/initiation.py": "a" * 64},
}


def conformance_bundle(tmp_path):
    scores = [.05, .3, .55, .9, .9, .9, .3, None, None, .9, None]
    detections = [
        DetectionRecord(i, None, 7, (10., 10., 30., 50.), score, 1)
        for i, score in enumerate(scores) if score is not None
    ]
    truth = [
        GroundTruthRecord(i, None, 1, (10., 10., 30., 50.), 1, 1., False)
        for i in range(len(scores))
    ]
    source = SourceManifest.create(
        kind="synthetic", name="Initiation résumé · अभ्यास",
        detection_sha256=detection_payload_sha256(detections, frame_count=len(scores)),
        ground_truth_sha256=ground_truth_payload_sha256(truth, frame_count=len(scores)),
        video_sha256=None, detector={"name": "hand fixture"}, frame_count=len(scores),
        width=100, height=80, fps=30., coordinate_space="pixel_xyxy",
        created_at="2026-10-30T12:00:00Z",
    )
    experiment = ExperimentManifest.create(
        source_id=source.source_id, baseline="baseline",
        variants=(
            {"name": "baseline", "overrides": {"max_age": 1}},
            {"name": "single-stage", "preset": "sort",
             "overrides": {"max_age": 1, "n_init": 1}},
        ),
        metrics=("HOTA", "IDF1", "MOTA", "IDSW", "Frag"),
        frame_range={"start": 0, "end": len(scores)}, visiontrack_version="0.3.0",
        git_revision=None, environment={"python": "fixture"},
        created_at="2026-10-30T12:00:00Z",
    )
    bundle = create_experiment_bundle(tmp_path, experiment, source, detections, truth)
    run_comparison(bundle)
    calculate_bundle_metrics(bundle)
    calculate_failure_events(bundle)
    create_comparison_summary(bundle)
    return bundle


def build_fixture(tmp_path):
    bundle = conformance_bundle(tmp_path)
    vectors = []
    for variant, start, end in [("baseline", 0, 11), ("single-stage", 0, 11),
                                ("baseline", 7, 9)]:
        trace = build_initiation_trace(bundle, variant=variant, start=start, end=end)
        # Producer provenance is deliberately a declared synthetic fixture, not an
        # assertion about the executing Python environment or source checkout.
        trace.pop("trace_id")
        trace["producer"] = PRODUCER
        trace["trace_id"] = sha256_json(trace)
        vectors.append({"name": f"{variant}-{start}-{end}",
                        "trace_json": canonical_json(trace) + "\n"})
    return {"schema_version": 1, "report_json": canonical_json(build_report_model(bundle)) + "\n",
            "vectors": vectors}


def test_python_lifecycle_and_run_bytes_match_browser_vectors(tmp_path):
    fixture = json.loads(FIXTURE.read_text())
    assert build_fixture(tmp_path) == fixture
    events = set()
    dispositions = set()
    for vector in fixture["vectors"]:
        trace = json.loads(vector["trace_json"])
        trace_id = trace.pop("trace_id")
        assert sha256_json(trace) == trace_id
        for frame in trace["frames"]:
            events.update(row["event"] for row in frame["tracks"])
            dispositions.update(row["disposition"] for row in frame["detections"])
    assert len(events) == 7
    assert len(dispositions) == 7
