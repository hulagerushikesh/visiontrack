"""Re-score saved output only; keep old packets and expose the new verdict."""
import copy
import json
import sys

import pytest

from experiments import mot17_metric_rescore as scorer
from experiments.mot17_case_baseline import encoded, run_once
from experiments.mot17_metric_crosscheck import crosscheck, reference_api
from tests.test_mot17_case_trace import Sequence


def fixture(tmp_path):
    directory = tmp_path / "old"
    run_once(Sequence(), directory)
    return {f"run-1/{name}": (directory / name).read_bytes()
            for name in ("scored.jsonl", "failures.jsonl", "summary.json")}


def test_rescore_does_not_run_tracker_and_preserves_input(tmp_path, monkeypatch):
    from visiontrack.tracking.tracker import ByteTracker
    contents = fixture(tmp_path)
    original = copy.deepcopy(contents)

    def forbidden(*args, **kwargs):
        pytest.fail("a metric re-score must never run a tracker")
    monkeypatch.setattr(ByteTracker, "update", forbidden)
    rows = []
    result, changes = scorer.rescore(contents, rows.append)
    assert contents == original
    assert result["metrics"]["FN"] == len([r for r in rows if r["event_type"] == "miss"])
    assert result["metrics"]["frames"] == 6
    assert changes["new_evaluator"] == "visiontrack.metrics/v2"
    assert changes["historical_records_rewritten"] is False
    pytest.importorskip("trackeval")
    te, iou, _ = reference_api()
    current = dict(contents)
    current["run-1/summary.json"] = encoded(result).encode()
    assert crosscheck(current, te, iou)["all_reported_checks_agree"] is True


def test_removed_historical_failure_is_retained_in_delta(tmp_path):
    contents = fixture(tmp_path)
    old = dict(event_type="fragmentation", source_frame=6, frame_index=5,
               gt_id=7, hyp_id=None, previous_hyp_id=1, gt_box=None, hyp_box=None)
    contents["run-1/failures.jsonl"] += encoded(old).encode()
    _, changes = scorer.rescore(contents, lambda r: None)
    assert changes["removed_events"] == [old]
    assert changes["new_counts"].get("fragmentation", 0) == 0


def test_noncontiguous_saved_frames_rejected(tmp_path):
    contents = fixture(tmp_path)
    rows = [json.loads(s) for s in contents["run-1/scored.jsonl"].splitlines()]
    rows[2]["source_frame"] = 4
    contents["run-1/scored.jsonl"] = "".join(encoded(r) for r in rows).encode()
    with pytest.raises(ValueError, match="non-contiguous"):
        scorer.rescore(contents, lambda r: None)


def test_cli_fails_on_nonagreement_not_just_execution_success(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["rescore", "--baseline", "old", "--output", "new"])
    monkeypatch.setattr(scorer, "execute", lambda *args: False)
    with pytest.raises(SystemExit) as exit_info:
        scorer.main()
    assert exit_info.value.code == 2


def test_existing_output_refused_before_input_read(tmp_path):
    with pytest.raises(ValueError, match="new output"):
        scorer.execute(tmp_path / "missing", tmp_path)
