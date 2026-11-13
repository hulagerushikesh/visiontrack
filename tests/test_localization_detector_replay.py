"""Detector replay uses generated pixels and a fake ONNX session."""

import hashlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image

from experiments import localization_detector_replay as replay
from experiments.localization_signal import audit_capture
from visiontrack.detection.yolox_onnx import YoloxDetector


class Session:
    def __init__(self, raw):
        self.raw = raw

    def get_inputs(self):
        return [SimpleNamespace(name="images", shape=[1, 3, 32, 32])]

    def run(self, _names, _feed):
        return [self.raw]


def _fixture(tmp_path: Path, monkeypatch) -> tuple[Path, Path, str]:
    # Three same-class overlapping proposals yield one complete supported group.
    raw = np.array([
        [16, 16, 8, 8, 0.9, 1.0],
        [17, 16, 8, 8, 0.8, 1.0],
        [15, 16, 8, 8, 0.7, 1.0],
    ], dtype=np.float64)
    def make_detector(*args, **kwargs):
        return YoloxDetector(
            "unused", input_size=32, session=Session(raw), class_filter={0},
        )
    monkeypatch.setattr(replay, "YoloxDetector", make_detector)
    detector = make_detector()
    records = []
    for split, color in (("development", "red"), ("test", "blue")):
        image = tmp_path / f"{split}.png"
        Image.new("RGB", (32, 32), color).save(image)
        detections, capture = detector.detect_with_proposals(
            np.asarray(Image.open(image).convert("RGB"))[:, :, ::-1].copy(),
            max_proposals=21,
        )
        spread = audit_capture(capture).rows[0]
        box = detections[0].xyxy.tolist()
        records.append({
            "split": split, "scene": f"{split}-scene", "key": "1",
            "image": image.name,
            "image_sha256": hashlib.sha256(image.read_bytes()).hexdigest(),
            "width": 32, "height": 32,
            "detections": [{
                "class_id": "car", "xyxy": box, "score": detections[0].score,
                "spread_status": spread.status, "spread": spread.spread,
                "group_size": spread.group_size,
            }],
            "references": [{"class_id": "car", "xyxy": box,
                            "eligible": True, "visibility": "visible"}],
        })
    manifest = tmp_path / "input.json"
    manifest.write_text(json.dumps({
        "schema": "visiontrack.localization-input/v1",
        "source_id": "generated-control", "frames": records,
    }))
    model = tmp_path / "model.onnx"
    model.write_bytes(b"generated fake model")
    return manifest, model, hashlib.sha256(model.read_bytes()).hexdigest()


def _verify(manifest, model, digest, **kwargs):
    return replay.verify_replay(manifest, model, digest, {0: "car"},
                                input_size=32, **kwargs)


def _edit(manifest, edit):
    data = json.loads(manifest.read_text())
    edit(data)
    manifest.write_text(json.dumps(data))


def test_full_replay_verifies_detector_rows_and_parity(tmp_path, monkeypatch):
    manifest, model, digest = _fixture(tmp_path, monkeypatch)
    result = _verify(manifest, model, digest)
    assert result["frames"] == 2 and result["detections"] == 2
    assert result["spread_status_counts"] == {"supported": 2}
    assert result["declared_detector_rows_verified"] is True
    assert result["independent_labels_verified"] is False


def test_populate_reference_only_manifest_then_verify(tmp_path, monkeypatch):
    manifest, model, digest = _fixture(tmp_path, monkeypatch)
    _edit(manifest, lambda data: [row.update(detections=[])
                                  for row in data["frames"]])
    output = tmp_path / "populated.json"
    result = replay.populate_manifest(
        manifest, output, model, digest, {0: "car"}, input_size=32,
    )
    assert result["declared_detector_rows_verified"] is False
    assert result["generated_manifest_sha256"] == hashlib.sha256(
        output.read_bytes()).hexdigest()
    assert _verify(output, model, digest)["declared_detector_rows_verified"] is True
    with pytest.raises(ValueError, match="new file"):
        replay.populate_manifest(manifest, output, model, digest,
                                 {0: "car"}, input_size=32)


def test_command_path_populates_and_verifies(tmp_path, monkeypatch, capsys):
    manifest, model, digest = _fixture(tmp_path, monkeypatch)
    _edit(manifest, lambda data: [row.update(detections=[])
                                  for row in data["frames"]])
    output = tmp_path / "populated.json"
    arguments = ["localization_detector_replay", "--manifest", str(manifest),
                 "--model", str(model), "--model-sha256", digest,
                 "--input-size", "32", "--class-map", "0:car"]
    monkeypatch.setattr(sys, "argv", arguments + ["--populate-output", str(output)])
    replay.main()
    assert json.loads(capsys.readouterr().out)["generated_manifest_path"] == str(output)
    monkeypatch.setattr(sys, "argv", arguments[:2] + [str(output)] + arguments[3:])
    replay.main()
    assert json.loads(capsys.readouterr().out)["declared_detector_rows_verified"] is True


@pytest.mark.parametrize("field,value", [
    ("score", 0.5), ("spread", 0.99), ("xyxy", [1, 1, 8, 8]),
    ("group_size", 4),
])
def test_changed_detector_row_is_refused(tmp_path, monkeypatch, field, value):
    manifest, model, digest = _fixture(tmp_path, monkeypatch)
    _edit(manifest, lambda data: data["frames"][0]["detections"][0].update(
        {field: value}))
    with pytest.raises(ValueError, match="differs from replay"):
        _verify(manifest, model, digest)


def test_wrong_model_hash_and_truncated_capture_are_refused(tmp_path, monkeypatch):
    manifest, model, digest = _fixture(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match="model SHA-256 mismatch"):
        _verify(manifest, model, "0" * 64)
    with pytest.raises(ValueError, match="truncated"):
        _verify(manifest, model, digest, max_proposals=2)


def test_unmapped_class_and_image_mutation_are_refused(tmp_path, monkeypatch):
    manifest, model, digest = _fixture(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match="differs from replay"):
        replay.verify_replay(manifest, model, digest, {0: "other"}, input_size=32)
    Image.new("RGB", (32, 32), "green").save(tmp_path / "test.png")
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        _verify(manifest, model, digest)
