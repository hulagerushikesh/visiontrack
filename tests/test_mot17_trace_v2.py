"""The same event and prior-match rule select a window, not a new attractive failure."""
import copy
import json

import pytest

from experiments import mot17_trace_v2 as trace
from experiments.mot17_case_baseline import encoded
from tests.test_mot17_case_trace import Sequence, contents
from visiontrack.eval.definitions import EVALUATOR


def selected_fixture():
    event = dict(event_type="id_switch", source_frame=6, gt_id=7,
                 hyp_id=2, previous_hyp_id=1)
    rows = [dict(source_frame=f, gt_ids=[7]) for f in range(1, 7)]
    old = dict(event_type="miss", source_frame=5, gt_id=7)
    new = [dict(event_type="miss", source_frame=f, gt_id=7) for f in (3, 4, 5)]
    saved = {"run-1/summary.json": encoded(dict(first_chronological_switch=event)).encode(),
             "run-1/scored.jsonl": "".join(encoded(r) for r in rows).encode(),
             "run-1/failures.jsonl": (encoded(old) + encoded(event)).encode()}
    packet = {"method.json": encoded(dict(evaluator=EVALUATOR)).encode(),
              "reference-check.json": encoded(dict(
                  all_reported_checks_agree=True, num_checks=45)).encode(),
              "score.json": encoded(dict(metrics={})).encode(),
              "failures.jsonl": "".join(encoded(r) for r in [*new, event]).encode()}
    return saved, packet


def test_same_event_rule_uses_v2_history_and_leaves_original_untouched():
    saved, packet = selected_fixture()
    original = copy.deepcopy((saved, packet))
    current, chosen = trace.prepare(saved, packet)
    assert chosen["source_window"] == [1, 9]
    assert chosen["last_scored_match"] == 2
    assert chosen["legacy_last_scored_match"] == 4
    assert chosen["legacy_source_window"] == [3, 9]
    assert current["run-1/scored.jsonl"] is saved["run-1/scored.jsonl"]
    assert (saved, packet) == original


def test_different_event_cannot_be_substituted():
    saved, packet = selected_fixture()
    rows = [json.loads(line) for line in packet["failures.jsonl"].splitlines()]
    rows[-1]["gt_id"] = 8
    packet["failures.jsonl"] = "".join(encoded(r) for r in rows).encode()
    with pytest.raises(ValueError, match="same first event"):
        trace.prepare(saved, packet)


def test_overview_uses_actual_calls_and_does_not_conflate_missing_with_alive(tmp_path):
    saved = contents(tmp_path)
    out = tmp_path / "replay"
    out.mkdir()
    chosen = dict(source_window=[3, 4], event=dict(previous_hyp_id=1))
    trace.replay(Sequence(), saved, chosen, out)
    result = trace.overview(out / "events.jsonl", chosen)
    assert result["old_id_continuously_updated_and_public"] is True
    assert result["event_counts"]["_match"] == 6
    assert result["physical_identity_established"] is False
    chosen["event"]["previous_hyp_id"] = 999
    assert trace.overview(out / "events.jsonl", chosen)[
        "old_id_continuously_updated_and_public"] is False
    chosen["source_window"] = [2, 4]
    with pytest.raises(ValueError, match="window incomplete"):
        trace.overview(out / "events.jsonl", chosen)


def test_existing_output_refused_before_inputs_read(tmp_path):
    with pytest.raises(ValueError, match="new output"):
        trace.execute(tmp_path / "b", tmp_path / "r", tmp_path / "p", "0" * 64,
                      tmp_path / "c", tmp_path / "l", tmp_path)
