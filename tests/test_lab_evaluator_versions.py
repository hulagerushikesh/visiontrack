"""Old Lab artifacts stay v1; new artifacts are explicit v2 and cannot be mixed."""
import json

import pytest

from tests.test_lab_failures import make_failure_bundle
from visiontrack.eval.definitions import EVALUATOR, LEGACY_EVALUATOR, legacy_evaluate_frames
from visiontrack.lab import (
    calculate_bundle_metrics,
    calculate_failure_events,
    create_comparison_summary,
)
from visiontrack.lab.contracts import GroundTruthRecord, TrackObservationRecord, sha256_json
from visiontrack.lab.evaluation_policy import LEGACY_LAB_PREPROCESSING
from visiontrack.lab.metrics import evaluation_frames
from visiontrack.lab.report import build_report_model
from visiontrack.lab.storage import read_ground_truth_jsonl, read_track_jsonl


def test_lab_keeps_legacy_preprocessing_when_mot17_runner_default_changes():
    # The current Lab artifact identifier names its historical policy. Changing
    # the MOT17 runner's default must not reinterpret that contract.
    ground_truth = (GroundTruthRecord(0, 1, 7, (0, 0, 10, 10), 1, 1., True),)
    tracks = (TrackObservationRecord(0, 1, (0, 0, 10, 10), .9, 1),)
    frames = evaluation_frames(ground_truth, tracks, start=0, end=1)
    assert frames[0][0].tolist() == []
    assert frames[0][2].tolist() == []  # MOT17 v2 would retain this prediction.


def convert_to_historical(bundle, name):
    path = bundle / "runs" / name / "metrics.json"
    artifact = json.loads(path.read_text())
    frames = evaluation_frames(
        tuple(read_ground_truth_jsonl(bundle / "inputs/ground_truth.jsonl", frame_count=3)),
        tuple(read_track_jsonl(bundle / "runs" / name / "tracks.jsonl", frame_count=3)),
        start=0, end=3)
    artifact.pop("evaluator")
    artifact.pop("metric_id")
    artifact["schema_version"] = 1
    artifact["preprocessing"] = LEGACY_LAB_PREPROCESSING
    artifact["values"] = legacy_evaluate_frames(frames)
    artifact["metric_id"] = sha256_json(artifact)
    path.write_text(json.dumps(artifact))
    return path.read_bytes()


def test_v1_failure_semantics_and_report_bytes_are_preserved(tmp_path):
    bundle = make_failure_bundle(tmp_path, variants=1)
    original = convert_to_historical(bundle, "baseline")
    events = calculate_failure_events(bundle)["baseline"]
    assert [e.event_type for e in events] == [
        "id_switch", "fragmentation", "miss", "false_positive"]
    assert all("evaluator" not in e.context for e in events)
    summary = create_comparison_summary(bundle)
    report = build_report_model(bundle)
    assert "evaluator" not in summary["evidence"]
    assert "evaluator" not in report
    assert report == build_report_model(bundle)
    assert (bundle / "runs/baseline/metrics.json").read_bytes() == original
    assert report["variants"][0]["failure_counts"]["fragmentation"] == 1


def test_v2_metrics_and_failures_have_explicit_semantics(tmp_path):
    bundle = make_failure_bundle(tmp_path, variants=1)
    metric = json.loads((bundle / "runs/baseline/metrics.json").read_text())
    assert metric["schema_version"] == 3 and metric["evaluator"] == EVALUATOR
    events = calculate_failure_events(bundle)["baseline"]
    assert all(e.context["evaluator"] == EVALUATOR for e in events)
    assert all(e.event_type != "fragmentation" for e in events)
    summary = create_comparison_summary(bundle)
    assert summary["evidence"]["evaluator"] == EVALUATOR
    report = build_report_model(bundle)
    assert report["evaluator"] == EVALUATOR
    assert any("historical v1" in limitation for limitation in report["limitations"])


def test_mixed_evaluators_cannot_be_compared(tmp_path):
    bundle = make_failure_bundle(tmp_path)
    convert_to_historical(bundle, "baseline")
    with pytest.raises(ValueError, match="mixed metric evaluator"):
        create_comparison_summary(bundle)


def test_new_calculation_never_overwrites_a_v1_artifact(tmp_path):
    bundle = make_failure_bundle(tmp_path, variants=1)
    old = convert_to_historical(bundle, "baseline")
    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        calculate_bundle_metrics(bundle)
    assert (bundle / "runs/baseline/metrics.json").read_bytes() == old


def test_wrong_failure_evaluator_is_rejected_even_if_rehashed(tmp_path):
    bundle = make_failure_bundle(tmp_path, variants=1)
    calculate_failure_events(bundle)
    path = bundle / "runs/baseline/failures.jsonl"
    events = [json.loads(s) for s in path.read_text().splitlines()]
    events[0]["context"]["evaluator"] = LEGACY_EVALUATOR
    content = dict(events[0])
    content.pop("event_id")
    events[0]["event_id"] = sha256_json(content)
    path.write_text("\n".join(json.dumps(e) for e in events) + "\n")
    with pytest.raises(ValueError, match="evaluator"):
        create_comparison_summary(bundle)
