from __future__ import annotations

from pathlib import Path

import pytest

from experiments.svmot_source_audit import audit


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
