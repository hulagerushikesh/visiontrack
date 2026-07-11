import numpy as np

from visiontrack.detection.base import Detection
from visiontrack.detection.synthetic import SyntheticScene, SyntheticSceneConfig
from visiontrack.eval.mot import MotAccumulator
from visiontrack.tracking.config import TrackerConfig
from visiontrack.tracking.tracker import ByteTracker


def _linear_detection(t, x0=100.0, y0=100.0, vx=5.0, vy=3.0, w=40.0, h=80.0, score=0.9):
    cx, cy = x0 + vx * t, y0 + vy * t
    return Detection(
        xyxy=[cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2], score=score, class_id=0
    )


def test_single_object_gets_stable_id():
    tracker = ByteTracker()
    ids = set()
    for t in range(20):
        obs = tracker.update([_linear_detection(t)])
        if obs:
            ids.add(obs[0].track_id)
    # After confirmation the object keeps exactly one id.
    assert len(ids) == 1


def test_tentative_track_not_reported_immediately():
    tracker = ByteTracker(TrackerConfig(n_init=3))
    obs = tracker.update([_linear_detection(0)])
    assert obs == []  # first frame: still tentative
    tracker.update([_linear_detection(1)])
    obs3 = tracker.update([_linear_detection(2)])
    assert len(obs3) == 1  # confirmed on the 3rd consecutive hit


def test_track_survives_short_occlusion():
    cfg = TrackerConfig(n_init=3, max_age=30)
    tracker = ByteTracker(cfg)
    # Confirm the track.
    for t in range(5):
        tracker.update([_linear_detection(t)])
    confirmed_id = tracker.update([_linear_detection(5)])[0].track_id

    # Drop detections for a few frames (occlusion) ...
    for t in range(6, 11):
        tracker.update([])
    # ... then it reappears; the id must persist (coasted on Kalman motion).
    obs = tracker.update([_linear_detection(11)])
    assert len(obs) == 1
    assert obs[0].track_id == confirmed_id


def test_track_deleted_after_max_age():
    cfg = TrackerConfig(n_init=2, max_age=5)
    tracker = ByteTracker(cfg)
    for t in range(4):
        tracker.update([_linear_detection(t)])
    for _ in range(10):  # long gap, well beyond max_age
        tracker.update([])
    assert tracker.tracks == []


def test_false_positive_does_not_confirm():
    """A one-off spurious detection must never become a confirmed track."""
    tracker = ByteTracker(TrackerConfig(n_init=3))
    tracker.update([Detection(xyxy=[10, 10, 40, 90], score=0.95, class_id=0)])
    # No supporting detections afterwards.
    reported = []
    for _ in range(5):
        reported += tracker.update([])
    assert reported == []


def test_two_objects_keep_distinct_ids():
    tracker = ByteTracker()
    a_ids, b_ids = set(), set()
    for t in range(20):
        det_a = _linear_detection(t, x0=100, y0=100, vx=4, vy=0)
        det_b = _linear_detection(t, x0=600, y0=400, vx=-4, vy=0)
        for o in tracker.update([det_a, det_b]):
            (a_ids if o.xyxy[0] < 350 else b_ids).add(o.track_id)
    assert len(a_ids) == 1 and len(b_ids) == 1
    assert a_ids.isdisjoint(b_ids)


def test_end_to_end_quality_on_synthetic_scene():
    """Integration: on a moderately noisy scene the tracker should achieve
    solid MOTA with few identity switches. Guards against regressions."""
    scene = SyntheticScene(
        SyntheticSceneConfig(num_objects=5, num_frames=100, seed=7)
    )
    tracker = ByteTracker()
    acc = MotAccumulator(iou_threshold=0.5)
    for frame in scene:
        obs = tracker.update(frame.detections)
        acc.update(
            frame.gt_ids,
            frame.gt_boxes,
            [o.track_id for o in obs],
            [o.xyxy for o in obs],
        )
    m = acc.result()
    assert m.mota > 0.6, m
    assert m.motp > 0.7, m
    assert m.id_switches <= 5, m
