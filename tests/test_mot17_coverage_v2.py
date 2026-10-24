"""Versioned coverage must reconcile exact saved events without rerunning tracking."""
import copy
import json
from dataclasses import asdict

import pytest

from experiments import mot17_coverage_v2 as coverage
from experiments.mot17_case_baseline import encoded, run_once, sha, write_json
from experiments.mot17_metric_rescore import rescore
from tests.test_mot17_case_trace import Sequence
from visiontrack.eval.definitions import EVALUATOR
from visiontrack.tracking.config import TrackerConfig


def fixture(tmp_path):
    directory = tmp_path / "run"
    run_once(Sequence(), directory)
    contents = {f"run-1/{name}": (directory / name).read_bytes()
                for name in ("raw.jsonl", "scored.jsonl", "failures.jsonl", "summary.json")}
    contents["plan.json"] = encoded(dict(tracker_config=asdict(TrackerConfig()),
                                         scope=dict(source_frames=[1, 6]))).encode()
    failures = []
    summary, _ = rescore(contents, failures.append)
    packet = {"method.json": encoded(dict(evaluator=EVALUATOR)).encode(),
              "reference-check.json": encoded(dict(
                  all_reported_checks_agree=True, num_checks=45)).encode(),
              "score.json": encoded(summary).encode(),
              "failures.jsonl": "".join(encoded(f) for f in failures).encode()}
    return contents, packet


def test_v2_partition_reconciles_and_does_not_run_tracker(tmp_path, monkeypatch):
    from visiontrack.tracking.tracker import ByteTracker
    contents, packet = fixture(tmp_path)
    original = copy.deepcopy((contents, packet))

    def forbidden(*args, **kwargs):
        pytest.fail("coverage must not run tracking")

    monkeypatch.setattr(ByteTracker, "update", forbidden)
    misses = []
    result = coverage.analyze(contents, packet, misses.append)
    assert result["schema"] == "visiontrack.mot17-case-coverage/v2"
    assert result["evaluator"] == EVALUATOR
    assert result["preprocessing"] == "visiontrack.mot17-preprocessing/v2"
    assert sum(result["fn_groups"].values()) == len(misses) == result["metrics"]["FN"]
    assert result["tracker_executed"] is result["causal_attribution"] is False
    assert (contents, packet) == original


def test_removed_legacy_miss_is_recorded_not_rewritten(tmp_path):
    contents, packet = fixture(tmp_path)
    contents["run-1/failures.jsonl"] += encoded(dict(
        event_type="miss", source_frame=6, gt_id=999)).encode()
    result = coverage.analyze(contents, packet, lambda r: None)
    assert result["miss_correspondence"]["removed"] == [(6, 999)]
    assert result["historical_records_rewritten"] is False


@pytest.mark.parametrize("kind", ["canonical", "frames", "evaluator", "reference", "score"])
def test_changed_or_unverified_receipt_rejected(tmp_path, kind):
    contents, packet = fixture(tmp_path)
    if kind == "canonical":
        packet["failures.jsonl"] = b""
    elif kind == "frames":
        rows = [json.loads(line) for line in contents["run-1/scored.jsonl"].splitlines()]
        rows[1]["source_frame"] = 9
        contents["run-1/scored.jsonl"] = "".join(encoded(r) for r in rows).encode()
    elif kind == "evaluator":
        packet["method.json"] = encoded(dict(evaluator="visiontrack.metrics/v1")).encode()
    elif kind == "reference":
        packet["reference-check.json"] = encoded(dict(
            all_reported_checks_agree=False, num_checks=45)).encode()
    else:
        score = json.loads(packet["score.json"])
        score["metrics"]["FN"] += 1
        packet["score.json"] = encoded(score).encode()
    with pytest.raises(ValueError):
        coverage.analyze(contents, packet, lambda r: None)


def packet(tmp_path):
    write_json(tmp_path / "summary.json", dict(pass_check=True))
    write_json(tmp_path / "manifest.json", {"summary.json": dict(
        bytes=(tmp_path / "summary.json").stat().st_size,
        sha256=sha(tmp_path / "summary.json"))})
    return sha(tmp_path / "manifest.json")


def test_packet_tampering_rejected(tmp_path):
    digest = packet(tmp_path)
    assert "summary.json" in coverage.read_packet(tmp_path, digest)
    (tmp_path / "summary.json").write_bytes(b"changed")
    with pytest.raises(ValueError, match="changed"):
        coverage.read_packet(tmp_path, digest)


def test_packet_symlinks_rejected(tmp_path):
    write_json(tmp_path / "summary.json", dict(pass_check=True))
    link = tmp_path / "other.json"
    link.symlink_to(tmp_path / "summary.json")
    write_json(tmp_path / "manifest.json", {"other.json": dict(bytes=1, sha256="0" * 64)})
    digest = sha(tmp_path / "manifest.json")
    with pytest.raises(ValueError, match="invalid packet"):
        coverage.read_packet(tmp_path, digest)


def test_existing_output_refused_before_reading(tmp_path):
    with pytest.raises(ValueError, match="new output"):
        coverage.execute(tmp_path / "b", tmp_path / "r", tmp_path / "p", "0" * 64, tmp_path)
