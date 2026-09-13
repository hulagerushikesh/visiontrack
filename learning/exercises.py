"""Dataset-free self-checks for the first four VisionTrack learning stages.

Run all exercises with ``python learning/exercises.py`` or select one with
``python learning/exercises.py geometry``. Every check uses tiny, deterministic
arrays and the real project implementation.
"""
from __future__ import annotations

import argparse

import numpy as np

from visiontrack.core.assignment import linear_assignment
from visiontrack.core.geometry import iou_matrix, xyah_to_xyxy, xyxy_to_xyah
from visiontrack.core.kalman import KalmanBoxTracker
from visiontrack.tracking.track import Track, TrackState


def geometry() -> None:
    """Check box conversion and a hand-computable IoU of 1/3."""
    boxes = np.array([[0.0, 0.0, 4.0, 4.0], [2.0, 0.0, 6.0, 4.0]])
    converted = xyah_to_xyxy(xyxy_to_xyah(boxes))
    overlap = float(iou_matrix(boxes[:1], boxes[1:])[0, 0])
    np.testing.assert_allclose(converted, boxes)
    np.testing.assert_allclose(overlap, 1.0 / 3.0)
    print(f"geometry: PASS (IoU={overlap:.3f}; expected 0.333)")


def kalman() -> None:
    """Check constant-velocity prediction and uncertainty-reducing update."""
    kf = KalmanBoxTracker()
    measurement = np.array([100.0, 50.0, 0.5, 80.0])
    mean, covariance = kf.initiate(measurement)
    mean[4] = 3.0
    predicted, predicted_covariance = kf.predict(mean, covariance)
    corrected, corrected_covariance = kf.update(
        predicted, predicted_covariance, np.array([104.0, 50.0, 0.5, 80.0])
    )
    np.testing.assert_allclose(predicted[0], 103.0)
    assert predicted[0] < corrected[0] < 104.0
    assert corrected_covariance[0, 0] < predicted_covariance[0, 0]
    print(
        "kalman: PASS "
        f"(predict x={predicted[0]:.3f}; update x={corrected[0]:.3f}; "
        "position uncertainty decreased)"
    )


def assignment() -> None:
    """Check that global assignment beats a row-by-row greedy choice."""
    cost = np.array([[1.0, 2.0], [1.1, 100.0]])
    rows, columns = linear_assignment(cost)
    total = float(cost[rows, columns].sum())
    np.testing.assert_array_equal(rows, [0, 1])
    np.testing.assert_array_equal(columns, [1, 0])
    np.testing.assert_allclose(total, 3.1)
    print(f"assignment: PASS (global cost={total:.1f}; row-greedy cost=101.0)")


def lifecycle() -> None:
    """Check Tentative -> Confirmed -> Deleted transitions."""
    kf = KalmanBoxTracker()
    detection = np.array([10.0, 10.0, 30.0, 50.0])
    track = Track(1, detection, kf, n_init=2, max_age=1)
    assert track.state == TrackState.TENTATIVE
    track.predict()
    track.update(detection, class_id=0, score=0.9)
    assert track.state == TrackState.CONFIRMED
    track.predict()
    track.mark_missed()
    assert track.state == TrackState.CONFIRMED
    track.predict()
    track.mark_missed()
    assert track.state == TrackState.DELETED
    print("lifecycle: PASS (Tentative -> Confirmed -> Deleted)")


EXERCISES = {
    "geometry": geometry,
    "kalman": kalman,
    "assignment": assignment,
    "lifecycle": lifecycle,
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("exercise", nargs="?", choices=["all", *EXERCISES], default="all")
    args = parser.parse_args()
    selected = EXERCISES.values() if args.exercise == "all" else [EXERCISES[args.exercise]]
    for exercise in selected:
        exercise()


if __name__ == "__main__":
    main()
