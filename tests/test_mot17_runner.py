"""Integration test for the MOT17 evaluation runner.

Uses in-memory fake sequences (public detections placed on the ground truth,
plus a distractor and a false positive) to exercise the full stack —
ByteTracker -> MOT17 preprocessing -> pooled CLEAR-MOT / IDF1 / HOTA — without
needing the real dataset. This is the plumbing the acceptance command relies on.
"""
import numpy as np

from visiontrack.datasets.splits import Split
from visiontrack.detection.mot_loader import FrameData
from visiontrack.eval.mot17 import evaluate_sequences
from visiontrack.tracking.config import TrackerConfig


def _box(cx, cy, w=40, h=90):
    return [cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2]


class _FakeSequence:
    """Minimal reader: N objects moving linearly, detections on the GT."""

    def __init__(self, name, n_frames=40, n_obj=4, seed=0):
        self.name = name
        self.n_frames = n_frames
        self.n_obj = n_obj
        self._rng = np.random.default_rng(seed)

    def __len__(self):
        return self.n_frames

    def frame(self, idx):
        boxes, ids, classes, conf, vis = [], [], [], [], []
        det_boxes, det_scores = [], []
        for k in range(self.n_obj):
            cx = 80 + 120 * k + 4 * idx
            cy = 300 + 10 * k
            b = _box(cx, cy)
            boxes.append(b)
            ids.append(k + 1)
            classes.append(1)  # pedestrian
            conf.append(1.0)
            vis.append(1.0)
            # public detection sits on the GT with small jitter and high score
            det_boxes.append(np.array(b) + self._rng.normal(0, 1.0, size=4))
            det_scores.append(0.9)
        # a distractor GT (class 7) with a detection on it -> must be ignored
        db = _box(700, 200, 30, 60)
        boxes.append(db)
        ids.append(999)
        classes.append(7)
        conf.append(1.0)
        vis.append(1.0)
        det_boxes.append(np.array(db))
        det_scores.append(0.8)
        return FrameData(
            frame=idx,
            det_xyxy=np.array(det_boxes),
            det_scores=np.array(det_scores),
            gt_xyxy=np.array(boxes),
            gt_ids=np.array(ids),
            gt_classes=np.array(classes),
            gt_conf=np.array(conf),
            gt_vis=np.array(vis),
        )

    def iter_range(self, first, last):
        for idx in range(first, last + 1):
            yield self.frame(idx)


def _fake_split(names, length):
    entry = {"length": length, "train": [1, length // 2], "val": [1, length]}
    seqs = {name.replace("-FRCNN", ""): dict(entry) for name in names}
    return Split(name="fake", protocol="test", sequences=seqs)


def test_runner_end_to_end_scores_high_and_reports_all_metrics():
    readers = [_FakeSequence("MOT17-02-FRCNN", seed=1), _FakeSequence("MOT17-04-FRCNN", seed=2)]
    split = _fake_split([r.name for r in readers], length=40)
    overall, reports = evaluate_sequences(
        readers, TrackerConfig(), split, subset="val", per_sequence=True
    )

    # All three metric families are present.
    for key in ("MOTA", "IDF1", "HOTA", "DetA", "AssA", "MOTP"):
        assert key in overall, key

    # Detections lie on the GT, so tracking should be strong.
    assert overall["MOTA"] > 0.8, overall
    assert overall["IDF1"] > 0.8, overall
    assert overall["HOTA"] > 0.5, overall
    # The distractor detection must not create false positives.
    assert overall["FP"] == 0, overall
    assert len(reports) == 2


def test_split_loads_from_committed_file():
    from visiontrack.datasets.splits import load_split

    split = load_split("mot17_val_half")
    assert len(split.video_ids()) == 7
    assert split.range_for("MOT17-13-DPM", "val") == (376, 750)
