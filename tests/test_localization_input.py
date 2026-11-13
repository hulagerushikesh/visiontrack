"""Local manifest integrity tests use generated pixels, never publisher media."""

import hashlib
import json
from pathlib import Path

import pytest
from PIL import Image
from PIL.PngImagePlugin import PngInfo

from experiments.localization_input import load_frames
from experiments.localization_outcome import compare


def _manifest(tmp_path: Path) -> Path:
    frames = []
    for split in ("development", "test"):
        path = tmp_path / f"{split}.png"
        color = (255, 0, 0) if split == "development" else (0, 0, 255)
        Image.new("RGB", (16, 12), color).save(path)
        frames.append({
            "split": split, "scene": f"{split}-camera", "key": "0001",
            "image": path.name, "image_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "width": 16, "height": 12,
            "detections": [{"class_id": "car", "xyxy": [1, 1, 11, 11],
                            "score": 0.8, "spread_status": "supported",
                            "spread": 0.1, "group_size": 3}],
            "references": [{"class_id": "car", "xyxy": [1, 1, 11, 11],
                            "eligible": True, "visibility": "visible"}],
        })
    manifest = tmp_path / "inputs.json"
    manifest.write_text(json.dumps({"schema": "visiontrack.localization-input/v1",
                                    "source_id": "generated-control", "frames": frames}))
    return manifest


def _edit(manifest: Path, edit) -> None:
    data = json.loads(manifest.read_text())
    edit(data)
    manifest.write_text(json.dumps(data))


def test_local_images_bind_to_frames_and_run_existing_comparison(tmp_path):
    manifest = _manifest(tmp_path)
    frames, receipt = load_frames(manifest)
    assert receipt["verified_image_files"] == 2
    assert receipt["decoded_rgb_split_checked"] is True
    assert receipt["scenes"] == 2
    assert receipt["independent_labels_verified_by_this_loader"] is False
    assert all(frame.image_sha256 == hashlib.sha256(
        (tmp_path / f"{frame.split}.png").read_bytes()).hexdigest() for frame in frames)
    result = compare(frames, resamples=10, require_image_hashes=True)
    assert result["supplied_image_hash_split_checked"] is True
    assert result["results"]["B3_paired"]["matches"] == 1


def test_changed_image_and_wrong_dimensions_are_refused(tmp_path):
    manifest = _manifest(tmp_path)
    Image.new("RGB", (16, 12), (0, 255, 0)).save(tmp_path / "test.png")
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        load_frames(manifest)
    manifest = _manifest(tmp_path)
    _edit(manifest, lambda data: data["frames"][0].update(width=17))
    with pytest.raises(ValueError, match="dimensions disagree"):
        load_frames(manifest)


def test_split_image_leak_is_refused_even_under_different_names(tmp_path):
    manifest = _manifest(tmp_path)
    duplicate = tmp_path / "duplicate.png"
    duplicate.write_bytes((tmp_path / "development.png").read_bytes())
    _edit(manifest, lambda data: data["frames"][1].update(
        image=duplicate.name,
        image_sha256=hashlib.sha256(duplicate.read_bytes()).hexdigest(),
    ))
    with pytest.raises(ValueError, match="source image leaks"):
        load_frames(manifest)


def test_split_reencoded_image_leak_is_refused_by_decoded_pixels(tmp_path):
    manifest = _manifest(tmp_path)
    duplicate = tmp_path / "same-pixels-new-bytes.png"
    metadata = PngInfo()
    metadata.add_text("comment", "different container bytes, identical RGB pixels")
    with Image.open(tmp_path / "development.png") as original:
        original.save(duplicate, pnginfo=metadata)
    assert duplicate.read_bytes() != (tmp_path / "development.png").read_bytes()
    _edit(manifest, lambda data: data["frames"][1].update(
        image=duplicate.name,
        image_sha256=hashlib.sha256(duplicate.read_bytes()).hexdigest(),
    ))
    with pytest.raises(ValueError, match="decoded image pixels leak"):
        load_frames(manifest)


def test_bad_boxes_and_split_manifests_are_refused(tmp_path):
    manifest = _manifest(tmp_path)
    _edit(manifest, lambda data: data["frames"][0]["references"][0].update(
        xyxy=[1, 1, 17, 11]))
    with pytest.raises(ValueError, match="outside the image"):
        load_frames(manifest)
    manifest = _manifest(tmp_path)
    _edit(manifest, lambda data: data["frames"][1].update(
        scene="development-camera", key="0002"))
    with pytest.raises(ValueError, match="scene leaks"):
        load_frames(manifest)


def test_invalid_detection_status_and_group_are_refused_at_load(tmp_path):
    manifest = _manifest(tmp_path)
    _edit(manifest, lambda data: data["frames"][0]["detections"][0].update(
        spread_status="missing_winner"))
    with pytest.raises(ValueError, match="spread does not match status"):
        load_frames(manifest)
    manifest = _manifest(tmp_path)
    _edit(manifest, lambda data: data["frames"][0]["detections"][0].update(
        group_size=2))
    with pytest.raises(ValueError, match="invalid group size"):
        load_frames(manifest)


def test_paths_duplicate_json_fields_and_nonfinite_values_are_refused(tmp_path):
    manifest = _manifest(tmp_path)
    _edit(manifest, lambda data: data["frames"][0].update(image="../development.png"))
    with pytest.raises(ValueError, match="relative to the manifest"):
        load_frames(manifest)
    manifest = _manifest(tmp_path)
    data = manifest.read_text()
    manifest.write_text(data.replace('"source_id": "generated-control"',
                                     '"source_id": "x", "source_id": "generated-control"'))
    with pytest.raises(ValueError, match="duplicate JSON field"):
        load_frames(manifest)
    manifest = _manifest(tmp_path)
    manifest.write_text(manifest.read_text().replace('"score": 0.8', '"score": NaN'))
    with pytest.raises(ValueError, match="non-finite JSON"):
        load_frames(manifest)
