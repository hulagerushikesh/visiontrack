# Box-gate ablation — paired input milestone

Completed 2026-10-23. The [registered one-switch study](BOX_GATE_ABLATION_PROTOCOL.md)
now has a separate, input-only generator. **No new tracker comparisons or
held-out tracker outcomes have been produced.** The registered recipe, numerical
acceptance rules, old traffic-study files and production tracker are unchanged.

## What we finished, in plain language

Before comparing the tracker with its rejection check on versus off, we need a
fair test: the same objects following the same paths, with exactly the same
imperfect detection rectangles going into both versions.

This step builds those numbers and checks them. They are toy numeric objects,
not recordings of people. The generator does not decide whether either version
tracks them better. It has **no variant selector**: the future experiment runner
must feed the same generated detection stream to each variant.

## Implemented boundaries

- Accept only the new registered split, path, seed and condition combinations,
  after checking both the new protocol's and the parent recipe's exact bytes.
  Reject unknown/wrong-split paths, old seeds, booleans and non-integer seeds
  before constructing the random-number generator.
- Keep true world contacts, ideal boxes, noisy boxes and measured anchors
  separate. Reference IDs are evaluation labels, not person identities or
  detection features. The intended detector inputs are box, score 0.9, class 0
  and `feature=None`, in registered order.
- Preserve the parent projection equations, 300-frame grid, local PCG64 draw
  order, all four conditions, jitter and half-open bottom/top pulse intervals.
  There is no clipping, dropping or ground-truth-based correction.
- Return immutable byte-backed float64 arrays; neither variant should be able
  to change the other's input data. Repeated generation produces identical
  bytes in the tested environment without touching NumPy's global RNG.
- Supply a separate detector-stream fingerprint binding frame indices, boxes,
  score, class and feature policy. It excludes reference IDs, contacts, variants
  and evaluation results. The full input manifest separately binds truth,
  draws, observations, recipe hashes, selectors and the NumPy version.
- No tracker construction, inference, file export, camera access, network call
  or old run-opening claim. Held-out *input generation* is supported for a later
  input-digest freeze; this milestone generated only new development random
  inputs, not new held-out observations or any new tracking outcomes.

The new `BoxGateInputs` type and manifest formats are separate from the original
traffic-v1 `SceneInputs`. We did not inject new paths into its frozen generator,
alter its source or relabel the already opened v1 evidence as untouched.

## Verification performed

**152 input tests pass**, including every one of the **120 development input
combinations** (three paths × ten seeds × four conditions).

The tests additionally check:

- Four-condition pairing of true paths and noise, clean/noisy projection pairs,
  and exact clean bottom-contact recovery.
- Independent scalar arithmetic for all three development paths and four
  conditions at endpoints and every pulse boundary. A per-frame/object PCG64
  oracle checks draw order throughout all 300 frames.
- Immutable ownership, fresh manifest dictionaries, self-excluding JSON hashes,
  and detector fingerprints that change with actual inputs but not truth labels.
- Same-input fingerprints for the two future variants, selector/integrity
  failures before random generation, and unchanged global random state.
- A test guard forbids constructing a tracker or calling the old scene
  generator throughout this new test module.

Source:
[`experiments/box_gate_scene.py`](https://github.com/hulagerushikesh/visiontrack/blob/main/experiments/box_gate_scene.py).
Tests:
[`tests/test_box_gate_scene.py`](https://github.com/hulagerushikesh/visiontrack/blob/main/tests/test_box_gate_scene.py).

From the repository root:

```bash
python -m pytest tests/test_box_gate_scene.py tests/test_box_gate_protocol.py
```

Input checks and fingerprints are not accuracy evidence. No universal numerical
bit-parity claim follows from replay under one NumPy/runtime environment. The
dataclass is not an untrusted-record validator; a future replay adapter must
revalidate provenance and inputs before executing either tracker variant.

## What is still left

1. The [development reference scorer](BOX_GATE_SCORING.md) is now tested on
   hand-worked rows, retaining all 37 endpoints. The [replay adapter](BOX_GATE_REPLAY.md)
   is implemented/tested with doubles, including the single-switch configuration,
   detector-only handoff and fresh/reset/fresh checks. Actual new tracker
   comparisons remain unmeasured; the full export/decision harness is next.
2. Build full paired exports and test the acceptance/no-effect/failure rules
   using hand-worked examples before running the committed development grid.
3. Freeze the complete reviewed harness, environment and new held-out input
   hashes, then open that grid once through a separate guarded execution gate.
4. Interpret all results, including regressions. Only later consider real-data
   transfer, production changes or a Python/C++ handoff.

The next engineering step needs no new footage or owner action. The volunteer
recording rehearsal remains useful but is a separate task, not a dependency of
this synthetic ablation.
