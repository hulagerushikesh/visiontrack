"""Offline lifecycle diagnosis must explain actual decisions without changing output."""
from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from visiontrack.cli import main
from visiontrack.detection.base import Detection
from visiontrack.lab import (
    DetectionRecord,
    ExperimentManifest,
    SourceManifest,
    create_experiment_bundle,
    detection_payload_sha256,
    initiation,
    run_comparison,
    sha256_json,
)
from visiontrack.lab.initiation import _InitiationObserver, build_initiation_trace
from visiontrack.tracking.config import TrackerConfig
from visiontrack.tracking.tracker import ByteTracker

NOW = "2026-10-30T12:00:00Z"


def bundle_for(tmp_path, scores, *, start=0, overrides=None):
    records = [
        DetectionRecord(frame, None, 7, (10, 10, 30, 50), score, 1)
        for frame, score in enumerate(scores) if score is not None
    ]
    source = SourceManifest.create(
        kind="synthetic", name="initiation-fixture",
        detection_sha256=detection_payload_sha256(records, frame_count=len(scores)),
        ground_truth_sha256=None, video_sha256=None, detector={"name": "fixture"},
        frame_count=len(scores), width=100, height=80, fps=30.,
        coordinate_space="pixel_xyxy", created_at=NOW,
    )
    experiment = ExperimentManifest.create(
        source_id=source.source_id, baseline="baseline",
        variants=({"name": "baseline", "overrides": overrides or {}},),
        metrics=("track_count",), frame_range={"start": start, "end": len(scores)},
        visiontrack_version="0.3.0", git_revision=None,
        environment={"python": "fixture"}, created_at=NOW,
    )
    bundle = create_experiment_bundle(tmp_path, experiment, source, records)
    run_comparison(bundle)
    return bundle


def snapshot(bundle):
    return {p.relative_to(bundle): p.read_bytes() for p in bundle.rglob("*") if p.is_file()}


def test_hand_lifecycle_and_score_dispositions_are_actual_and_read_only(tmp_path):
    bundle = bundle_for(
        tmp_path, [.05, .3, .55, .9, .9, .9, .3, None, None, .9, None],
        overrides={"max_age": 1},
    )
    original = snapshot(bundle)
    trace = build_initiation_trace(bundle, variant="baseline", start=0, end=11)
    assert snapshot(bundle) == original
    assert trace == build_initiation_trace(bundle, variant="baseline", start=0, end=11)
    content = dict(trace)
    assert content.pop("trace_id") == sha256_json(content)
    assert trace["public_output_parity"] == "exact_sha256_match"
    assert trace["accuracy_claim"] is trace["physical_identity_verified"] is False
    assert trace["track_sha256"] == hashlib.sha256(
        original[Path("runs/baseline/tracks.jsonl")],
    ).hexdigest()
    frames = trace["frames"]
    assert [row["detections"][0]["disposition"] for row in frames[:7]] == [
        "below_low_score", "unmatched_low_score", "below_birth_score",
        "spawned_tentative", "matched_tentative_high", "matched_tentative_high",
        "matched_confirmed_low",
    ]
    assert [row["tracks"][0]["event"] for row in frames[3:]] == [
        "born", "tentative_match", "confirmed_now", "updated", "coasting",
        "deleted_expired", "born", "deleted_unconfirmed",
    ]
    assert [row["public_track_ids"] for row in frames] == [
        [], [], [], [], [], [1], [1], [], [], [], [],
    ]
    assert frames[3]["tracks"][0]["birth_frame"] == 3
    assert frames[7]["tracks"][0]["state"] == "confirmed"
    assert frames[7]["tracks"][0]["public"] is False
    assert frames[8]["tracks"][0]["time_since_update"] == 2
    assert frames[10]["tracks"][0]["previous_state"] == "tentative"
    assert frames[9]["tracks"][0]["track_id"] == 2
    for row in frames:
        for detection in row["detections"]:
            assert detection["detection_index"] == 7
            assert "input_offset" not in detection
        for track in row["tracks"]:
            assert track["detection_index"] in (None, 7)
    assert str(tmp_path) not in json.dumps(trace)


def test_warmup_is_not_reset_at_selected_window_and_uses_absolute_frame_indices(tmp_path):
    bundle = bundle_for(tmp_path, [.9] * 9, start=3)
    trace = build_initiation_trace(bundle, variant="baseline", start=6, end=8)
    assert [row["frame_index"] for row in trace["frames"]] == [6, 7]
    first = trace["frames"][0]
    assert first["tracks"][0]["event"] == "updated"
    assert first["tracks"][0]["hits"] == 4
    assert first["tracks"][0]["birth_frame"] == 3
    assert first["detections"][0]["disposition"] == "matched_confirmed_high"
    assert first["public_track_ids"] == [1]
    assert trace["replay_frame_range"] == {"start": 3, "end": 9}


def test_inclusive_score_boundaries_and_matching_precedes_birth_threshold(tmp_path):
    bundle = bundle_for(tmp_path, [.1, .5, .6, .5, .1, .55], overrides={"n_init": 2})
    trace = build_initiation_trace(bundle, variant="baseline", start=0, end=6)
    assert [f["detections"][0]["disposition"] for f in trace["frames"]] == [
        "unmatched_low_score", "below_birth_score", "spawned_tentative",
        "matched_tentative_high", "matched_confirmed_low", "matched_confirmed_high",
    ]
    low_birth = bundle_for(tmp_path / "low-birth", [.45], overrides={"new_track_thresh": .4})
    row = build_initiation_trace(low_birth, variant="baseline", start=0, end=1)["frames"][0]
    assert row["detections"][0]["disposition"] == "unmatched_low_score"
    assert not row["tracks"]


