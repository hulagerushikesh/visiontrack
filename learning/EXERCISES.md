# VisionTrack dataset-free exercises

These exercises use the real NumPy implementation but need no video, detector,
model weights, or MOT dataset. From the repository root, install the core once
and run:

```bash
python -m pip install -e .
python learning/exercises.py
```

Pass `geometry`, `kalman`, `assignment`, or `lifecycle` to run one exercise.
Read each function, predict its output on paper, run it, and then change one
input to test your explanation.

## 1. Geometry overlap

Two 4×4 boxes overlap by 2×4. Compute their intersection, union, and IoU before
running the check. Expected IoU: `0.333`.

## 2. Kalman predict and update

A box starts at x=100 with x-velocity 3. Predict the next x, then decide whether
a measurement at x=104 should pull the estimate left or right and whether the
position uncertainty should grow or shrink. Expected: predicted x=103, updated
x between 103 and 104, and lower covariance after update.

## 3. Global assignment

For `[[1, 2], [1.1, 100]]`, compare row-by-row greedy matching with a global
one-to-one assignment. Expected pairs: `(0, 1)` and `(1, 0)`; total cost `3.1`
instead of greedy cost `101.0`.

## 4. Track lifecycle

Trace a track configured with `n_init=2` and `max_age=1`: create it, add the
second hit, then miss twice. Expected states: `Tentative -> Confirmed -> Deleted`.

## Finish

When all four print `PASS`, explain why each assertion represents a tracker
invariant. The study guide links to the production code enforcing each one.
