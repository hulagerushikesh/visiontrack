from __future__ import annotations

import json
from pathlib import Path

import pytest

from experiments.svmot_source_audit import _rectangle_union_area, audit


def _fixture(tmp_path: Path, *, det_box: str = "10,20,30,40") -> tuple[Path, Path, Path]:
    root = tmp_path / "sample"
    seq = root / "data" / "train_seq"
    for part in ("gt", "det", "img"):
        (seq / part).mkdir(parents=True)
    (root / "classes.txt").write_text("car\n", encoding="utf-8")
    (seq / "seqinfo.ini").write_text(
        "[Sequence]\nname = old_name\nseqlength = 2\nimwidth = 100\nimheight = 100\n",
        encoding="utf-8",
    )
    (seq / "gt" / "gt.txt").write_text(
        "1,7,10,20,30,40,1,0,0.9\n2,7,11,20,30,40,1,0,0.8\n",
        encoding="utf-8",
    )
    (seq / "det" / "det.txt").write_text(
        f"1,-1,{det_box},0.8,-1,-1,-1\n2,-1,11,20,30,40,0.7,-1,-1,-1\n",
        encoding="utf-8",
    )
    (seq / "img" / "0001.jpg").write_bytes(b"sample")
    train = tmp_path / "train.txt"
    test = tmp_path / "test.txt"
    train.write_text("train_seq\n", encoding="utf-8")
    test.write_text("test_seq\n", encoding="utf-8")
    return root, train, test


def test_audit_reports_exact_gt_detection_boxes_and_metadata_mismatch(tmp_path: Path) -> None:
    root, train, test = _fixture(tmp_path)
    result = audit(root, train, test, ["train_seq"])
    row = result["sequences"][0]
    assert row["exact_gt_det_box_matches"] == 2
    assert row["all_det_boxes_match_gt"] is True
    assert row["declared_name_matches_directory"] is False
    assert row["gt_unique_ids"] == 1
    assert row["gt_zero_visibility_rows"] == 0
    assert row["gt_below_half_visibility_rows"] == 0
    assert result["test_labels_opened"] is False


def test_audit_detects_independent_box_and_rejects_test_selection(tmp_path: Path) -> None:
    root, train, test = _fixture(tmp_path, det_box="12,20,30,40")
    row = audit(root, train, test, ["train_seq"])["sequences"][0]
    assert row["exact_gt_det_box_matches"] == 1
    assert row["all_det_boxes_match_gt"] is False
    with pytest.raises(ValueError, match="official train"):
        audit(root, train, test, ["test_seq"])
    with pytest.raises(ValueError, match="plain directory"):
        audit(root, train, test, ["../train_seq"])


def test_audit_rejects_duplicate_ground_truth_id_in_one_frame(tmp_path: Path) -> None:
    root, train, test = _fixture(tmp_path)
    with (root / "data" / "train_seq" / "gt" / "gt.txt").open("a", encoding="utf-8") as stream:
        stream.write("2,7,12,20,30,40,1,0,0.8\n")
    with pytest.raises(ValueError, match="duplicate GT frame/ID"):
        audit(root, train, test, ["train_seq"])


def test_audit_counts_visibility_policy_rows(tmp_path: Path) -> None:
    root, train, test = _fixture(tmp_path)
    gt = root / "data" / "train_seq" / "gt" / "gt.txt"
    gt.write_text(gt.read_text(encoding="utf-8").replace(",0,0.9", ",0,0.0")
                  .replace(",0,0.8", ",0,0.4"), encoding="utf-8")
    row = audit(root, train, test, ["train_seq"])["sequences"][0]
    assert row["gt_zero_visibility_rows"] == 1
    assert row["gt_below_half_visibility_rows"] == 2


def _occlusion_fixture(root: Path) -> Path:
    path = root / "data" / "train_seq" / "occlusion.json"
    frames = [
        {"frame_id": 1, "objects": [{"object_id": 7, "bbox": [10, 20, 30, 40],
                                     "stopped": False, "occlusions": []}]},
        {"frame_id": 2, "objects": [{"object_id": 7, "bbox": [11, 20, 30, 40],
                                     "stopped": True, "occlusions": []}]},
    ]
    path.write_text(json.dumps(frames), encoding="utf-8")
    return path


