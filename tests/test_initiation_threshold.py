"""Hand fixtures and doubles check the method before actual study execution."""
import copy
import itertools

import pytest

from experiments.initiation_threshold import (
    CASES,
    SCORES,
    SPEEDS,
    crossing_score,
    run_cell,
    scene,
    score_run,
)


def event(time, y=300):
    return {"estimated_frame": time, "crossing_y": y}


def test_crossing_matching_is_one_to_one_and_maximum_cardinality():
    # Greedily assigning the first truth to prediction 0 would miss truth 2.
    assert crossing_score([event(4), event(5.5)], [event(4.7), event(3.2)]) == {
        "true_events": 2, "predicted_events": 2, "tp": 2, "fp": 0, "fn": 0}
    assert crossing_score([event(4)], [event(4), event(4)]) == {
        "true_events": 1, "predicted_events": 2, "tp": 1, "fp": 1, "fn": 0}


def test_crossing_matching_rejects_wrong_lane_and_time():
    assert crossing_score([event(4)], [event(4, 370), event(6)])["tp"] == 0
    assert crossing_score([], [event(4)])["fp"] == 1
    assert crossing_score([], [])["tp"] == 0
    assert crossing_score([event(4)], [])["fn"] == 1
    with pytest.raises(ValueError, match="capacity"):
        crossing_score([event(1)] * 3, [])


def test_all_registered_inputs_have_separate_finite_truth_and_proposals():
    cells = list(itertools.product(CASES, SCORES, SPEEDS))
    assert len(cells) == 54
    for case, confidence, speed in cells:
        rows = scene(case, confidence, speed)
        assert [r["frame"] for r in rows] == list(range(len(rows)))
        assert rows == scene(case, confidence, speed)
        assert len(rows) == (48 if case == "long_absence" else 12)
        for row in rows:
            for truth in row["truth"]:
                for detection in row["detections"]:
                    assert truth["xyxy"] is not detection["xyxy"]


def test_identical_proposals_do_not_establish_truth():
    for confidence, speed in itertools.product(SCORES, SPEEDS):
        true = scene("steady_true", confidence, speed)
        false = scene("persistent_false", confidence, speed)
        assert [r["detections"] for r in true] == [r["detections"] for r in false]
        assert all(r["truth"] for r in true)
        assert not any(r["truth"] for r in false)


def test_gaps_and_score_transition_are_fixed():
    assert not scene("confirmation_gap", .57, 2)[1]["detections"]
    gap = scene("confirmed_gap", .57, 2)
    assert not gap[5]["detections"] and not gap[6]["detections"]
    late = scene("late_strong", .57, 2)
    assert [r["detections"][0]["score"] for r in late] == [.57] * 4 + [.9] * 8
    long = scene("long_absence", .57, 2)
    assert all(not r["truth"] and not r["detections"] for r in long[8:40])
    assert len([r for r in long if r["truth"]]) == 16


@pytest.mark.parametrize("args", [("unknown", .57, 2), ("steady_true", .56, 2),
                                  ("steady_true", .57, 3)])
def test_unregistered_cells_fail(args):
    with pytest.raises(ValueError, match="unregistered"):
        scene(*args)


def output_fixture(inputs, *, include_truth=True, include_false=False):
    outputs = []
    for row in inputs:
        observations = []
        if include_truth:
            observations = [{**copy.deepcopy(t), "score": .9, "class_id": 2}
                            for t in row["truth"] if row["frame"] >= 2]
        if include_false and row["frame"] >= 2:
            observations.append({"id": 2, "xyxy": [480 + row["frame"] * 2 - 9,
                                                     350, 520 + row["frame"] * 2 - 9, 390],
                                 "score": .57, "class_id": 2})
        outputs.append({"frame": row["frame"], "births": 2 if row["frame"] == 0 else 0,
                        "observations": observations})
    return outputs


def test_hand_supplied_outputs_separate_false_boxes_and_crossings():
    inputs = scene("steady_true", .57, 2)
    outputs = output_fixture(inputs, include_false=True)
    score = score_run(inputs, outputs)
    assert score["mot"]["false_negatives"] == 2
    assert score["mot"]["true_positives"] == score["mot"]["false_positives"] == 10
    assert score["ids_with_false_positive_boxes"] == 1
    assert score["confirmation_delays"][0]["delay_frames"] == 2
    assert score["crossings"] == {"true_events": 1, "predicted_events": 2,
                                  "tp": 1, "fp": 1, "fn": 0}


def test_confirmation_delay_is_null_when_never_matched():
    inputs = scene("steady_true", .57, 2)
    score = score_run(inputs, output_fixture(inputs, include_truth=False))
    assert score["confirmation_delays"][0]["delay_frames"] is None
    assert score["unconfirmed_births"] == 2
    assert score["crossings"]["fn"] == 1


@pytest.mark.parametrize("bad", ["missing", "reordered", "misnumbered"])
def test_scoring_requires_complete_ordered_frames(bad):
    inputs = scene("steady_true", .57, 2)
    outputs = output_fixture(inputs)
    if bad == "missing":
        outputs.pop()
    elif bad == "reordered":
        outputs[0], outputs[1] = outputs[1], outputs[0]
    else:
        inputs[0]["frame"] = outputs[0]["frame"] = 1
    with pytest.raises(ValueError, match="ordered"):
        score_run(inputs, outputs)


class EmptyTracker:
    def __init__(self, config):
        self.cfg = config
        self.reset()

    def reset(self):
        self.frame_index = -1
        self._next_id = 1

    def update(self, detections):
        self.frame_index += 1
        # Modifying a handed-off array cannot alter input or the other variant.
        for detection in detections:
            detection.xyxy[:] = 0
        return []


def test_paired_adapter_copies_inputs_and_changes_only_initiation():
    configs = []
    def factory(config):
        configs.append(config)
        return EmptyTracker(config)
    inputs, runs, result = run_cell("steady_true", .57, 2, factory)
    assert inputs == scene("steady_true", .57, 2)
    assert runs["baseline"] == runs["candidate"]
    assert result["baseline"] == result["candidate"]
    assert [c.new_track_thresh for c in configs] == [.6, .6, .55, .55]
    configs[0].new_track_thresh = .55
    assert configs[0] == configs[2]


def test_repeatability_failure_stops_cell():
    class BadReset(EmptyTracker):
        def reset(self):
            super().reset()
            self._next_id = getattr(self, "attempt", 0) + 1
            self.attempt = self._next_id

        def update(self, detections):
            self.frame_index += 1
            self._next_id += self.attempt
            return []
    with pytest.raises(ValueError, match="repeatability"):
        run_cell("steady_true", .57, 2, BadReset)
