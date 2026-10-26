# Observation availability v1 — complete development findings

Checkpoint: **2026-10-26**. All **12 cells / 36 passes** completed from committed
design `45d3250f14433ca3c47b1b398298205f15964048`. No failures, skipped cells,
selective retries, tuning, new tracker settings or C++ changes.
See the [prospective protocol](OBSERVATION_AVAILABILITY_PROTOCOL.md) for the
fixed question, geometry, recipe, measurements and stop rules.

## The finding in plain language

**A missing public box, a changed ID and an apparently recovered ID are different
outcomes.** We now have one reproducible small example that separates them:

- With distinct observations, both references stay matched after startup.
- Removing one observation for 4 or 12 frames creates misses, but the old ID
  resumes immediately when the box returns. Missing output did not necessarily
  mean lost internal identity.
- A 36-frame missing-observation episode produces a new ID and two additional
  confirmation misses after observations return.
- Supplying one shared box for 36 frames has the **same total miss count** as
  that missing-box episode, but **two ID switches instead of one**. The full
  correspondence history differs; the headline miss count cannot explain it.

These are outcomes for **one deterministic parallel-motion geometry**, not a
better tracker, a realistic detector benchmark or a causal explanation of MOT17.
The shared-box condition changes shape/location as well as observation support.
It does not isolate a geometry-free effect of “ambiguity.”

## Every registered cell

All totals include **four startup misses** (two references × frames 0–1).
FP is zero in all cells. Recovery starts at frame `12 + duration`.

| Episode frames | Condition | Total FN | Extra FN vs distinct | IDSW | Fragmentations |
| --- | --- | --- | --- | --- | --- |
| 4 | distinct | 4 | 0 | 0 | 0 |
| 4 | unchanged control | 4 | 0 | 0 | 0 |
| 4 | missing second | 8 | 4 | 0 | 1 |
| 4 | shared union | 8 | 4 | 0 | 1 |
| 12 | distinct | 4 | 0 | 0 | 0 |
| 12 | unchanged control | 4 | 0 | 0 | 0 |
| 12 | missing second | 16 | 12 | 0 | 1 |
| 12 | shared union | 16 | 12 | 0 | 1 |
| 36 | distinct | 4 | 0 | 0 | 0 |
| 36 | unchanged control | 4 | 0 | 0 | 0 |
| 36 | missing second | 42 | 38 | 1 | 1 |
| 36 | shared union | 42 | 38 | 2 | 1 |

For the degraded 4-/12-frame cells all additional misses occur during the episode;
both references first recover with their pre-episode IDs at delay zero. In each
36-frame degraded cell there are 36 episode misses and two recovery misses.
All settled-warmup strata have zero failures. The complete unrounded CLEAR
metrics and every frame/failure remain in the local bundle; no length-averaged
score or best-looking cell was selected.

### Why “first recovery had the same ID” is not enough

Before each episode, reference 1 is matched to track 1 and reference 2 to track 2.
In the 36-frame missing-second cell, reference 1 resumes at frame 48 with ID 1;
reference 2 first resumes at 50 with ID 3 (delay two).

In the 36-frame **shared-union** cell:

| Frame | Reference 1 scored match | Reference 2 scored match |
| --- | --- | --- |
| 11, before episode | 1 | 2 |
| 12–47, shared observation | missing | 2 |
| 48–49, distinct boxes returned | missing | 2 |
| 50–67 | 2 | 3 |

Reference 2's **first** recovery match is ID 2 at 48, so the registered first-match
`same_id` field is true. Nevertheless, at 50 its correspondence changes to 3;
reference 1 resumes with 2. Both switches occur at 50. Calling that first-match
field “stable identity recovery” would conceal a failure. The protocol already
required retaining the full history and warned against that interpretation.

The filtered track-2 box has IoU **0.740042 / 0.559188** against references 1/2
at 48. Canonical previous-match priority retains its correspondence to reference
2. At 50 those overlaps are **0.776630 / 0.481523**; the latter is below 0.5.
Public track 3 is now present and overlaps reference 2 at **0.960006**. The
saved correspondence changes accordingly. Raw supplied boxes, filtered public
boxes and evaluator history are not interchangeable.

