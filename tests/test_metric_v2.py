"""Crowded, empty, threshold and geometry regressions for metric definitions v2."""
from dataclasses import asdict

import numpy as np
import pytest

from experiments.mot17_metric_crosscheck import CLEAR_FIELDS, data_for_reference, reference_api
from tests.test_metric_discrepancy_examples import box, make_data
from visiontrack.eval.geometry import metric_iou
from visiontrack.eval.hota import compute_hota, compute_identity
from visiontrack.eval.mot import MotAccumulator


def compare(records):
    pytest.importorskip("trackeval")
    data, frames = make_data(records)
    te, _, _ = reference_api()
    reference = te.metrics.CLEAR(dict(PRINT_CONFIG=False)).eval_sequence(data)
    acc = MotAccumulator()
    for frame in frames:
        acc.update(*frame)
    result = asdict(acc.result())
    for key, field in CLEAR_FIELDS.items():
        # This installed reference's all-empty early return leaves metadata
        # CLR_Frames at zero. Our API always reports frames actually received.
        if key == "CLR_Frames" and (not data["num_gt_dets"] or not data["num_tracker_dets"]):
            assert result[field] == len(frames)
            continue
        assert result[field] == pytest.approx(reference[key], abs=1e-10), key
    hota = compute_hota(frames)
    rh = te.metrics.HOTA().eval_sequence(data)
    np.testing.assert_allclose(hota.per_alpha, rh["HOTA"], atol=1e-10, rtol=0)
    for field, key in (("det_a", "DetA"), ("ass_a", "AssA"),
                       ("det_re", "DetRe"), ("det_pr", "DetPr"),
                       ("ass_re", "AssRe"), ("ass_pr", "AssPr")):
        assert getattr(hota, field) == pytest.approx(np.mean(rh[key]), abs=1e-10)
    ri = te.metrics.Identity(dict(PRINT_CONFIG=False)).eval_sequence(data)
    assert compute_identity(frames).idf1 == pytest.approx(ri["IDF1"], abs=1e-10)


@pytest.mark.parametrize("seed", range(8))
def test_crowded_random_sequences_against_reference(seed):
    rng = np.random.default_rng(seed)
    records = []
    for frame in range(20):
        positions = rng.uniform(0, 20, 4)
        gt = [box(x) for x in positions]
        kept = [i for i in range(4) if rng.random() > 0.2]
        records.append(([1, 2, 3, 4], gt,
                        [10 + i + (10 if frame >= 10 and i == 0 else 0) for i in kept],
                        [box(positions[i] + rng.uniform(-3, 3)) for i in kept]))
    compare(records)


@pytest.mark.parametrize("records", [
    [([], [], [], [])] * 3,
    [([1], [box(0)], [], [])] * 3,
    [([], [], [10], [box(0)])] * 3,
    [([1], [box(0)], [10], [box(0)]), ([], [], [], []),
     ([1], [box(0)], [10], [box(0)])],
    [([1, 2], [box(0), box(0)], [10, 11], [box(0), box(0)])] * 4,
])
def test_empty_frames_and_deterministic_ties(records):
    compare(records)


def test_eighty_percent_is_partially_not_mostly_tracked():
    acc = MotAccumulator()
    for frame in range(5):
        acc.update(np.array([1]), np.array([box(0)]), np.array([10]),
                   np.array([box(0 if frame < 4 else 100)]))
    assert acc.result().mostly_tracked == 0
    assert acc.result().partially_tracked == 1


@pytest.mark.parametrize("alphas", [[], [np.nan], [-0.1], [0], [1.1], [[0.5]]])
def test_invalid_hota_thresholds_rejected(alphas):
    with pytest.raises(ValueError, match="alphas"):
        compute_hota([], np.array(alphas))


def test_metric_geometry_has_no_tracker_area_floor():
    tiny = np.array([[0., 0., 1e-4, 1e-4]])
    assert metric_iou(tiny, tiny).tolist() == [[1.]]
    pytest.importorskip("trackeval")
    _, iou, _ = reference_api()
    np.testing.assert_array_equal(metric_iou(tiny, tiny), iou(tiny, tiny, "x0y0x1y1"))


def test_duplicate_frame_ids_rejected():
    with pytest.raises(ValueError, match="unique aligned"):
        MotAccumulator().update(np.array([1, 1]), np.array([box(0), box(1)]),
                                np.array([10]), np.array([box(0)]))


def test_threshold_inclusion_and_reference_iou_conversion():
    pytest.importorskip("trackeval")
    _, iou, _ = reference_api()
    rows = [dict(source_frame=1, gt_ids=[1], gt_xyxy=[[0., 0., 3., 1.]],
                 track_ids=[10], track_xyxy=[[1., 0., 4., 1.]])]
    data = data_for_reference(rows, iou)
    assert data["similarity_scores"][0].tolist() == [[0.5]]
    acc = MotAccumulator()
    assert acc.update(np.array([1]), np.array(rows[0]["gt_xyxy"]),
                      np.array([10]), np.array(rows[0]["track_xyxy"])) == []
