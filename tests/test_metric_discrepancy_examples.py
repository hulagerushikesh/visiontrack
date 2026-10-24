"""Legacy-vs-reference counterexamples, not approval of the legacy definitions.

These characterize the newly found discrepancy while the baseline stays sealed.
Replace these inequalities with reference-parity regressions in the separately
reviewed evaluator correction; do not preserve a bug as a permanent contract.
"""
import numpy as np
import pytest

from experiments.mot17_metric_crosscheck import data_for_reference, reference_api
from visiontrack.eval.hota import compute_hota
from visiontrack.eval.mot import MotAccumulator

pytest.importorskip("trackeval")


def box(x):
    return [float(x), 0., float(x + 10), 10.]


def make_data(records):
    _, iou, _ = reference_api()
    rows, frames = [], []
    for frame, (g, gb, t, tb) in enumerate(records, start=1):
        rows.append(dict(source_frame=frame, gt_ids=g, gt_xyxy=gb,
                         track_ids=t, track_xyxy=tb))
        frames.append((np.array(g, dtype=int), np.array(gb).reshape(-1, 4),
                       np.array(t, dtype=int), np.array(tb).reshape(-1, 4)))
    return data_for_reference(rows, iou), frames


def test_hota_algorithms_disagree_without_a_hungarian_tie():
    data, frames = make_data([([1, 2], [box(0), box(6.6)],
                               [10, 11], [box(3.2), box(-3.4)])])
    te, _, _ = reference_api()
    ref = te.metrics.HOTA().eval_sequence(data)
    legacy = compute_hota(frames, alphas=np.array([0.5]))
    # Legacy threshold-dependent matching chooses the .515 diagonal edge.
    # Reference alignment*similarity chooses the two .4925 off-diagonal edges
    # before thresholding; neither is valid at alpha=.5. This is NOT a tie.
    assert legacy.det_a == pytest.approx(1 / 3)
    assert ref["HOTA_TP"][9] == 0
    assert ref["DetA"][9] == 0
    similarity = data["similarity_scores"][0]
    assert similarity[0, 0] > 0.5
    assert similarity[0, 1] < 0.5 and similarity[1, 0] < 0.5


def test_clear_stale_correspondence_can_preempt_a_current_one():
    data, frames = make_data([
        ([1, 2], [box(0), box(4)], [10], [box(0)]),
        ([1, 2], [box(0), box(4)], [10], [box(4)]),
        ([1, 2], [box(0), box(4)], [10, 11], [box(2), box(0)]),
    ])
    accumulator = MotAccumulator()
    for frame in frames:
        accumulator.update(*frame)
    te, _, _ = reference_api()
    reference = te.metrics.CLEAR(dict(THRESHOLD=0.5, PRINT_CONFIG=False)).eval_sequence(data)
    assert accumulator.result().true_positives == 3
    assert accumulator.result().id_switches == 0
    assert reference["CLR_TP"] == 4
    assert reference["IDSW"] == 1


def test_clear_trailing_loss_is_not_reference_fragmentation():
    data, frames = make_data([
        ([1], [box(0)], [10], [box(0)]),
        ([1], [box(0)], [10], [box(0)]),
        ([1], [box(0)], [], []),
    ])
    accumulator = MotAccumulator()
    for frame in frames:
        accumulator.update(*frame)
    te, _, _ = reference_api()
    reference = te.metrics.CLEAR(dict(THRESHOLD=0.5, PRINT_CONFIG=False)).eval_sequence(data)
    assert accumulator.result().fragmentations == 1  # current interruption definition
    assert reference["Frag"] == 0  # never matched again, no resumed segment
