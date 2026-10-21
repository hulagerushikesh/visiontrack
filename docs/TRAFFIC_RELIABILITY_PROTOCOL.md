# Frozen traffic mechanism protocol — v1

Frozen 2026-10-21 **before generating tracker comparisons**. This is an executable
specification's input contract, not an executed experiment or registered clinical
study. The [probe plan](TRAFFIC_RELIABILITY_PLAN.md) explains the broader aim.

## What we are testing, in ordinary language

An object can move steadily while its camera image changes speed or its detection
box jumps. We will reproduce these two effects separately, then together, and
check whether they change tracking and a simple counting decision. We are not
testing face recognition, long-term identity, real road-user behavior, or a new
tracker. No images, volunteers, cloud services or external replies are required.

**This step freezes the recipe only.** Geometry checks may inspect every planned
input; tracker outputs, comparative scores and held-out tracking are not run.

## Frozen artifacts and integrity

The machine-readable settings are
[`experiments/traffic_protocol_v1.json`](https://github.com/hulagerushikesh/visiontrack/blob/main/experiments/traffic_protocol_v1.json).
Both that file and this document have byte-level SHA-256 entries in
[`experiments/traffic_protocol_v1.sha256`](https://github.com/hulagerushikesh/visiontrack/blob/main/experiments/traffic_protocol_v1.sha256).
From a local checkout, run:

```sh
python -m experiments.traffic_protocol
```

This verifies the checked-in recipe, prints identifiers, and exits without
running a tracker or writing results. A hash establishes artifact integrity, not
research validity or the quality of the eventual implementation. The Git commit
records the freeze; any amendment requires a new protocol version, rationale and
digest before further outcomes. Do not silently refresh v1 hashes after results.

The baseline is the NumPy tracker at commit
`16c287a6b18c5c142a28e4bce70b3232946459db`, with **every** `TrackerConfig` field
recorded explicitly. Later default changes cannot alter this experiment. Future
runs must record their actual code revision and reject unreviewed baseline drift.
This step changes no tracker, existing synthetic generator or parity fixture.

## Scene and timing

- Frames `t=0..299`, 30 fps, timestamps `t/30`, image 1280×720. Update the tracker
  once per frame, reset for each run. No skipped updates or resampled time.
- World coordinates are a toy flat plane: X in `[-6,6]`, Y in `[0,20]`, arbitrary
  metre-like units, not surveyed/calibrated measurements. Every object exists in
  all 300 frames; `P(t)=start+(end-start)*t/299`. No acceleration or births/deaths.
- Each surrogate object has width 0.6, height 1.7, class 0 and score 0.9. These
  are not validated human/car dimensions or class-specific motion models.
- For column vector `(X,Y,1)`, project `H P` then divide by its third coordinate
  `q`. Use the manifest's affine or perspective H. The two maps agree along the
  centreline at Y=0 and Y=20, not at intermediate positions. Perspective changes
  both apparent speed and size; this is a **joint projection effect**, not an
  experiment isolating motion from scale. The camera itself never moves.
- The projected true ground contact is `(u,v)`. The ideal upright sprite box is
  `[u-w/2,v-h,u+w/2,v]`, with `w=60*0.6/q`, `h=100*1.7/q`. This is a specified
  toy observation model, not full 3D rendering or perspective projection of an
  object's entire body. Ground truth retains ideal boxes and separate contacts.
- Validate H determinant magnitude >1e-9, finite inputs/outputs, positive
  homogeneous denominator >1e-6 for projection **and inverse**, positive boxes
  fully within the image, and inverse round-trip absolute error ≤1e-9. Reject
  invalid scenes/outputs rather than clip, clamp or silently omit them. Inverse
  anchor positions outside the ground ROI remain valid diagnostic positions;
  never clamp them into a crossing. Invalid tracked boxes invalidate the run.

The six named paths and disjoint seed lists in JSON are the complete scenario
set. Development: `solo`, `opposing`, `converging`, ten seeds each. Held-out:
`offcentre`, `close_opposing`, `slanted`, ten different seeds each. The unit is
a whole scenario, not an object, frame or seed. These few hand-designed scenarios
are mechanism probes, not a representative sample of traffic or independent
camera sites. Seeds repeat observation noise only; they do not create new paths.

## Paired observation conditions

| Condition | Mapping | Box error |
| --- | --- | --- |
| control | affine | off |
| perspective_only | perspective | off |
| box_error_only | affine | on |
| combined | perspective | on |

For each scenario/seed, create `Generator(PCG64(seed))` anew. For every frame in
order, then object in ascending ID, draw four `uniform(-1,1)` values for edges
`x1,y1,x2,y2`. Draw them even when error is off. Use the same draws and paths in
all four conditions; no branch-dependent RNG consumption. Record NumPy version.
No shuffling, missing detections, appearance, score degradation, false positives,
automatic mutual occlusion, detector inference or camera motion in v1.

When error is on, add `0.02*z*[w,h,w,h]` to ideal edges. Then subtract `0.35*h`
from bottom edge on frames `[135,165)`; add `0.35*h` to top edge on `[210,240)`.
The abrupt pulses are deliberately imposed, not measured detector statistics.
Apply both pulses to every object, keeping width, height and q from its **ideal**
box. Require validity without repair. Always compare to unperturbed ground truth.
Record four-condition input digests; changes to error must not change truth.

## Anchors are measurements, not identities or interventions

True contact, ideal-box centre, observed bottom-centre and observed box-centre
must be separate arrays. Both measured anchors are inverse-projected using the
exact H; calibration error is absent in this experiment. Only an **unperturbed**
bottom-centre equals true contact under this sprite model. Centre is above the
ground; truncation/jitter can invalidate bottom-centre as a contact estimate too.

Track the same observed boxes once with the frozen baseline. Derive both anchors
from its returned boxes; anchor reporting does not change association. Primary
counting uses bottom-centre; centre is a secondary sensitivity diagnostic, not
an improvement selected after seeing scores. Missing returned rows remain gaps;
consume public outputs as returned, including any coasted rows. Do not synthesize
new rows or filter outputs using ground truth. IDs are local to each run.

## Crossing and window semantics — freeze before coding the scorer

This is one directed **line crossing**, not a complete origin/destination flow.
Ground truth comes from true contacts; predictions come from returned track-box
anchors. A pair of consecutive frame samples for the same ID emits:

- positive direction when `Yprevious < 10 <= Ycurrent`;
- negative direction when `Yprevious > 10 >= Ycurrent`.

Require a one-frame gap exactly; no interpolation through missing rows. Starting
on the line emits nothing until a later eligible pair. Arrival at the line counts;
dwelling on it does not emit again. A subsequent departure followed by a return
can emit the opposite direction. Keep only the **first event per ID per
direction**; no attempt to recognize two IDs as the same physical object.

For an eligible pair, compute linear fraction `(10-Yprevious)/(Ycurrent-Yprevious)`
and interpolate frame time and X. Accept X in `[-6,6)`. Event time is a real-valued
frame index, not rounded. Count in windows `[0,30)`, `[30,60)`, ... `[270,300)`
independently by direction. Exactly-on-boundary events belong to the later window.
Use float64 throughout; do not add an unstated epsilon to comparisons.

Match true/predicted events one-to-one if direction agrees, absolute frame-time
error ≤30, and absolute X error ≤1. Optimize maximum number of matches first,
minimum total absolute time error second, then total absolute X error; exact ties
use lexicographically sorted `(truth object_id, predicted track_id)` pairs.
Matching must not require a predicted track ID to equal a truth ID. Reject
nonfinite events. Matched events may occupy different counting windows: report
that error rather than silently merging windows.

Report unmatched true events (misses), unmatched predictions (extras), their
**sum** (primary event error), matched absolute time/X errors and matched
wrong-window events. Also report sum of absolute predicted-minus-true counts
over every direction/window. A signed total alone can hide cancelling errors.
No truth match means timing/X summaries are `null`, not zero. No truth events
means recall is undefined, not perfect. The first scorer must have fixtures for
perfect, duplicate, missed, fragmented, reverse, boundary, dwelling, gapped,
wrong-window, spatially ineligible and ambiguous-match cases.

## Diagnostics, comparisons and stop rules

Tracking diagnostics use the existing evaluator with IoU 0.5 and ideal-box truth:
ID switches, misses, false positives and matched-object-frame fraction. Also
report contact localization error separately from tracking matches; do not call
file integrity, inverse consistency or synthetic truth real-world accuracy.
Stratify by true Y region (`[0,20/3)`, `[20/3,40/3)`, `[40/3,20]`), condition and
pulse window. These regions use the JSON float64 boundaries.

For every scenario and seed, report all four absolute outcomes, the three paired
differences versus control, and the interaction
`combined-perspective_only-box_error_only+control`. Show all scenario results and
seed ranges/means; no frame-wise p-values, confidence claims or seed-wise claims
of independent scenes. Zero differences and unfavorable findings stay visible.

No intervention, tuning, automatic winner, acceptance margin or claimed gain is
authorized in v1: this is failure characterization. First pass development
geometry/scorer tests and baseline replay/reset checks, then freeze the harness
commit and input digests before running held-out tracking once. Record all runs
and errors; no selective reruns with favorable seeds. If a specification defect
is found, document it and stop for a versioned amendment. Once opened, this
held-out set cannot be reused as untouched evidence for a later proposed fix;
register that fix, practical acceptance margins and new held-out scenarios first.

Future output must include protocol/digest, actual source revision, baseline
source verification, dependency versions, split/scenario/seed/condition, complete
configuration, truth/detection/output digests, all diagnostics and limitations.
Exact input bytes must be reproducible in the pinned environment; cross-version
floating-point differences must be disclosed, not silently rehashed as parity.

## What remains after this freeze

Implement/test the generator, then replay and score on development inputs before
opening the held-out run. Only later consider predeclared fixes and separately
rights-reviewed real evidence. RQ5/private recording remains a separate study;
C++ and the live website stay unchanged. Nothing here establishes novelty,
practical traffic performance, a partnership or access to another team's data.