def test_n_init_one_records_actual_tentative_birth_not_assumed_confirmation(tmp_path):
    bundle = bundle_for(tmp_path, [.9, .9], overrides={"n_init": 1})
    trace = build_initiation_trace(bundle, variant="baseline", start=0, end=2)
    assert trace["frames"][0]["tracks"][0]["state"] == "tentative"
    assert trace["frames"][0]["public_track_ids"] == []
    assert trace["frames"][1]["tracks"][0]["event"] == "confirmed_now"


@pytest.mark.parametrize("start,end", [(0, 0), (-1, 1), (0, 201), (True, 2), (0., 2)])
def test_invalid_window_refused_before_bundle_access(start, end):
    with pytest.raises(ValueError, match="integer trace window"):
        build_initiation_trace("not-a-bundle", variant="baseline", start=start, end=end)


def test_unknown_variant_outside_window_and_corrupt_evidence_are_rejected(tmp_path):
    bundle = bundle_for(tmp_path, [.9] * 6, start=2)
    with pytest.raises(ValueError, match="not declared"):
        build_initiation_trace(bundle, variant="../escape", start=2, end=3)
    for start, end in [(0, 2), (5, 7)]:
        with pytest.raises(ValueError, match="inside"):
            build_initiation_trace(bundle, variant="baseline", start=start, end=end)
    (bundle / "inputs/detections.jsonl").write_text("corrupt\n")
    with pytest.raises(ValueError, match="SHA-256"):
        build_initiation_trace(bundle, variant="baseline", start=2, end=3)


def test_validly_rehashed_but_wrong_saved_output_fails_replay_check(tmp_path):
    bundle = bundle_for(tmp_path, [.9] * 4)
    track_path = bundle / "runs/baseline/tracks.jsonl"
    track_path.write_bytes(b"")
    run_path = bundle / "runs/baseline/run.json"
    data = json.loads(run_path.read_text())
    data.update(track_sha256=hashlib.sha256(b"").hexdigest(), observation_count=0)
    data.pop("run_id")
    data["run_id"] = sha256_json(data)
    run_path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="replay differs"):
        build_initiation_trace(bundle, variant="baseline", start=0, end=1)


def test_row_limit_and_changed_stage_contract_fail_closed(tmp_path, monkeypatch):
    bundle = bundle_for(tmp_path, [.9] * 3)
    monkeypatch.setattr(initiation, "MAX_TRACE_ROWS", 1)
    with pytest.raises(ValueError, match="smaller window"):
        build_initiation_trace(bundle, variant="baseline", start=0, end=3)
    monkeypatch.setattr(initiation, "MAX_TRACE_ROWS", 20_000)
    monkeypatch.setattr(initiation, "_STAGES", ("confirmed_high",))
    with pytest.raises(ValueError, match="stage contract changed"):
        build_initiation_trace(bundle, variant="baseline", start=0, end=3)


def test_cli_text_json_and_errors_leave_bundle_unchanged(tmp_path, capsys):
    bundle = bundle_for(tmp_path, [.55, .9, .9, .9])
    original = snapshot(bundle)
    args = ["lab-initiation", str(bundle), "--variant", "baseline", "--start", "0", "--end", "4"]
    assert main(args) == 0
    out = capsys.readouterr()
    assert not out.err
    assert "below new-track score" in out.out
    assert "confirmed_now" in out.out
    assert "Read-only: nothing was written" in out.out
    assert main([*args, "--json"]) == 0
    out = capsys.readouterr()
    assert not out.err
    trace = json.loads(out.out)
    assert trace["schema"] == "visiontrack.initiation-trace/v1"
    assert main([*args, "--end", "900", "--json"]) == 2
    out = capsys.readouterr()
    assert out.err.startswith("error:")
    assert out.out == ""
    assert snapshot(bundle) == original


@pytest.mark.parametrize("overrides", [
    {}, {"n_init": 1}, {"max_age": 1}, {"use_mahalanobis_gating": False},
    {"use_giou": True}, {"w_unc": .2}, {"w_ocm": .2}, {"use_oru": True},
    {"class_aware": False},
])
def test_observer_exact_output_and_input_parity_with_competing_tracks(overrides):
    config = replace(TrackerConfig(), **overrides)
    observed = _InitiationObserver(config, offset=0, start=0, end=25)
    plain = ByteTracker(replace(config))
    rng = np.random.default_rng(19)
    for frame in range(25):
        dets = [
            Detection(np.array([x, 10., x + 20., 50.]), score, class_id)
            for x, score, class_id in [
                (10. + frame, .3 if frame % 6 == 0 else .9, 1),
                (36. - frame, .55 if frame % 4 == 0 else .95, 2),
                (float(rng.integers(0, 70)), .05, 1),
            ] if frame not in (5, 6, 20)
        ]
        before = [det.xyxy.copy() for det in dets]
        expected = plain.update(dets)
        actual = observed.update(dets)
        assert len(expected) == len(actual)
        for left, right in zip(expected, actual, strict=True):
            assert (left.frame, left.track_id, left.score, left.class_id) == (
                right.frame, right.track_id, right.score, right.class_id,
            )
            assert left.xyxy.tobytes() == right.xyxy.tobytes()
        for det, box in zip(dets, before, strict=True):
            assert det.xyxy.tobytes() == box.tobytes()