This explanation uses saved outputs, not an actual-call association/Kalman trace.
It does not establish why the tracker selected a particular detection internally.
The end-of-window matches above are a descriptive reading of the required saved
history, not a new prospectively registered acceptance endpoint.

## Verification and provenance

- All three passes per cell are byte-identical: fresh, reset and second fresh.
- All three unchanged controls have exact input, output and scored-result equality
  with their duration-matched distinct cells.
- **592 unique cell frames / 1,080 supplied boxes** are retained. Including the
  repeatability passes, the tracker performed 1,776 frame updates. Repeated
  passes are not extra independent examples or statistical samples.
- A separate read-only calculation checked all **62 manifest members**, recorded
  harness/package hashes against Git, all 12 cells, input geometry, 36 saved
  output passes, 165 failure events, strata, recovery fields and paired deltas.
- That audit used scalar intersection/union and exhaustive two-reference partial
  assignments to check the recorded IoU/previous-priority matching objective in
  all 592 frames. There were no nonunique optimum frames in these records.
  FN/FP/switch/fragmentation counts, TP, MOTA and MOTP agree with that calculation.
  It executed no tracker. This was a work-session read-only arithmetic audit,
  not a separately packaged evaluator, blind reviewer or real-data validation.
- **1,098 Python tests pass, one slow test deselected**, including 28 new
  hand-written geometry/scoring/replay-double tests and 25 prior inventory tests.
  Ruff, strict documentation and offline staged-review controls pass. Remote CI
  and website deployment are separate from these local checks.

Runtime: Python **3.12.9**, NumPy **2.3.1**, Darwin arm64, little endian.
Package source remains exactly at `7308dfbe8f79da61b56beed05784e56b512c156a`.
The receipt records all package files, implementation/test/recipe/protocol hashes
and environment. Actual local bundle, outside both repositories:
`../visiontrack-walkthrough/observation-availability-zSW3bU/study`.

| Artifact | SHA-256 |
| --- | --- |
| Frozen recipe | `2b66b7cc1cc0a6113d31a434e9a7358a690ed029c5f89d602c1ffa0b269de558` |
| Pre-run method | `6b187bc6fc1ec5959a74e26f172ab959bebd40dff2d89de5c25499f4dc97c750` |
| Complete summary | `88012af5130ecaedf8176926713711e9c88786325492d88fed7b71b8795b24b0` |
| Manifest | `1492dc49411f47d063e9b5b158ee070aa4f04f80bcc9ba4a1ee8a5ab9836b637` |

Preview without constructing a tracker:

```bash
PYTHONPATH=src:. python -m experiments.observation_availability
```

An intentional reproduction requires the committed frozen files/package source,
the recorded runtime for exact bytes and a **new external output directory**:

```bash
PYTHONPATH=src:. python -m experiments.observation_availability \
  --output /path/to/new/external-directory --write
```

Reproducing creates new development outcomes, not fresh validation. Do not
overwrite the existing bundle or modify the recipe to improve these numbers.

## Decision and next milestone

**Retain unchanged defaults.** This is a completed observation characterization,
not an accepted intervention. It provides a clearer research target: expose
uncertain continuity rather than promise that a surviving/returning ID is correct.

- [x] Freeze the question and all conditions before actual tracker outcomes.
- [x] Execute the complete grid with exact repeatability and unchanged controls.
- [x] Audit saved records, retain the short-gap null ID effect and long-gap harms.
- [x] Write an understandable finding without manufacturing physical validation.
- [ ] Next bounded task: specify a **diagnostic-only continuity warning** study:
      what detector/track information it can use without GT, what counts as a
      warning, and fresh controls for genuine size/motion changes and false alarms.
      Fix usefulness/error criteria before implementing or testing a warning.
- [ ] Test representative permitted real observations and independent labels
      before claiming transfer or accepting changed tracking behavior.

No new pixels, consent records, models, outreach, release or C++ port. C++ remains
the exact implementation of accepted reference behavior; diagnostic findings
alone do not justify modifying it.
