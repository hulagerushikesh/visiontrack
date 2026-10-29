from __future__ import annotations

import json
from pathlib import Path

import pytest

from experiments.svmot_occlusion_review import select_event


def _fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    root = tmp_path / "sample"
    folder = root / "data" / "train_seq"
    folder.mkdir(parents=True)
    frames = []
    for frame in range(1, 13):
        occluded = 4 <= frame <= 8
        frames.append({"frame_id": frame, "objects": [{
            "object_id": 7, "bbox": [frame * 10, 10, 20, 20],
            "occlusions": ([{"area": 200}] if occluded else []),
        }]})
    (folder / "occlusion.json").write_text(json.dumps(frames), encoding="utf-8")
    train = tmp_path / "train.txt"
    test = tmp_path / "test.txt"
    train.write_text("train_seq\n", encoding="utf-8")
    test.write_text("test_seq\n", encoding="utf-8")
    return root, train, test


def test_selects_contiguous_moving_train_event_with_fixed_context(tmp_path: Path) -> None:
    root, train, test = _fixture(tmp_path)
    result = select_event(root, train, test, ["train_seq"])
    event = result["selected_event"]
    assert (event["onset_frame"], event["first_clear_frame"]) == (4, 9)
    assert (event["review_start_frame"], event["review_end_frame"]) == (1, 12)
    assert event["max_single_occlusion_fraction"] == 0.5
    assert event["center_displacement_px"] == 60
    assert len(event["occlusion_sha256"]) == 64
    assert result["test_labels_opened"] is False


def test_rejects_test_or_path_selection(tmp_path: Path) -> None:
    root, train, test = _fixture(tmp_path)
    with pytest.raises(ValueError, match="official train"):
        select_event(root, train, test, ["test_seq"])
    with pytest.raises(ValueError, match="plain directory"):
        select_event(root, train, test, ["../train_seq"])
