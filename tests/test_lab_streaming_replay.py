"""Long-run diagnosis must stream all evidence, preserve bytes and fail closed."""
from __future__ import annotations

import hashlib
import json
import tracemalloc
from dataclasses import asdict
from pathlib import Path

import pytest

from visiontrack.cli import main
from visiontrack.lab import (
    DetectionRecord,
    ExperimentManifest,
    GroundTruthRecord,
    SourceManifest,
    build_association_explanation,
    build_initiation_trace,
    create_experiment_bundle,
    detection_payload_sha256,
    ground_truth_payload_sha256,
    run_comparison,
    sha256_json,
)
from visiontrack.lab.initiation import _InitiationObserver
from visiontrack.lab.replay import _iter_replay_frames
from visiontrack.lab.runner import _group_detections, load_experiment_bundle
from visiontrack.lab.storage import _iter_jsonl, serialize_detection_jsonl

NOW = "2026-11-01T00:00:00Z"
BOX = (10., 10., 30., 50.)


def make_bundle(tmp_path, *, start=1, end=7, empty=False, overrides=None):
    detections = [] if empty else [
        DetectionRecord(frame, None, key, BOX, score, 1)
        for frame in (0, 2, 3, 4, 6, 8) for key, score in ((7, .9), (91, .05))
    ]
    truth = [GroundTruthRecord(frame, None, 1, BOX, 1, 1., False) for frame in range(9)]
    source = SourceManifest.create(
        kind="synthetic", name="streamed diagnostic fixture",
        detection_sha256=detection_payload_sha256(detections, frame_count=9),
        ground_truth_sha256=ground_truth_payload_sha256(truth, frame_count=9),
        video_sha256=None, detector={"name": "fixture"}, frame_count=9, width=100, height=80,
        fps=30., coordinate_space="pixel_xyxy", created_at=NOW,
    )
    experiment = ExperimentManifest.create(
        source_id=source.source_id, baseline="baseline",
        variants=({"name": "baseline", "overrides": overrides or {}},), metrics=("track_count",),
        frame_range={"start": start, "end": end}, visiontrack_version="0.5.0",
        git_revision=None, environment={"python": "fixture"}, created_at=NOW,
    )
    bundle = create_experiment_bundle(tmp_path, experiment, source, detections, truth)
    run_comparison(bundle)
    return bundle


def rebind_payload(bundle, relative, payload):
    """Give invalid rows honest hashes so tests reach semantic validation."""
    (bundle / relative).write_bytes(payload)
    source = json.loads((bundle / "source.json").read_text())
    source.pop("source_id")
    field = "detection_sha256" if "detections" in relative else "ground_truth_sha256"
    source[field] = hashlib.sha256(payload).hexdigest()
    source = SourceManifest.create(**source)
    experiment = json.loads((bundle / "manifest.json").read_text())
    experiment.pop("experiment_id")
    experiment.pop("config_sha256")
    experiment["source_id"] = source.source_id
    experiment = ExperimentManifest.create(**experiment)
    (bundle / "source.json").write_text(source.to_json() + "\n")
    (bundle / "manifest.json").write_text(experiment.to_json() + "\n")
    run_path = bundle / "runs/baseline/run.json"
    metadata = json.loads(run_path.read_text())
    metadata.update(source_id=source.source_id, experiment_id=experiment.experiment_id,
                    detection_sha256=source.detection_sha256)
    metadata.pop("run_id")
    metadata["run_id"] = sha256_json(metadata)
    run_path.write_text(json.dumps(metadata))
    target = bundle.with_name(experiment.experiment_id)
    bundle.rename(target)
    return target


@pytest.mark.parametrize("empty,start,end", [(False, 1, 7), (False, 0, 9), (True, 1, 7)])
def test_streamed_frames_equal_materialized_runner_with_gaps_and_source_tail(
    tmp_path, empty, start, end,
):
    bundle = make_bundle(tmp_path, empty=empty, start=start, end=end)
    _, source, records = load_experiment_bundle(bundle)
    assert tuple(_iter_replay_frames(bundle, source, start=start, end=end)) == (
        _group_detections(records, start=start, end=end)
    )
    trace = build_initiation_trace(bundle, variant="baseline", start=start, end=end)
    assert [row["frame_index"] for row in trace["frames"]] == list(range(start, end))
    assert trace["track_sha256"] == hashlib.sha256(
        (bundle / "runs/baseline/tracks.jsonl").read_bytes(),
    ).hexdigest()
    if not empty and start == 1:
        assert trace["frames"][0]["detections"] == []
        assert trace["frames"][1]["tracks"][0]["birth_frame"] == 2
        assert trace["frames"][3]["public_track_ids"] == [1]
        assert trace["frames"][4]["tracks"][0]["event"] == "coasting"


