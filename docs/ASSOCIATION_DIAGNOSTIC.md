# Why did this detection not match this track?

`lab-initiation` explains births, confirmation and disappearance. The separate
`lab-association` command answers the next, narrower engineering question:
**was this particular track/detection pair offered, blocked, or not selected?**

This is an unreleased checkout feature, added after the published 0.4.0 package.
Use a current source checkout (`python -m pip install -e ".[lab]"`); installing
0.4.0 from PyPI alone does not provide this command. No new release is claimed.

## Use it on an existing saved run

Choose a frame, a track ID that existed before association at that frame, and
the original detection key from the [initiation trace](INITIATION_DIAGNOSTIC.md).
Detection keys are not array positions; key 7 can be the first detection.

```bash
visiontrack lab-association BUNDLE --variant bytetrack \
  --frame 1 --track-id 1 --detection-index 7
```

Replace these illustrative selectors with keys in your own bundle. The current
synthetic demo's keys can differ. Add `--json` to emit only canonical
`visiontrack.association-explanation/v1` JSON to standard output. Errors go to
standard error with exit code 2 and no partial JSON. No `--write` mode exists.
Shell redirection can save the separate explanation outside the sealed bundle.
The Lab browser does not import this new contract yet.

## Read the result

The output lists all three production stages: confirmed/high-score,
confirmed/low-score recovery, and tentative/leftover-high-score. For each stage
it says whether the selected track and detection were actually offered.

| Result | Meaning | What it does not establish |
| --- | --- | --- |
| Pair not offered | One or both inputs were absent from that stage | No gate was tested for that pair there |
| `blocked_by_gate` | One or more actual IoU, class or Kalman gate tests failed | Disabling a gate would improve tracking |
| `above_cost_limit` | No hard gate failed, but the actual cost exceeded the solver's acceptance ceiling | A correct physical match was rejected |
| `eligible_not_selected` | Cost was eligible but the one-to-one solver did not select the pair | The exact counterfactual reason, or a better alternative assignment |
| `selected` | The production solver returned the pair | Correct physical identity or a public confirmed box |

For an offered pair, all failed gates are retained, together with predicted
track box/class, IoU and its minimum, squared Kalman distance and hard limit,
actual gated solver cost/ceiling, and the returned partners of the selected
track and detection. An eligible pair may lose to another assignment; the
returned partners are facts, not a new optimization or a causal proof.

The recovery stage disables the **hard** Kalman gate. A numeric distance can
still be present if the soft uncertainty cost is enabled; a null hard limit
means disabled, not failed or zero. Equality passes the IoU, Kalman and cost
boundaries. Class `-1` is agnostic. The `above_cost_limit` case is kept distinct
because optional GIoU motion can exceed the existing cost ceiling even when
the raw IoU gate passes. This tool reports that behavior without changing it.

For example, a low-score detection may never meet a confirmed track that was
already matched in the high-score stage. Calling that a Kalman rejection would
be wrong: the pair was not offered to recovery at all.

## Why trust the numeric explanation?

The observer uses the real tracker's computed matrices and its **single**
production solver call. It does not reconstruct gates or run another matcher.
A small protected solver seam leaves ordinary arithmetic and assignment intact.
The shared initiation replay starts at the experiment boundary, preserves warm-up
and continues through the entire saved experiment. Its canonical public output
must match the saved track SHA exactly before any explanation is returned.
Source hashes before/after replay also have to agree. Corrupt input, missing
selectors, an inactive/newborn target track, changed implementation, missing
observation hook or differing output causes refusal.

Only one source frame, three stage summaries and at most one offered pair are
exported. No quadratic matrix is retained. The existing 20,000 detection/track
row limit still applies to that frame. Replay cost is **not** bounded to one
frame: full saved-run replay and its input/output memory are still required.
No footage, detector, network input, camera or external model is accessed.

The explanation carries run/input/output fingerprints, settings and executing
source hashes. These are reproducibility records, not publisher authentication.
Run-local track IDs do not identify people. No accuracy, accepted tracker fix,
default change or C++ behavior port follows from this diagnostic.

## Checks

Hand-built tests cover individual/simultaneous gate failures, inclusive bounds,
class-agnostic matches, competition, disabled hard gating with soft distance,
GIoU cost rejection, unoffered low-score inputs, sparse keys and warm-up. A
production-matrix boundary test ensures distances are observed, not rebuilt.
Observer/plain-tracker runs compare exact outputs, input bytes, solver call
counts and actual cost bytes across seven settings. Existing initiation v1
conformance bytes remain unchanged apart from honest executing-source provenance.
Clean wheel and source installs exercise both the API and console command;
normal CI retains those install checks.
