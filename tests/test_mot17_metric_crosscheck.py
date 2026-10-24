"""Reference-side geometry and fixed-tolerance metric checks on authored data."""
import json

import numpy as np
import pytest

from experiments import mot17_metric_crosscheck as check
from experiments.mot17_case_baseline import encoded, run_once
from tests.test_mot17_case_trace import Sequence

pytest.importorskip("trackeval")


@pytest.fixture
def saved(tmp_path):
    directory = tmp_path / "baseline"
    run_once(Sequence(), directory)
    return {f"run-1/{name}": (directory / name).read_bytes()
            for name in ("summary.json", "scored.jsonl")}


def test_authored_cold_start_metrics_agree_without_tracker_rerun(saved, monkeypatch):
    te, iou, _ = check.reference_api()
    from visiontrack.core import geometry
    from visiontrack.tracking.tracker import ByteTracker

    def forbidden(*args, **kwargs):
        raise AssertionError("must not run our tracker or our geometry in the crosscheck")
    monkeypatch.setattr(ByteTracker, "update", forbidden)
    monkeypatch.setattr(geometry, "iou_matrix", forbidden)
    result = check.crosscheck(saved, te, iou)
    assert result["all_reported_checks_agree"] is True
    assert result["num_checks"] == 45
    assert result["frames"] == 6 and result["scored_public_boxes"] == 4
    assert result["independent_preprocessing"] is False
    assert result["tracker_executed"] is False


def test_discrepancy_is_reported_without_tolerance_relaxation(saved):
    summary = json.loads(saved["run-1/summary.json"])
    summary["unrounded"]["clear"]["false_negatives"] += 1
    saved["run-1/summary.json"] = encoded(summary).encode()
    te, iou, _ = check.reference_api()
    result = check.crosscheck(saved, te, iou)
    assert result["all_reported_checks_agree"] is False
    assert result["checks"]["clear"]["CLR_FN"]["reference_minus_baseline"] == -1
    assert result["checks"]["clear"]["CLR_FN"]["tolerance"] == 0


def test_fixed_count_and_float_tolerances():
    assert check.comparison(1, 1)["agrees"] is True
    assert check.comparison(1, 1.00000000001)["agrees"] is False
    assert check.comparison(1., 1.00000000001)["agrees"] is True
    assert check.comparison(1., 1.000000001)["agrees"] is False


def test_reference_geometry_dense_ids_and_empty_frame():
    _, iou, _ = check.reference_api()
    rows = [dict(source_frame=1, gt_ids=[7, 99], track_ids=[100],
                 gt_xyxy=[[0., 0., 10., 10.], [20., 0., 30., 10.]],
                 track_xyxy=[[0., 0., 10., 10.]]),
            dict(source_frame=2, gt_ids=[99], track_ids=[],
                 gt_xyxy=[[20., 0., 30., 10.]], track_xyxy=[])]
    result = check.data_for_reference(rows, iou)
    assert result["gt_ids"][0].tolist() == [0, 1]
    assert result["tracker_ids"][0].tolist() == [0]
    assert result["similarity_scores"][0].tolist() == [[1.], [0.]]
    assert result["similarity_scores"][1].shape == (1, 0)
    assert (result["num_gt_dets"], result["num_tracker_dets"]) == (3, 1)


@pytest.mark.parametrize("defect", ["frames", "duplicate", "shape", "nonfinite"])
def test_malformed_scored_data_rejected(defect):
    _, iou, _ = check.reference_api()
    row = dict(source_frame=1, gt_ids=[7], track_ids=[100],
               gt_xyxy=[[0., 0., 10., 10.]], track_xyxy=[[0., 0., 10., 10.]])
    if defect == "frames":
        row["source_frame"] = 2
    elif defect == "duplicate":
        row["gt_ids"] = [7, 7]
    elif defect == "shape":
        row["track_xyxy"] = []
    else:
        row["gt_xyxy"][0][0] = np.nan
    with pytest.raises(ValueError):
        check.data_for_reference([row], iou)
