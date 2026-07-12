# Phase 2 — Factored association cost (the ablation surface)

Goal: make appearance / uncertainty / motion **independent, weighted toggles**
without touching the Hungarian solver — and prove the refactor changes nothing
when only IoU is on.

## What shipped

- **[`tracking/cost.py`](../src/visiontrack/tracking/cost.py)** — the factored cost:

  ```
  cost = w_iou · motion  ⊕  w_app · appearance  ⊕  w_unc · uncertainty
  ```

  with a hard gate (min IoU, class match, optional Kalman Mahalanobis). Terms:
  - `motion_distance` — `1 − IoU` (default) or `1 − GIoU`.
  - `appearance_distance` — cosine distance between re-ID embeddings (RQ1 hook;
    inert until embeddings exist in Phase 3).
  - `uncertainty_distance` — normalized Mahalanobis, folding the gate into a
    graded cost (RQ3 hook).
  - `build_association_cost` — assembles the gated, weighted matrix for
    `associate()`. Pure NumPy, fully unit-tested.

- **[`tracking/config.py`](../src/visiontrack/tracking/config.py)** — new config
  fields `w_iou` (1.0), `w_app` (0.0), `w_unc` (0.0), `use_giou` (False); every
  branch of the cost is now a config field, so a variant is a config override.

- **[`tracking/tracker.py`](../src/visiontrack/tracking/tracker.py)** — `_match`
  now builds inputs (IoU, optional GIoU motion, class-mismatch mask, Kalman
  gating distances, appearance hook) and delegates to `build_association_cost`.
  The solver call is unchanged.

## Design contract (and why it holds)

With the defaults `w_iou=1, w_app=0, w_unc=0, use_giou=False`:

- `cost = 1·(1 − IoU) = 1 − IoU`  and  `max_cost = 1·(1 − iou_thresh)`;
- appearance/uncertainty terms are gated behind `w > 0`, so they are never added;
- the forbidden mask (IoU < thresh, class mismatch, Mahalanobis gate) is built
  exactly as before.

⇒ the cost matrix is **bit-identical** to v1. `tests/test_cost.py::test_defaults_reproduce_one_minus_iou`
asserts this directly.

## Acceptance (met) — bit-identical MOT17 val

Re-running the Phase 0 command after the refactor:

```
             MOTA   IDF1   HOTA   DetA   AssA   IDSW
Phase 0    0.469  0.570  0.497  0.423  0.587    188
Phase 2    0.469  0.570  0.497  0.423  0.587    188   ← identical
```

Command: `visiontrack eval --dataset mot17 --split val --detector FRCNN`.
All 231 tests pass (10 new `test_cost.py` + the existing 221 tracker/eval tests,
which exercise the refactored `_match` unchanged); ruff clean.

## What the hooks do now

- **Appearance** (`w_app > 0`): the tracker looks for `feature` on tracks and
  detections; until Phase 3 adds the per-track embedding gallery, tracks have no
  feature, so the term is skipped and behavior is unchanged
  (`test_appearance_hook_inert_without_features`).
- **Uncertainty** (`w_unc > 0`): fully functional now — it reuses the Kalman
  gating distances as a graded cost. Off by default; the controlled study of it
  is Phase 5.
- **GIoU** (`use_giou=True`): switches the motion term; useful when detections
  and predictions don't yet overlap.

## Notes

- The solver (`core/assignment.py`) and the whole `core/` package are untouched.
- Heavy deps unchanged; no new dependencies in this phase.
