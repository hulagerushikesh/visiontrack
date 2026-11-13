"""Controls for exploratory camera-held-out fitting, without source media."""

import pytest

from experiments.localization_outcome import MatchedRow
from experiments.lta_spread_pilot import cross_camera


def _row(camera, index, *, class_id="car", spread=0.1):
    return MatchedRow(
        camera, (camera, str(index), 0), class_id, 20 + index, 10 + index,
        0.5 + index * 0.02, spread, index * 0.03, index * 0.3, index * 0.01,
    )


def test_each_fold_fits_other_cameras_and_keeps_same_supported_test_population():
    rows = {
        "a": [_row("a", i) for i in range(5)] + [_row("a", 6, spread=None)],
        "b": [_row("b", i) for i in range(5)] + [_row("b", 7, class_id="bus")],
        "c": [_row("c", i) for i in range(5)],
    }
    report = cross_camera(rows)
    assert report["camera_folds"]["b"]["paired_test_matched"] == 5
    assert report["camera_folds"]["b"]["excluded_unseen_class"] == 1
    assert report["camera_folds"]["a"]["supported_matched"] == 5
    assert report["camera_folds"]["a"]["train_supported_matched"] == 11
    assert report["paired_matches_total"] == 15
    assert report["cameras_with_paired_matches"] == 3
    assert report["camera_mean_delta"] == pytest.approx(
        sum(fold["B3_minus_B2"] for fold in report["camera_folds"].values()) / 3
    )


def test_camera_with_no_matches_remains_visible():
    report = cross_camera({"empty": [], "other": [_row("other", 1)]})
    assert report["cameras_total"] == 2
    assert report["cameras_with_paired_matches"] == 0
    assert report["camera_folds"]["empty"]["status"] == "no paired comparison"
    assert report["camera_folds"]["other"]["status"] == "no paired comparison"
    assert report["camera_mean_delta"] is None
