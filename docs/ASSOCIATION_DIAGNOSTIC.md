# Why did this detection not match this track?

`lab-initiation` explains births, confirmation and disappearance. The separate
`lab-association` command answers the next, narrower engineering question:
**was this particular track/detection pair offered, blocked, or not selected?**

This command/API is available in [published 0.5.0](RELEASE_NOTES_0.5.0.md).
Install with `python -m pip install --upgrade "visiontrack-mot[lab]==0.5.0"`.
An existing 0.4.0 installation does not provide it; a website update alone does
not upgrade your local package. A source checkout remains an optional dev route.

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
The Lab can now import this separate explanation alongside a checked initiation
trace. Package and website delivery remain separate; this does not change the
already published 0.4.0 wheel.

## Inspect the explanation in the Lab

For a no-install introduction, open `/lab` and select **Explain a match failure**.
This optional prepared lesson checks a fixed synthetic report, timeline and
association explanation together, then explains overlap, motion rejection and
the resulting new tentative ID in three short steps. It uses an intentionally
small Kalman noise scale (0.001), not the default setting. Full-precision saved
stage results and the frame's lifecycle rows are available under an optional
details section. There is no camera, inference, file selection or Human review
decision. Closing or changing the selected report discards the lesson; it never
replaces or adds evidence to that report. **Try guided demo** remains the separate
confirmation lesson. These teaching examples do not establish real-world accuracy.

For your own saved run:

1. Open `/lab` and import the saved run's `report.json`.
2. Under **Why did a detection become a track?**, import its matching
   `initiation-trace.json`. Select the frame you want to understand.
3. Select **Why did this pair match or fail?**. Choose a track that already
   existed before this frame's association and an original detection key.
   Newly born tracks are excluded; a frame without a usable pair explains why.
4. Run the displayed command using your local 0.5.0 installation. Replace
   `BUNDLE_PATH` with the original saved experiment folder, and redirect to a
   new `association.json` outside that sealed bundle.
5. Select **Import association explanation** and choose that file. Read the
   three stage results and actual numeric gate/cost comparisons. Equality passes
   the bounds. Full precision is retained so rounding cannot hide a failure.

The panel starts closed and is optional. The beginner **Try guided demo** stays
focused on its three confirmation steps; it does not require this export.
Changing the frame, trace, report or selected pair discards the previous panel
or import session. Closing/clearing the panel cancels pending reads. Rejected
and superseded imports cannot leave an old successful explanation visible.

The browser accepts at most 1 MiB of numeric explanation JSON. It checks strict
versioned structure, duplicate keys, nesting, fingerprint, exact report/run
lineage and Python configuration bytes, selected frame/pair, matching detection,
stage input counts/admission, gate/outcome consistency and actual partners
against the already checked initiation trace. It does not recompute Kalman
matrices, run an assignment solver, authenticate the producer or judge physical
identity. A newer producer may inspect an older saved run; producer hashes need
not match the trace exporter, but run/input/output/settings and the selected
detection must agree. Files stay in tab memory; there is no upload or persistence.

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

The **unreleased checkout** now [streams diagnostic replay](DIAGNOSTIC_REPLAY_SCALING.md)
instead of retaining all saved input/output rows. Public 0.5.0 retains the memory
behavior above. The new path preserves full-run history and exact output checks;
it also rechecks evidence files before return. Active-track histories still
grow, so this is not a constant-memory tracker or a speed/accuracy claim.

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
normal CI retains those install checks. The Python-to-browser association check
also generates fourteen small hand-authored synthetic cases, covering all four
offered-pair outcomes, unoffered/below-score inputs, recovery with/without soft
distance, class-agnostic/disabled gates and inclusive IoU/cost bounds. Re-signed
invalid records check semantic refusals independently of content hashes.
Cancellation during reads/hashing, bounded input and rendered React controls
are checked. These are code/static-render checks; browser interaction/visual QA
and practitioner comprehension remain unverified after the earlier access denial.

The prepared lesson also pins all three original exports and checks real
report/trace/pair validation, damaged or mismatched records, late failures,
restart/close cancellation through all seven hashing calls, rendered teaching
steps and application composition. Fresh Python replay must continue to match
its declared numeric stages and lifecycle facts. Its assets are lazy-loaded only
on explicit selection. Code and static rendering checks are not visual or
interaction QA.
