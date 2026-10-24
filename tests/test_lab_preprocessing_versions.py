"""New filtering is explicit, old report bytes survive, mixed policies fail closed."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from tests.test_lab_evaluator_versions import convert_to_historical
from tests.test_lab_failures import NOW, _run_metadata, make_failure_bundle
from visiontrack.eval.definitions import EVALUATOR
from visiontrack.eval.mot17 import MOT17_PREPROCESSING, evaluate_frames
from visiontrack.lab import (
    DetectionRecord,
    ExperimentManifest,
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
    sha256_json,
)
from visiontrack.lab.contracts import canonical_json
from visiontrack.lab.evaluation_policy import LEGACY_LAB_PREPROCESSING
from visiontrack.lab.metrics import evaluation_frames
from visiontrack.lab.report import build_report_model, render_report_html
from visiontrack.lab.storage import read_ground_truth_jsonl, read_track_jsonl


def _rewrite(path, artifact):
    artifact.pop("metric_id", None)
    artifact["metric_id"] = sha256_json(artifact)
    path.write_text(json.dumps(artifact))


def to_schema_two(bundle, name="baseline"):
    path = bundle / "runs" / name / "metrics.json"
    artifact = json.loads(path.read_text())
    frames = evaluation_frames(
        tuple(read_ground_truth_jsonl(bundle / "inputs/ground_truth.jsonl", frame_count=3)),
        tuple(read_track_jsonl(bundle / "runs" / name / "tracks.jsonl", frame_count=3)),
        start=0, end=3,
    )
    artifact.update(schema_version=2, preprocessing=LEGACY_LAB_PREPROCESSING,
                    values=evaluate_frames(frames))
    _rewrite(path, artifact)


def policy_difference_bundle(root):
    """Hand-defined outputs: zero-marked pedestrian and car are not ignore regions in v2."""
    detections = [DetectionRecord(0, None, 0, (10, 10, 30, 50), .95, 1)]
    gt = [GroundTruthRecord(f, f, 1, (10, 10, 30, 50), 1, 1., False) for f in range(3)]
    gt += [GroundTruthRecord(0, 0, 2, (60, 10, 80, 50), 1, 1., True),
           GroundTruthRecord(0, 0, 3, (100, 10, 120, 50), 3, 1., False)]
    source = SourceManifest.create(
        kind="mot", name="hand-defined-policy-difference",
        detection_sha256=detection_payload_sha256(detections, frame_count=3),
        ground_truth_sha256=ground_truth_payload_sha256(gt, frame_count=3),
        video_sha256=None, detector={"name": "fixture, not a detector evaluation"},
        frame_count=3, width=160, height=80, fps=30., coordinate_space="pixel_xyxy",
        created_at=NOW,
    )
    experiment = ExperimentManifest.create(
        source_id=source.source_id, baseline="baseline",
        variants=({"name": "baseline", "overrides": {"n_init": 2}},),
        metrics=("HOTA", "IDF1", "MOTA", "IDSW", "Frag"),
        frame_range={"start": 0, "end": 3}, visiontrack_version="0.3.0",
        git_revision="policy-fixture", environment={"python": "fixture"}, created_at=NOW,
    )
    bundle = create_experiment_bundle(root, experiment, source, detections, gt)
    tracks = [TrackObservationRecord(f, 10, (10, 10, 30, 50), .95, 1) for f in range(3)]
    tracks += [TrackObservationRecord(0, 20, (60, 10, 80, 50), .95, 1),
               TrackObservationRecord(0, 30, (100, 10, 120, 50), .95, 3)]
    variant = experiment.variants[0]
    create_variant_run(bundle, "baseline", _run_metadata(experiment, source, variant, tracks),
                       tracks, frame_count=3)
    return bundle


def test_new_policy_changes_scoring_not_inputs_and_failure_context_matches(tmp_path):
    bundle = policy_difference_bundle(tmp_path)
    before = {p: p.read_bytes() for p in bundle.rglob("*.jsonl")}
    metric = calculate_bundle_metrics(bundle)["baseline"]
    assert metric["schema_version"] == 3
    assert metric["evaluator"] == EVALUATOR
    assert metric["preprocessing"] == MOT17_PREPROCESSING
    assert metric["values"]["FP"] == 2 and metric["values"]["TP"] == 3
    events = calculate_failure_events(bundle)["baseline"]
    assert len(events) == 2 and all(e.event_type == "false_positive" for e in events)
    assert all(e.context["preprocessing"] == MOT17_PREPROCESSING for e in events)
    assert all(e.context["metric_id"] == metric["metric_id"] for e in events)
    assert all(p.read_bytes() == content for p, content in before.items())
    create_comparison_summary(bundle)
    report = build_report_model(bundle)
    assert report["preprocessing"] == MOT17_PREPROCESSING
    assert any("not evidence of improved tracking" in item for item in report["limitations"])
    assert MOT17_PREPROCESSING in render_report_html(report)


def test_schema_two_uses_legacy_filtering_for_actual_different_case(tmp_path):
    bundle = policy_difference_bundle(tmp_path)
    calculate_bundle_metrics(bundle)
    to_schema_two(bundle)
    metric = json.loads((bundle / "runs/baseline/metrics.json").read_text())
    assert metric["values"]["FP"] == 0
    assert calculate_failure_events(bundle)["baseline"] == ()
    create_comparison_summary(bundle)
    assert "preprocessing" not in build_report_model(bundle)


def test_python_export_matches_shared_browser_policy_vector(tmp_path):
    bundle = policy_difference_bundle(tmp_path)
    calculate_bundle_metrics(bundle)
    events = calculate_failure_events(bundle)["baseline"]
    create_comparison_summary(bundle)
    vector = json.loads((Path(__file__).parent / "fixtures/lab_preprocessing_v2.json").read_text())
    report = build_report_model(bundle)
    assert report == vector["report"]
    content = dict(report)
    content.pop("report_id")
    assert canonical_json(content) == vector["canonical_report_content"]
    assert vector["canonical_failure_contents"] == [
        canonical_json({k: v for k, v in event.to_dict().items() if k != "event_id"})
        for event in sorted(events, key=lambda event: event.event_id)
    ]


@pytest.mark.parametrize("version,report_id,json_sha,html_sha,events_sha", [
    (1, "389a9c67e89eb20bd44b368a1f8b038f9dcdb4a153a6fe3e94f98f9c473e3c55",
     "dbdddcddd68b1253026978cbe16c46c3d3dff58f210a58291c22273822cb830d",
     "ea13f1a6e80ef3d5ad00991164b7c3cf64c06b79319c5576ec7fb1bef75c470f",
     "0d3d3318d56b576d5b3702c03485b93f40cdecc0dfe6166dfb77a437e22bc31f"),
    (2, "e5e5c389c1c1de97589dec8c92b068b8c1d5d134008082136aa0223365ed1941",
     "d1df76a3d73a3560d3d74253df70c14e131cdc63343537616233e02a2cf8e080",
     "a76d2a1734dbf733aeef743bd78f8a6476b72bd6593322930b0a5f8a17d89f52",
     "6b520dced14e7065f91c0a5e3078e82b00c69f02049b9455a6a360cfe51995e8"),
])
def test_historical_report_and_event_golden_bytes(tmp_path, version, report_id,
                                                json_sha, html_sha, events_sha):
    # Captured by executing the unmodified 87575c9 checkout before migration,
    # not by approving the current implementation's own output.
    bundle = make_failure_bundle(tmp_path, variants=1)
    if version == 1:
        convert_to_historical(bundle, "baseline")
    else:
        to_schema_two(bundle)
    calculate_failure_events(bundle)
    create_comparison_summary(bundle)
    report = build_report_model(bundle)
    assert report["report_id"] == report_id
    assert hashlib.sha256(canonical_json(report).encode()).hexdigest() == json_sha
    assert hashlib.sha256(render_report_html(report).encode()).hexdigest() == html_sha
    events = (bundle / "runs/baseline/failures.jsonl").read_bytes()
    assert hashlib.sha256(events).hexdigest() == events_sha


def test_mixed_preprocessing_is_rejected_before_summary_or_failure_publication(tmp_path):
    bundle = make_failure_bundle(tmp_path)
    to_schema_two(bundle, "patient")
    with pytest.raises(ValueError, match="mixed metric preprocessing"):
        create_comparison_summary(bundle)
    with pytest.raises(ValueError, match="mixed metric evaluation"):
        calculate_failure_events(bundle)
    assert not (bundle / "comparison.json").exists()
    assert not list(bundle.glob("runs/*/failures.jsonl"))


@pytest.mark.parametrize("schema,policy", [
    (1, MOT17_PREPROCESSING), (2, MOT17_PREPROCESSING),
    (3, LEGACY_LAB_PREPROCESSING), (3, "visiontrack.mot17-preprocessing/v1"),
    (3, "unknown"), (3, None), (3, {}),
])
def test_rehashed_unknown_or_wrong_schema_policy_is_rejected(tmp_path, schema, policy):
    bundle = make_failure_bundle(tmp_path, variants=1)
    path = bundle / "runs/baseline/metrics.json"
    artifact = json.loads(path.read_text())
    artifact.update(schema_version=schema, preprocessing=policy)
    if schema == 1:
        artifact.pop("evaluator")
    _rewrite(path, artifact)
    with pytest.raises(ValueError, match="preprocessing"):
        create_comparison_summary(bundle)
    with pytest.raises(ValueError, match="preprocessing"):
        calculate_failure_events(bundle)
    assert not (bundle / "runs/baseline/failures.jsonl").exists()


@pytest.mark.parametrize("threshold", [True, None, "0.5", 0., .7, float("nan"), float("inf")])
def test_unsupported_threshold_is_rejected_even_with_valid_fingerprint(tmp_path, threshold):
    bundle = make_failure_bundle(tmp_path, variants=1)
    path = bundle / "runs/baseline/metrics.json"
    artifact = json.loads(path.read_text())
    artifact["iou_threshold"] = threshold
    # Non-finite values are rejected by canonical hashing as well.
    if isinstance(threshold, float) and not threshold < float("inf"):
        with pytest.raises(ValueError):
            _rewrite(path, artifact)
        return
    _rewrite(path, artifact)
    with pytest.raises(ValueError, match="iou_threshold"):
        calculate_failure_events(bundle)


def test_failure_policy_mismatch_is_rejected_even_after_rehash(tmp_path):
    bundle = make_failure_bundle(tmp_path, variants=1)
    calculate_failure_events(bundle)
    path = bundle / "runs/baseline/failures.jsonl"
    events = [json.loads(row) for row in path.read_text().splitlines()]
    events[0]["context"]["preprocessing"] = "visiontrack.mot17-preprocessing/v1"
    content = dict(events[0])
    content.pop("event_id")
    events[0]["event_id"] = sha256_json(content)
    path.write_text("\n".join(json.dumps(e) for e in events) + "\n")
    with pytest.raises(ValueError, match="preprocessing"):
        create_comparison_summary(bundle)


@pytest.mark.parametrize("version,field,value", [
    (1, "evaluator", EVALUATOR),
    (2, "preprocessing", MOT17_PREPROCESSING),
])
def test_historical_failure_cannot_claim_new_semantics(tmp_path, version, field, value):
    bundle = make_failure_bundle(tmp_path, variants=1)
    if version == 1:
        convert_to_historical(bundle, "baseline")
    else:
        to_schema_two(bundle)
    calculate_failure_events(bundle)
    path = bundle / "runs/baseline/failures.jsonl"
    events = [json.loads(row) for row in path.read_text().splitlines()]
    events[0]["context"][field] = value
    content = dict(events[0])
    content.pop("event_id")
    events[0]["event_id"] = sha256_json(content)
    path.write_text("\n".join(json.dumps(event) for event in events) + "\n")
    with pytest.raises(ValueError, match="historical"):
        create_comparison_summary(bundle)


def test_later_metric_conflict_cannot_partially_migrate_a_bundle(tmp_path):
    bundle = make_failure_bundle(tmp_path)
    to_schema_two(bundle, "patient")
    first = bundle / "runs/baseline/metrics.json"
    first.unlink()
    before = {p: p.read_bytes() for p in bundle.rglob("*") if p.is_file()}
    with pytest.raises(FileExistsError, match="new bundle"):
        calculate_bundle_metrics(bundle)
    assert not first.exists()
    assert all(p.read_bytes() == content for p, content in before.items())


def test_later_failure_conflict_cannot_publish_earlier_variant(tmp_path):
    bundle = make_failure_bundle(tmp_path)
    later = bundle / "runs/patient/failures.jsonl"
    later.write_text("foreign data\n")
    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        calculate_failure_events(bundle)
    assert later.read_text() == "foreign data\n"
    assert not (bundle / "runs/baseline/failures.jsonl").exists()
