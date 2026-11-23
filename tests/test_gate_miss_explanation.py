"""R1 replay: recording the gate must not change tracking, and its split must add up."""
import numpy as np

import experiments.gate_miss_explanation as g
from experiments.svmot_gate import replay


def _detections():
    rows = []
    for n in range(1, 13):
        rows.append((n, 100.0, 50.0 + 6 * n, 140.0, 80.0 + 6 * n, 0.9, 0))
        rows.append((n, 400.0, 300.0, 430.0, 340.0, 0.8, 0))
    rows.append((13, 100.0, 128.0, 180.0, 158.0, 0.9, 0))  # same place, much wider: gate refuses
    rows.append((13, 400.0, 300.0, 430.0, 340.0, 0.8, 0))
    return np.array(rows)


def test_recording_does_not_change_the_default_tracker_output():
    array = _detections()
    recorded, _ = g.gate_on_replay(array, 13)
    assert recorded == replay(array, 13, "gate_on")


def test_refusals_split_exactly_into_four_box_terms():
    _, kf = g.gate_on_replay(_detections(), 13)
    assert kf.refusals, "the widened box should be refused by the gate"
    refusal = kf.refusals[-1]
    assert refusal["frame"] == 13
    assert refusal["iou"] >= 0.3
    assert abs(sum(refusal["terms"].values()) - refusal["d2"]) < 1e-9 * refusal["d2"]
    assert max(refusal["terms"], key=refusal["terms"].get) == "aspect"
    assert kf.diagonal_error == 0.0


def test_missed_crossing_is_linked_to_the_refusal_on_that_vehicle():
    reference_boxes = {(12, 7): [100.0, 122.0, 140.0, 152.0], (13, 7): [100.0, 128.0, 180.0, 158.0]}
    reference = [{"frame": 13, "id": 7, "x": 140.0, "y": 140.0, "dir": "A->B"}]
    refusal = {"frame": 13, "d2": 20.0, "iou": 0.5, "box": [100.0, 128.0, 180.0, 158.0],
               "terms": {"centre_x": 1.0, "centre_y": 1.0, "aspect": 17.0, "height": 1.0}}
    rows = g.explain(reference_boxes, reference, [0], [refusal], rescued={0})
    assert rows[0]["refusal"]["driver"] == "aspect"
    assert rows[0]["refusal"]["frames_before_crossing"] == 0
    assert rows[0]["speed_px_per_frame"] == float(np.hypot(20.0, 6.0))  # centre step
    assert rows[0]["height_px"] == 30.0
    assert rows[0]["rescued_by_gate_off"] is True
