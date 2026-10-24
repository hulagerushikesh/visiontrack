"""Reference-parity regressions retaining the historical counterexamples."""
import numpy as np
import pytest

from experiments.mot17_metric_crosscheck import data_for_reference, reference_api
from visiontrack.eval._legacy_hota import compute_hota as legacy_hota
from visiontrack.eval._legacy_mot import MotAccumulator as LegacyAccumulator
from visiontrack.eval.hota import compute_hota
from visiontrack.eval.mot import MotAccumulator


def box(x):
    return [float(x), 0., float(x + 10), 10.]


def make_data(records):
    pytest.importorskip("trackeval")
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
    legacy = legacy_hota(frames, alphas=np.array([0.5]))
    corrected = compute_hota(frames, alphas=np.array([0.5]))
    # Legacy threshold-dependent matching chooses the .515 diagonal edge.
    # Reference alignment*similarity chooses the two .4925 off-diagonal edges
    # before thresholding; neither is valid at alpha=.5. This is NOT a tie.
    assert legacy.det_a == pytest.approx(1 / 3)
    assert ref["HOTA_TP"][9] == 0
    assert ref["DetA"][9] == 0
    assert corrected.det_a == ref["DetA"][9]
    assert corrected.hota == ref["HOTA"][9]
    similarity = data["similarity_scores"][0]
    assert similarity[0, 0] > 0.5
    assert similarity[0, 1] < 0.5 and similarity[1, 0] < 0.5


def test_clear_stale_correspondence_can_preempt_a_current_one():
    data, frames = make_data([
        ([1, 2], [box(0), box(4)], [10], [box(0)]),
        ([1, 2], [box(0), box(4)], [10], [box(4)]),
        ([1, 2], [box(0), box(4)], [10, 11], [box(2), box(0)]),
    ])
    accumulator, historical = MotAccumulator(), LegacyAccumulator()
    for frame in frames:
        accumulator.update(*frame)
        historical.update(*frame)
    te, _, _ = reference_api()
    reference = te.metrics.CLEAR(dict(THRESHOLD=0.5, PRINT_CONFIG=False)).eval_sequence(data)
    assert historical.result().true_positives == 3
    assert historical.result().id_switches == 0
    assert accumulator.result().true_positives == reference["CLR_TP"]
    assert accumulator.result().id_switches == reference["IDSW"]
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
    assert accumulator.result().fragmentations == reference["Frag"]
    assert reference["Frag"] == 0  # never matched again, no resumed segment
