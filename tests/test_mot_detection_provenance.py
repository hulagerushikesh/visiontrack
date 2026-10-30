from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from experiments.mot_detection_provenance import audit_files, audit_rows


def _gt(frame: str, x: str) -> list[str]:
    return [frame, "7", x, "20", "30", "40", "1", "1", "1"]


def _det(frame: str, x: str) -> list[str]:
    return [frame, "-1", x, "20", "30", "40", "0.8", "-1", "-1", "-1"]


def test_numeric_formatting_does_not_hide_gt_geometry_mirror() -> None:
    result = audit_rows([_gt("1", "10.0"), _gt("2", "11")],
                        [_det("1", "1e1"), _det("2", "11.000")])
    assert result["exact_numeric_gt_det_box_matches"] == 2
    assert result["identical_box_multisets"] is True
    assert result["geometry_screen"] == "review_gt_geometry_mirror"
    assert result["independent_detector_verified"] is False


def test_duplicate_detections_do_not_count_as_multiple_gt_matches() -> None:
    result = audit_rows([_gt("1", "10")], [_det("1", "10"), _det("1", "10")])
    assert result["exact_numeric_gt_det_box_matches"] == 1
    assert result["all_detection_boxes_match_gt_geometry"] is False
    assert result["geometry_screen"] == "independence_unverified"


def test_different_boxes_do_not_prove_independence() -> None:
    result = audit_rows([_gt("1", "10")], [_det("1", "10.1")])
    assert result["exact_numeric_gt_det_box_matches"] == 0
    assert result["geometry_screen"] == "independence_unverified"
    assert result["independent_detector_verified"] is False


@pytest.mark.parametrize("bad", ["NaN", "Infinity", "oops", "10,20"])
def test_rejects_invalid_coordinate(bad: str) -> None:
    with pytest.raises(ValueError, match="invalid MOT"):
        audit_rows([_gt("1", bad)], [_det("1", "10")])


def test_rejects_invalid_shape_and_empty_streams() -> None:
    with pytest.raises(ValueError, match="both MOT streams"):
        audit_rows([], [_det("1", "10")])
    with pytest.raises(ValueError, match="nine GT columns"):
        audit_rows([_gt("1", "10")[:-1]], [_det("1", "10")])
    with pytest.raises(ValueError, match="invalid MOT"):
        audit_rows([_gt("0", "10")], [_det("1", "10")])
    with pytest.raises(ValueError, match="invalid MOT"):
        audit_rows([_gt("1", "10")], [_det("1", "10")[:4] + ["0"] + _det("1", "10")[5:]])


def test_file_receipt_pins_exact_inputs(tmp_path: Path) -> None:
    gt = tmp_path / "gt.txt"
    det = tmp_path / "det.txt"
    gt.write_text(",".join(_gt("1", "10")) + "\n", encoding="utf-8")
    det.write_text(",".join(_det("1", "10.000")) + "\n", encoding="utf-8")
    result = audit_files(gt, det)
    assert result["schema"] == "visiontrack.mot-detection-provenance-screen/v1"
    assert result["gt_sha256"] == hashlib.sha256(gt.read_bytes()).hexdigest()
    assert result["detections_sha256"] == hashlib.sha256(det.read_bytes()).hexdigest()
    assert result["identical_box_multisets"] is True
    with pytest.raises(ValueError, match="must differ"):
        audit_files(gt, gt)
