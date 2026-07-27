"""Tests for the ID-switch error taxonomy (experiments/error_taxonomy.py)."""
from __future__ import annotations

import numpy as np

from experiments.error_taxonomy import (
    _rate,
    _run_frames,
    context_features,
    taxonomy_report,
)


def _box(cx, cy, w=10.0, h=20.0):
    return np.array([cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2])


def test_occlusion_feature_detects_overlap():
    gt_ids = np.array([1, 2])
    gt_boxes = np.stack([_box(0, 0), _box(3, 0)])  # heavily overlapping
    f = context_features(0, gt_ids, gt_boxes, {})
    assert f["occlusion"] > 0.2
    assert f["crowding"] == 1


def test_isolated_object_has_no_occlusion_or_crowding():
    gt_ids = np.array([1, 2])
    gt_boxes = np.stack([_box(0, 0), _box(500, 500)])  # far apart
    f = context_features(0, gt_ids, gt_boxes, {})
    assert f["occlusion"] == 0.0
    assert f["crowding"] == 0


def test_motion_feature_uses_previous_centre():
    gt_ids = np.array([7])
    gt_boxes = np.stack([_box(20, 0, h=20)])  # centre (20, 0), height 20
    prev = {7: np.array([0.0, 0.0])}           # moved 20px => 1.0 box-heights
    f = context_features(0, gt_ids, gt_boxes, prev)
    assert abs(f["motion"] - 1.0) < 1e-6
    # No history -> zero motion.
    assert context_features(0, gt_ids, gt_boxes, {})["motion"] == 0.0


def test_rate_thresholding():
    rows = [{"occlusion": 0.0}, {"occlusion": 0.5}, {"occlusion": 0.3}]
    assert _rate(rows, "occlusion", 0.1) == 2 / 3
    crowd = [{"crowding": 0}, {"crowding": 3}, {"crowding": 2}]
    assert _rate(crowd, "crowding", 2) == 2 / 3  # >= thresh for crowding


def test_run_frames_records_a_switch_under_occlusion():
    # Two GT objects cross; feed hypotheses that swap ids at the crossing so a
    # switch is guaranteed, and check it is captured and classified.
    frames = []
    for t in range(6):
        gt_ids = np.array([1, 2])
        # objects approach then separate (overlap mid-sequence)
        gt_boxes = np.stack([_box(t * 4, 0), _box(40 - t * 4, 0)])
        if t < 3:
            hyp_ids = np.array([10, 20])
            hyp_boxes = gt_boxes.copy()
        else:
            hyp_ids = np.array([20, 10])  # swapped -> forces switches
            hyp_boxes = gt_boxes.copy()
        frames.append((gt_ids, gt_boxes, hyp_ids, hyp_boxes))
    switches, background, idsw = _run_frames(frames, "bytetrack")
    assert idsw >= 1
    assert len(switches) == idsw
    assert len(background) == 12  # 2 GT * 6 frames
    # A well-formed report renders.
    assert "error taxonomy" in taxonomy_report(switches, background, idsw).lower()


def test_report_has_all_conditions():
    report = taxonomy_report([], [], 0)
    for cond in ("occlusion", "crowding", "motion"):
        assert cond in report