def test_audit_matches_occlusion_objects_to_ground_truth(tmp_path: Path) -> None:
    root, train, test = _fixture(tmp_path)
    _occlusion_fixture(root)
    row = audit(root, train, test, ["train_seq"])["sequences"][0]
    assert row["occlusion_annotation_present"] is True
    assert row["occlusion_gt_structure_matches"] is True
    assert row["occlusion_boxes_match_gt_intersections"] is True
    assert row["visibility_mismatch_rows"] == 2
    assert row["occlusion_frames"] == 2
    assert row["occlusion_objects"] == 2
    assert row["stopped_true_rows"] == 1


def test_audit_rejects_occlusion_box_or_frame_mismatch(tmp_path: Path) -> None:
    root, train, test = _fixture(tmp_path)
    path = _occlusion_fixture(root)
    frames = json.loads(path.read_text(encoding="utf-8"))
    frames[1]["objects"][0]["bbox"][0] = 12
    path.write_text(json.dumps(frames), encoding="utf-8")
    with pytest.raises(ValueError, match="occlusion/GT box mismatch"):
        audit(root, train, test, ["train_seq"])
    frames[1]["objects"][0]["bbox"][0] = 11
    frames[1]["frame_id"] = 3
    path.write_text(json.dumps(frames), encoding="utf-8")
    with pytest.raises(ValueError, match="occlusion frame order mismatch"):
        audit(root, train, test, ["train_seq"])


def test_audit_rejects_self_occlusion_and_duplicate_object(tmp_path: Path) -> None:
    root, train, test = _fixture(tmp_path)
    path = _occlusion_fixture(root)
    frames = json.loads(path.read_text(encoding="utf-8"))
    frames[0]["objects"][0]["occlusions"] = [
        {"occluder_id": 7, "occlusion_bbox": [10, 20, 2, 2], "area": 4},
    ]
    path.write_text(json.dumps(frames), encoding="utf-8")
    with pytest.raises(ValueError, match="invalid occluder reference"):
        audit(root, train, test, ["train_seq"])
    frames[0]["objects"][0]["occlusions"] = []
    frames[0]["objects"].append(dict(frames[0]["objects"][0]))
    path.write_text(json.dumps(frames), encoding="utf-8")
    with pytest.raises(ValueError, match="occlusion/GT object IDs mismatch"):
        audit(root, train, test, ["train_seq"])


def test_audit_requires_occlusion_geometry_to_match_both_objects(tmp_path: Path) -> None:
    root, train, test = _fixture(tmp_path)
    path = _occlusion_fixture(root)
    frames = json.loads(path.read_text(encoding="utf-8"))
    frames[0]["objects"].append({
        "object_id": 8, "bbox": [35, 20, 30, 40],
        "stopped": False, "occlusions": [],
    })
    with (root / "data" / "train_seq" / "gt" / "gt.txt").open("a", encoding="utf-8") as stream:
        stream.write("1,8,35,20,30,40,1,0,0.9\n")
    frames[0]["objects"][0]["occlusions"] = [
        {"occluder_id": 8, "occlusion_bbox": [36, 20, 4, 40], "area": 160},
    ]
    path.write_text(json.dumps(frames), encoding="utf-8")
    with pytest.raises(ValueError, match="GT box intersection"):
        audit(root, train, test, ["train_seq"])
    frames[0]["objects"][0]["occlusions"][0] = {
        "occluder_id": 8, "occlusion_bbox": [35, 20, 5, 40], "area": 200,
    }
    path.write_text(json.dumps(frames), encoding="utf-8")
    assert audit(root, train, test, ["train_seq"])["sequences"][0]["occlusion_links"] == 1


def test_overlap_union_does_not_double_count_and_flags_visibility_mismatch(
        tmp_path: Path) -> None:
    assert _rectangle_union_area([[0, 0, 5, 4], [3, 0, 5, 4]]) == 32
    root, train, test = _fixture(tmp_path)
    _occlusion_fixture(root)
    result = audit(root, train, test, ["train_seq"])["sequences"][0]
    assert result["visibility_matches_geometric_overlap_to_3dp"] is False
    assert result["visibility_mismatch_rows"] == 2
    gt = root / "data" / "train_seq" / "gt" / "gt.txt"
    gt.write_text(gt.read_text(encoding="utf-8").replace(",0,0.9", ",0,1.0")
                  .replace(",0,0.8", ",0,1.0"), encoding="utf-8")
    result = audit(root, train, test, ["train_seq"])["sequences"][0]
    assert result["visibility_matches_geometric_overlap_to_3dp"] is True
    assert result["max_visibility_absolute_error"] == 0