def test_diagnostics_never_materialize_jsonl_files(tmp_path, monkeypatch):
    bundle = make_bundle(tmp_path)
    before = {p: p.read_bytes() for p in bundle.rglob("*") if p.is_file()}
    expected = build_initiation_trace(bundle, variant="baseline", start=3, end=5)
    expected_pair = build_association_explanation(
        bundle, variant="baseline", frame=4, track_id=1, detection_index=7,
    )
    read_bytes, read_text = Path.read_bytes, Path.read_text
    def guard_bytes(path, *args, **kwargs):
        assert path.suffix != ".jsonl", "whole-file JSONL read"
        return read_bytes(path, *args, **kwargs)
    def guard_text(path, *args, **kwargs):
        assert path.suffix != ".jsonl", "whole-file JSONL read"
        return read_text(path, *args, **kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(Path, "read_bytes", guard_bytes)
        patch.setattr(Path, "read_text", guard_text)
        assert build_initiation_trace(bundle, variant="baseline", start=3, end=5) == expected
        assert build_association_explanation(
            bundle, variant="baseline", frame=4, track_id=1, detection_index=7,
        ) == expected_pair
    assert {p: p.read_bytes() for p in before} == before


@pytest.mark.parametrize("ending", [b"\n", b"\r\n", b"\r", b""])
def test_streaming_reader_checks_exact_consumed_bytes_and_legacy_line_endings(tmp_path, ending):
    records = [DetectionRecord(i, None, 7, BOX, .9, 1) for i in range(3)]
    payload = ending.join(record.to_json().encode() for record in records)
    if ending:
        payload += ending
    else:
        payload = b"\n".join(record.to_json().encode() for record in records)
    path = tmp_path / "detections.jsonl"
    path.write_bytes(payload)
    kwargs = dict(record_type=DetectionRecord, key=lambda r: (r.frame_index, r.detection_index),
                  label="detection", frame_count=3)
    assert list(_iter_jsonl(path, expected_sha256=hashlib.sha256(payload).hexdigest(),
                            **kwargs)) == records
    with pytest.raises(ValueError, match="SHA-256"):
        list(_iter_jsonl(path, expected_sha256="0" * 64, **kwargs))


@pytest.mark.parametrize("ending", ["\n", "\r\n", "\r"])
def test_streaming_reader_memory_does_not_grow_with_total_row_count(tmp_path, ending):
    # Broad allocation envelope, not a timing test or a tracker-memory claim.
    # A list-backed reader over the larger file exceeds this by several MB.
    peaks = []
    for size in (100, 10_000):
        path = tmp_path / f"{size}.jsonl"
        with path.open("w", encoding="utf-8", newline="") as stream:
            for frame in range(size):
                stream.write(DetectionRecord(frame, None, 7, BOX, .9, 1).to_json() + ending)
        tracemalloc.start()
        try:
            count = sum(1 for _ in _iter_jsonl(
                path, record_type=DetectionRecord,
                key=lambda row: (row.frame_index, row.detection_index), label="detection",
                frame_count=size,
            ))
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        assert count == size
        peaks.append(peak)
    assert peaks[1] < max(512 * 1024, peaks[0] * 3), peaks


@pytest.mark.parametrize("location", ["before", "after"])
@pytest.mark.parametrize("fault", [
    "duplicate", "out-of-order", "blank", "invalid", "missing-field", "wrong-type", "range",
])
def test_invalid_detection_rows_outside_selected_replay_range_are_not_skipped(
    tmp_path, location, fault,
):
    bundle = make_bundle(tmp_path)
    path = bundle / "inputs/detections.jsonl"
    lines = path.read_bytes().splitlines(keepends=True)
    row = lines[0] if location == "before" else lines[-1]
    if fault == "duplicate":
        bad = row
    elif fault == "out-of-order":
        bad = lines[1] if location == "before" else lines[0]
    elif fault == "blank":
        bad = b"\n"
    elif fault == "invalid":
        bad = b"{bad}\n"
    elif fault == "missing-field":
        bad = b"{}\n"
    else:
        data = json.loads(row)
        data["frame_index"] = "bad" if fault == "wrong-type" else 9
        bad = (json.dumps(data) + "\n").encode()
    payload = bad + b"".join(lines) if location == "before" else b"".join(lines) + bad
    bundle = rebind_payload(bundle, "inputs/detections.jsonl", payload)
    with pytest.raises(ValueError):
        build_initiation_trace(bundle, variant="baseline", start=3, end=4)


def test_ground_truth_is_fully_validated_even_though_diagnosis_does_not_score_it(tmp_path):
    bundle = make_bundle(tmp_path)
    payload = (bundle / "inputs/ground_truth.jsonl").read_bytes() + b"{bad}\n"
    bundle = rebind_payload(bundle, "inputs/ground_truth.jsonl", payload)
    with pytest.raises(ValueError, match="ground-truth"):
        build_initiation_trace(bundle, variant="baseline", start=3, end=4)


@pytest.mark.parametrize("fault", ["count", "range", "order"])
def test_saved_track_stream_is_validated_before_diagnostic_replay(tmp_path, fault):
    bundle = make_bundle(tmp_path)
    path = bundle / "runs/baseline/tracks.jsonl"
    metadata_path = bundle / "runs/baseline/run.json"
    metadata = json.loads(metadata_path.read_text())
    if fault == "count":
        metadata["observation_count"] += 1
    else:
        lines = path.read_bytes().splitlines(keepends=True)
        if fault == "range":
            row = json.loads(lines[-1])
            row["frame_index"] = 8  # Valid source row, outside [1, 7).
            lines[-1] = (json.dumps(row) + "\n").encode()
        else:
            lines.reverse()
        payload = b"".join(lines)
        path.write_bytes(payload)
        metadata["track_sha256"] = hashlib.sha256(payload).hexdigest()
    metadata.pop("run_id")
    metadata["run_id"] = sha256_json(metadata)
    metadata_path.write_text(json.dumps(metadata))
    with pytest.raises(ValueError, match="count|frame_range|out-of-order"):
        build_association_explanation(
            bundle, variant="baseline", frame=4, track_id=1, detection_index=7,
        )


@pytest.mark.parametrize("relative", [
    "manifest.json", "source.json", "runs/baseline/run.json", "inputs/detections.jsonl",
    "inputs/ground_truth.jsonl", "runs/baseline/tracks.jsonl",
])
def test_evidence_changed_during_replay_refuses_cli_without_partial_json(
    tmp_path, monkeypatch, capsys, relative,
):
    bundle = make_bundle(tmp_path)
    original = _InitiationObserver.update
    changed = False
    def mutate(self, detections, camera_shift=None):
        nonlocal changed
        result = original(self, detections, camera_shift=camera_shift)
        if not changed:
            changed = True
            path = bundle / relative
            path.write_bytes(path.read_bytes() + b" ")
        return result
    monkeypatch.setattr(_InitiationObserver, "update", mutate)
    assert main(["lab-initiation", str(bundle), "--variant", "baseline", "--start", "3",
                 "--end", "4", "--json"]) == 2
    out = capsys.readouterr()
    assert out.out == "" and out.err.startswith("error:")
    assert changed


def test_features_outside_experiment_remain_ignored_but_inside_refused(tmp_path):
    bundle = make_bundle(tmp_path)
    _, source, records = load_experiment_bundle(bundle)
    rows = [asdict(row) for row in records]
    rows[0]["feature_ref"] = "unused-before-range"
    rows[-1]["feature_ref"] = "unused-after-range"
    payload = serialize_detection_jsonl([DetectionRecord(**row) for row in rows])
    bundle = rebind_payload(bundle, "inputs/detections.jsonl", payload)
    assert build_initiation_trace(bundle, variant="baseline", start=3, end=4)
    rows[2]["feature_ref"] = "unsupported-in-range"
    payload = serialize_detection_jsonl([DetectionRecord(**row) for row in rows])
    bundle = rebind_payload(bundle, "inputs/detections.jsonl", payload)
    with pytest.raises(ValueError, match="feature_ref"):
        build_initiation_trace(bundle, variant="baseline", start=3, end=4)
