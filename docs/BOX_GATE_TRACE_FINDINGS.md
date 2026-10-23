# Internal traces: where the gaps and extra counts arise

**2026-10-23. New exploratory development replay, not new validation.**
The [committed wrapper](BOX_GATE_TRACE_REPLAY.md) ran from clean revision
`dd653aa` over all **120 development pairs / 240 variants**, with one fresh
traced pass of 300 updates per variant: **72,000 recorded updates**. Every public
output matched its original saved output **exactly**. There were no errors,
skips, retries or held-out data reads. The original study remains a **failure**;
we have explained some mechanisms, not accepted a better tracker.

## What is now finished

- [x] Execute the complete committed development diagnostic in its fixed order.
- [x] Retain all 240 traces, attempts, plan and complete manifest outside Git.
- [x] Independently check the saved records with a new read-only auditor.
- [x] Explain concrete startup, pulse-boundary and pre-pulse counting examples.
- [ ] Choose/register the next narrower intervention before observing outcomes.
- [ ] Validate any accepted behavior on genuinely fresh, representative evidence.

The trace bundle is about 273 MiB and stays local. The compact checked-in
`experiments/box_gate_trace_v1_evidence.json` pins its manifest/plan, execution
code and post-run auditor/tests/output. It does not substitute for the raw files.

## 1. Startup misses are confirmation, not failed detection

In the solo, seed 2001, box-error-only baseline trace:

| Frame | Internal event | Public result |
| --- | --- | --- |
| 0 | Spawn ID 1, tentative, one hit | No box |
| 1 | Match ID 1, tentative, two hits | No box |
| 2 | Match ID 1, confirmed, three hits | ID 1 becomes visible |

The tracker has a detection/track internally before publishing it. This explains
these particular startup misses under the frozen `n_init=3` policy; it is not
evidence that the detector failed or that we should remove confirmation.

## 2. A shape pulse triggers a gate veto and a new confirmation delay

For that same baseline at frame **135**, the existing ID-1 prediction and
detection have IoU **0.6357672271568077**, above the association threshold 0.3.
Class mismatch is false. However, their recorded **4D xyah squared Mahalanobis
distance is 22.83821097524357**, above the active threshold **9.4877**.
The actual forbidden mask is true, the cost is 1.7 versus a maximum 0.7, and
the association returns no match. The low-score recovery stage has no detections.

The trace then shows ID 1 marked missed but still alive, and **ID 2 spawned as
tentative**. Frame 136 gives ID 2 its second hit; frame 137 confirms its third
hit and publishes ID 2. Frames 135–136 show no public box. ID 1 has not yet been
deleted: a confirmed but stale track is not published by this implementation.

This is a directly recorded rejection/lifecycle chain in this toy case. It does
not prove every missing box has that cause, or that every gate veto is incorrect.
The full 4D gate combines centre, aspect and height; the trace does not isolate
which component should be removed or how an alternative would affect safety.

Across the fixed selected windows, the baseline has **1,329 candidate-pair
vetoes attributable solely to that gate** despite eligible IoU/class: 665 in
box-error-only, 664 combined, none in control/perspective-only. These are matrix
candidate pairs, including alternative/stale-track candidates—not 1,329 unique
errors, people, independent trials or a population rate. Gate-off computes no
distance in this configuration; its `null` distance is **not zero**.

## 3. Keeping the ID does not preserve the counting anchor

Gate-off accepts ID 1 with detection ordinal 0 at frame 135. Its IoU is the same
0.6358; the Mahalanobis calculation is inactive, not independently observed to
pass. The subsequent state update moves the published box's bottom substantially.

For the frozen **affine toy projection**, world Y is `(650 - bottom_pixel_y) / 16.25`:

| Frame | Published ID | Bottom pixel Y | Derived toy world Y |
| --- | --- | --- | --- |
| 134 | 1 | 500.22985510614876 | 9.216624301160076 |
| 135 | 1 | 459.572768021098 | 11.718598891009353 |

The counting line is Y=10. These same-ID public boxes bracket the already saved
crossing at **134.31310297954988**, about **15.1869 frames early** relative to
truth at 149.5. The imposed observation-shape error changes the box-state anchor;
a stable ID does not make that contact trajectory physically correct. This is
toy geometry, not calibrated measurements from a real camera.

## 4. An extra directional count can occur without an ID switch or gate veto

In separated-opposing, seed 2001, box-error-only, the previously noted extra
crossing occurs **before** the frame-135 pulse. The trace shows ID 2 consistently
matched to detection ordinal 1 at frames 126–129. Its active gate distances at
frames 127 and 128 are about **0.0765** and **0.0612**, well below 9.4877;
the pair is accepted in both frames.

| Frame | Published ID-2 bottom world Y |
| --- | --- |
| 126 | 10.08687843936531 |
| 127 | 9.969571795875705 |
| 128 | 10.072787077364815 |

At frame 128 the **predicted** bottom world Y is 9.914707676141978; the matched
measurement update changes it to **10.072787077364815**. Thus the post-update
box anchor moves back across the line while the association keeps the same ID
and detection ordinal. The original counting rule keeps a first event **per
ID and direction**, allowing the negative crossing at about 126.7406 and the
extra positive crossing at **127.29480328576642**. That positive event is on the
wrong path to match the positive reference crossing. Both variants retain it.

This localizes this example to updated-anchor/line-crossing stability rather
than an ID switch or a rejected association. It is consistent with the supplied
noisy observations, not proof of a Kalman arithmetic bug or a universal reason
for count errors. Smoothing, a different contact state or crossing hysteresis
could have costs such as latency/missed short passages; none is an accepted fix.

## Audit and reproduction

The new stdlib-only `experiments/box_gate_trace_audit.py` verifies all **482 trace
files**, all **365 original development files**, historic committed code hashes,
case/attempt order, fixed selection, complete saved-output parity and selected
frame publication eligibility. It checks **55,578 recorded association stages**
across **18,526 selected frame/variant records**: actual masks, default costs,
solver proposals, accepted matches and unmatched indices.

It does not execute a tracker/generator/scorer or reopen held-out data. It does
not recompute filter/covariance math, independently regenerate every payload
receipt, prove the physical correctness of a box or independently witness the
execution. Hand-worked event-diagram/forgery tests are not new measurements.

```bash
python -m experiments.box_gate_trace_audit \
  --trace /absolute/path/to/the/retained/trace/bundle \
  --development /absolute/path/to/original/development/bundle \
  --root /absolute/path/to/visiontrack
```

Default output is JSON on stdout. Optional `--output` creates a **new** external
companion; it refuses overwrite and repository/input-bundle destinations. Neither
the original evidence nor the completed trace is rewritten by the audit.

## Next decision

The follow-up must separate **association sensitivity to box shape** from
**contact-anchor/crossing stability** while retaining joint ID, localization and
counting safety. Position-only gating alone is not established as a solution;
counting-only stabilization would not establish identity/localization accuracy.
Design/register a narrower comparison with genuinely fresh held-out cases before
new outcomes, and preserve the earlier negative result. Real-data transfer,
owner usability and practitioner discovery remain separate gates.

No production setting, C++ implementation, release, outreach or website behavior
was changed in this diagnostic milestone.
