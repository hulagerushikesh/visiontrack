"""Tests for the DanceTrack loader (perturbed-GT oracle detections).

Uses a tiny hand-written MOT-format sequence in a tmp dir — no real dataset, so
this runs in CI. Covers GT parsing, pedestrian marking (so the MOT17 evaluator
scores the boxes), perturbed-GT detections, determinism, and frame_filename.
"""
import numpy as np
import pytest

from visiontrack.detection.base import Detection
from visiontrack.detection.dancetrack_loader import (
    DanceTrackDetectorSequence,
    DanceTrackSequence,
    discover_dancetrack,
    frame_filename,
)
from visiontrack.detection.mot_loader import PEDESTRIAN_CLASS
from visiontrack.detection.noise import NoiseConfig


def _make_seq(tmp_path, name="dancetrack0001", n_frames=6, n_obj=4, w=1920, h=1080):
    d = tmp_path / name
    (d / "gt").mkdir(parents=True)
    (d / "img1").mkdir()
    (d / "seqinfo.ini").write_text(
        "[Sequence]\n"
        f"name={name}\nimDir=img1\nframeRate=20\n"
        f"seqLength={n_frames}\nimWidth={w}\nimHeight={h}\nimExt=.jpg\n"
    )
    lines = []
    for f in range(1, n_frames + 1):
        for oid in range(1, n_obj + 1):
            x, y, bw, bh = 100 * oid, 50 * oid, 40, 90
            # DanceTrack gt: frame,id,x,y,w,h,1,1,1
            lines.append(f"{f},{oid},{x},{y},{bw},{bh},1,1,1")
    (d / "gt" / "gt.txt").write_text("\n".join(lines) + "\n")
    return d


def test_parses_info_and_marks_pedestrian(tmp_path):
    seq = DanceTrackSequence(_make_seq(tmp_path))
    assert seq.info.length == 6
    assert seq.info.width == 1920 and seq.info.height == 1080
    fd = seq.frame(1)
    assert fd.gt_xyxy.shape == (4, 4)
    # every box must be PEDESTRIAN + considered, else the evaluator ignores it
    assert np.all(fd.gt_classes == PEDESTRIAN_CLASS)
    assert np.all(fd.gt_conf >= 1.0)


def test_detections_are_perturbed_gt(tmp_path):
    # No drops / no FPs → one detection per GT box, jittered off the GT.
    cfg = NoiseConfig(jitter_std=5.0, drop_prob=0.0, fp_rate=0.0)
    seq = DanceTrackSequence(_make_seq(tmp_path), noise_cfg=cfg, seed=1)
    fd = seq.frame(2)
    assert fd.det_xyxy.shape[0] == fd.gt_xyxy.shape[0]  # 4 dets, 4 gt
    # jittered, so not identical to GT, but close
    assert not np.allclose(fd.det_xyxy, fd.gt_xyxy)
    assert np.abs(fd.det_xyxy - fd.gt_xyxy).mean() < 30


def test_drop_and_fp_change_detection_count(tmp_path):
    cfg = NoiseConfig(jitter_std=2.0, drop_prob=0.9, fp_rate=0.0)  # drop most
    seq = DanceTrackSequence(_make_seq(tmp_path), noise_cfg=cfg, seed=0)
    dropped = sum(seq.frame(f).det_xyxy.shape[0] for f in range(1, 7))
    assert dropped < 6 * 4  # fewer detections than GT boxes


def test_perturbation_is_deterministic(tmp_path):
    d = _make_seq(tmp_path)
    a = DanceTrackSequence(d, seed=3).frame(4).det_xyxy
    b = DanceTrackSequence(d, seed=3).frame(4).det_xyxy
    np.testing.assert_array_equal(a, b)


class _StubDetector:
    """Returns two person boxes + one non-person (to test class filtering)."""

    def detect(self, frame_rgb):
        return [
            Detection(xyxy=np.array([10.0, 10, 50, 90]), score=0.8, class_id=0),
            Detection(xyxy=np.array([60.0, 20, 90, 120]), score=0.6, class_id=0),
            Detection(xyxy=np.array([0.0, 0, 5, 5]), score=0.9, class_id=2),  # car
        ]


def test_detector_sequence_uses_real_detections(tmp_path):
    imageio = pytest.importorskip("imageio.v2")
    d = _make_seq(tmp_path, n_frames=2, n_obj=3)
    imageio.imwrite(d / "img1" / "00000001.jpg",
                    np.zeros((1080, 1920, 3), dtype=np.uint8))  # only frame 1 exists

    seq = DanceTrackDetectorSequence(d, _StubDetector())
    fd = seq.frame(1)
    # detections come from the detector (not perturbed GT); the car (class 2) is
    # filtered out by the default person-only class_ids.
    assert fd.det_xyxy.shape[0] == 2
    assert sorted(np.round(fd.det_scores, 1)) == [0.6, 0.8]
    assert fd.gt_xyxy.shape[0] == 3  # GT still loaded for evaluation

    # a frame with no image on disk -> no detections, GT intact (honest miss)
    fd2 = seq.frame(2)
    assert fd2.det_xyxy.shape[0] == 0
    assert fd2.gt_xyxy.shape[0] == 3


def test_discover_and_frame_filename(tmp_path):
    d = _make_seq(tmp_path)
    # write an 8-digit frame file (DanceTrack style) and a 6-digit one
    (d / "img1" / "00000003.jpg").write_bytes(b"x")
    found = discover_dancetrack(tmp_path, split=".")  # split "." -> tmp_path itself
    assert d in found
    assert frame_filename(d / "img1", 3) == d / "img1" / "00000003.jpg"
    assert frame_filename(d / "img1", 99) is None
