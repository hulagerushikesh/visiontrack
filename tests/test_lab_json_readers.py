"""A digest cannot resolve repeated fields: reject them before evidence use."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from test_lab_decision import decision_values, sealed_report_bundle
from test_lab_evidence import evidence_manifest
from test_lab_evidence import make_bundle as make_evidence_bundle
from test_lab_report import make_report_bundle
from test_lab_streaming_replay import make_bundle, rebind_payload

from visiontrack.cli import main
from visiontrack.lab import (
    DecisionRecord,
    DetectionRecord,
    build_report_model,
    plan_human_decision,
    sha256_json,
    write_evidence_manifest,
)
from visiontrack.lab.contracts import _parse_json

VECTORS = json.loads(
    (Path(__file__).parent / "fixtures/lab_json_boundary.json").read_text(encoding="utf-8"),
)


def duplicate(text, key, earlier="null"):
    needle = json.dumps(key) + ":"
    assert text.count(needle) >= 1
    return text.replace(needle, f"{needle}{earlier},{needle}", 1)


def snapshot(bundle):
    return {path.relative_to(bundle): path.read_bytes()
            for path in bundle.rglob("*") if path.is_file()}


@pytest.mark.parametrize("text", VECTORS["accepted"])
def test_json_boundary_preserves_valid_json(text):
    assert _parse_json(text) == json.loads(text)
    assert _parse_json(text.encode()) == json.loads(text)


@pytest.mark.parametrize("text", VECTORS["rejected"])
def test_json_boundary_refuses_ambiguous_or_nonstandard_json(text):
    with pytest.raises(ValueError):
        _parse_json(text)
    with pytest.raises(ValueError):
        _parse_json(text.encode())


def test_detection_does_not_silently_choose_the_last_score():
    row = DetectionRecord(0, None, 7, (10., 10., 30., 50.), .9, 1)
    text = duplicate(row.to_json(), "score", "0.05")
    assert json.loads(text)["score"] == .9  # Previous permissive interpretation.
    with pytest.raises(ValueError, match="duplicate JSON object key: 'score'"):
        DetectionRecord.from_json(text)


@pytest.mark.parametrize("command", ["lab-initiation", "lab-association"])
@pytest.mark.parametrize("relative,key", [
    ("manifest.json", "frame_range"),
    ("manifest.json", "start"),
    ("source.json", "fps"),
    ("source.json", "name"),
    ("runs/baseline/run.json", "observation_count"),
    ("runs/baseline/run.json", "n_init"),
    ("inputs/detections.jsonl", "score"),
    ("inputs/ground_truth.jsonl", "object_id"),
    ("runs/baseline/tracks.jsonl", "score"),
])
def test_diagnostics_refuse_repeated_fields_even_with_matching_content_hashes(
    tmp_path, capsys, relative, key, command,
):
    bundle = make_bundle(tmp_path)
    path = bundle / relative
    payload = duplicate(path.read_text(), key).encode()
    if relative.startswith("inputs/"):
        # Rebind exact raw hashes and lineage so this is not a checksum-only test.
        bundle = rebind_payload(bundle, relative, payload)
    else:
        path.write_bytes(payload)
        if relative.endswith("tracks.jsonl"):
            run_path = bundle / "runs/baseline/run.json"
            metadata = json.loads(run_path.read_text())
            metadata["track_sha256"] = hashlib.sha256(payload).hexdigest()
            metadata.pop("run_id")
            metadata["run_id"] = sha256_json(metadata)
            run_path.write_text(json.dumps(metadata))
    before = snapshot(bundle)
    selectors = (["--start", "3", "--end", "5"] if command == "lab-initiation" else
                 ["--frame", "4", "--track-id", "1", "--detection-index", "7"])
    assert main([command, str(bundle), "--variant", "baseline", *selectors, "--json"]) == 2
    output = capsys.readouterr()
    assert output.out == ""
    assert "duplicate JSON object key" in output.err
    assert snapshot(bundle) == before


@pytest.mark.parametrize("relative,key", [
    ("runs/baseline/run.json", "run_id"),
    ("runs/baseline/metrics.json", "metric_id"),
    ("runs/baseline/metrics.json", "MOTA"),
])
def test_report_builder_refuses_duplicate_fields_in_saved_run_and_metrics(tmp_path, relative, key):
    bundle = make_report_bundle(tmp_path)
    path = bundle / relative
    path.write_text(duplicate(path.read_text(), key))
    before = snapshot(bundle)
    with pytest.raises(ValueError, match="duplicate JSON object key"):
        build_report_model(bundle)
    assert snapshot(bundle) == before


def test_evidence_writer_does_not_use_ambiguous_run_metadata(tmp_path):
    bundle, _, _ = make_evidence_bundle(tmp_path)
    path = bundle / "runs/baseline/run.json"
    # This fixture uses json.dumps's spaces, unlike normal canonical run output.
    path.write_text(duplicate(json.dumps(json.loads(path.read_text()), separators=(",", ":")),
                              "run_id"))
    before = snapshot(bundle)
    with pytest.raises(ValueError, match="duplicate JSON object key"):
        write_evidence_manifest(bundle, "baseline", evidence_manifest(), {})
    assert snapshot(bundle) == before
    assert not (bundle / "runs/baseline/evidence").exists()


def test_human_decision_reader_refuses_ambiguous_report_before_drafting(tmp_path):
    bundle = sealed_report_bundle(tmp_path)
    path = bundle / "report/report.json"
    path.write_text(duplicate(path.read_text(), "report_id"))
    before = snapshot(bundle)
    with pytest.raises(ValueError, match="duplicate JSON object key"):
        plan_human_decision(bundle, status="rejected_all", accepted_variant=None,
                            rationale="Review rehearsal only.", author="reviewer",
                            decided_at="2026-11-01T00:00:00Z")
    assert snapshot(bundle) == before
    assert not (bundle / "decision.json").exists()


def test_contract_decision_reader_does_not_choose_between_two_statuses():
    decision = DecisionRecord.create(**decision_values())
    text = duplicate(decision.to_json(), "status", '"rejected_all"')
    with pytest.raises(ValueError, match="duplicate JSON object key: 'status'"):
        DecisionRecord.from_json(text)
