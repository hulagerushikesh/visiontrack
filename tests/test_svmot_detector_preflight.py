from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from experiments import svmot_detector_preflight as study
from visiontrack.detection.base import Detection


def _sample(tmp_path: Path) -> tuple[Path, Path, Path, Path, Path]:
    root = tmp_path / "sample"
    folder = root / "data" / "dev_scene"
    (folder / "img").mkdir(parents=True)
    (folder / "gt").mkdir()
    (folder / "occlusion.json").write_text("[]", encoding="utf-8")
    (folder / "gt" / "gt.txt").write_text(
        "".join(f"{frame},7,10,20,30,20,1,1,1.000\n" for frame in range(1, 5)),
        encoding="utf-8",
    )
    for frame in range(1, 5):
        Image.new("RGB", (100, 100)).save(folder / "img" / f"{frame:04d}.jpg")
    train = tmp_path / "train.txt"
    test = tmp_path / "test.txt"
    train.write_text("dev_scene\n", encoding="utf-8")
    test.write_text("heldout_scene\n", encoding="utf-8")
    model = tmp_path / "model.onnx"
    model.write_bytes(b"model fixture")
    selection = tmp_path / "selection.json"
    selection.write_text(json.dumps({
        "schema": "visiontrack.svmot-occlusion-review-selection/v1",
        "test_labels_opened": False,
        "selected_event": {
            "sequence": "dev_scene", "object_id": 7,
            "review_start_frame": 1, "onset_frame": 2,
            "first_clear_frame": 3, "review_end_frame": 4,
            "occlusion_sha256": hashlib.sha256(b"[]").hexdigest(),
        },
    }), encoding="utf-8")
    return root, train, test, selection, model


class _Detector:
    def __init__(self, model_path: str, *, input_size: int,
                 class_filter: set[int]) -> None:
        assert class_filter == {2}
        assert input_size in {416, 640}
        self.count = 0

    def detect(self, image: np.ndarray) -> list[Detection]:
        assert image.shape == (100, 100, 3)
        self.count += 1
        if self.count == 2:
            return []
        return [Detection([10, 20, 40, 40], score=0.8, class_id=2)]


def test_preflight_runs_only_bounded_detector_and_reports_phases(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, train, test, selection, model = _sample(tmp_path)
    monkeypatch.setitem(study.MODEL_SPECS, "nano",
                        (hashlib.sha256(model.read_bytes()).hexdigest(), 416))
    result = study.preflight(root, train, test, selection, model, _Detector)
    json.dumps(result)  # The owner-local CLI receipt must be serializable.
    assert result["phases"] == {
        "before": {"frames": 1, "frames_with_car_box_overlap_at_0_5": 1,
                   "frames_with_any_car_detection": 1},
        "occluded": {"frames": 1, "frames_with_car_box_overlap_at_0_5": 0,
                     "frames_with_any_car_detection": 0},
        "after": {"frames": 2, "frames_with_car_box_overlap_at_0_5": 2,
                  "frames_with_any_car_detection": 2},
    }
    assert result["publisher_detections_used"] is False
    assert result["tracker_ran"] is False
    assert result["test_scenes_opened"] is False


def test_preflight_rejects_heldout_or_changed_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, train, test, selection, model = _sample(tmp_path)
    monkeypatch.setitem(study.MODEL_SPECS, "nano",
                        (hashlib.sha256(model.read_bytes()).hexdigest(), 416))
    receipt = json.loads(selection.read_text(encoding="utf-8"))
    receipt["selected_event"]["sequence"] = "heldout_scene"
    selection.write_text(json.dumps(receipt), encoding="utf-8")
    with pytest.raises(ValueError, match="official train"):
        study.preflight(root, train, test, selection, model, _Detector)
    receipt["selected_event"]["sequence"] = "dev_scene"
    selection.write_text(json.dumps(receipt), encoding="utf-8")
    (root / "data" / "dev_scene" / "occlusion.json").write_text("[ ]", encoding="utf-8")
    with pytest.raises(ValueError, match="occlusion source"):
        study.preflight(root, train, test, selection, model, _Detector)


def test_preflight_rejects_unpinned_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, train, test, selection, model = _sample(tmp_path)
    monkeypatch.setitem(study.MODEL_SPECS, "nano", ("0" * 64, 416))
    with pytest.raises(ValueError, match="model fingerprint"):
        study.preflight(root, train, test, selection, model, _Detector)


def test_preflight_uses_pinned_x_input_and_rejects_unknown_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, train, test, selection, model = _sample(tmp_path)
    monkeypatch.setitem(study.MODEL_SPECS, "x",
                        (hashlib.sha256(model.read_bytes()).hexdigest(), 640))
    result = study.preflight(root, train, test, selection, model, _Detector,
                             model_key="x")
    assert result["detector"].startswith("YOLOX x ONNX; 640 px")
    with pytest.raises(ValueError, match="unknown pinned"):
        study.preflight(root, train, test, selection, model, _Detector,
                        model_key="unregistered")
