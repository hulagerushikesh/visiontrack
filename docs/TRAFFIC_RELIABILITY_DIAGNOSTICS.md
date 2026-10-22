# Tracking and contact-error diagnostics — development milestone

Completed 2026-10-22. The [development runner](TRAFFIC_RELIABILITY_RUNNER.md)
now reports tracking continuity and ground-contact position errors alongside
its crossing scores. The [frozen protocol](TRAFFIC_RELIABILITY_PROTOCOL.md),
production tracker, original synthetic generator and Python/C++ fixtures are
unchanged. **This is instrumentation and fixture validation, not a completed
traffic study, new tracker, representative traffic accuracy result or gain.**

## The questions we can now keep separate

Imagine a person walking steadily across a room. A tracker could count one
crossing correctly but still lose them briefly, change their ID, or estimate
the wrong position on the floor. One count cannot answer all these questions.

- **Matched object-frames:** for how many expected observations does a reported
  tracker box match the ideal reference box at IoU ≥0.5? IoU measures overlap.
- **Missed object-frames:** expected observations without such a match. These
  include the baseline's initial confirmation delay; they are not filled in.
- **False-positive rows:** reported boxes without a reference match. They are
  not silently discarded just because another box tracks the object correctly.
- **ID switches:** a reference object is matched to a different local tracking
  ID than its previous match. IDs need not equal reference IDs to be correct.
- **Fragmentations:** the existing evaluator's transition from matched to
  unmatched. Its exact existing definition is retained, not redefined here.
- **Contact-position error:** how far a box-derived ground position is from
  the known contact point in this toy scene, separately from the above counts.

Completeness is matched object-frames / true object-frames, not proof of a
single uninterrupted ID, a dense real trajectory or persistent person identity.
In the simple 300-frame control smoke check, the unchanged tracker returns 298
matched rows and two initial misses, no ID switch and no false-positive row.
The expected crossing can still be correct despite those two initial misses.

## Two position measurements, with different denominators

**Observation contact error** uses the supplied detection boxes, whose reference
correspondence is known from the generator. It includes **every true
object-frame**, whether or not the tracker returns a matching box. This
describes the imposed measurement error independently of tracker performance.

**Matched-track contact error** uses the actual returned tracker boxes, only
where the existing IoU evaluator establishes a reference correspondence. It is
**conditional on a match**: difficult/missed observations can be absent from
this number. Always read its sample count and completeness alongside the error.
When there is no match, the position estimate is missing; its mean/max error is
`null`, not zero. We do not invent a nearest reference for an unmatched row.

Both measurements report bottom-centre and box-centre separately, using the
exact synthetic inverse projection. Each has sample count, mean Euclidean
distance, mean absolute X/Y error, signed X/Y bias and maximum distance. Per-frame
signed errors are retained for inspection. Units are **toy world units**, not
surveyed metres, validated camera calibration or real-world location accuracy.

For a hand-fed perfect ideal box, bottom-centre equals the simulated contact.
Box-centre is above it and therefore has a nonzero contact bias by construction.
Conversely, a shifted returned box can have position error while its supplied
observation remains perfect. Truncation can corrupt bottom-centre as well.
These checks validate the measurement distinction, not a universal anchor rule.

## Where and when the failures occur

The report includes all-scene summaries and the frozen true-Y regions:

- region 0: `[0, 20/3)`;
- region 1: `[20/3, 40/3)`;
- region 2: `[40/3, 20]`.

Classification uses the exact stored float64 boundaries without an added epsilon.
Each region also has three scheduled phases: bottom-pulse frames `[135,165)`,
top-pulse frames `[210,240)`, and all remaining frames. These **time labels also
apply to control conditions**, where box perturbation is disabled. They do not
claim a control box was truncated. Condition is recorded separately.

The evaluator runs **once continuously across all 300 frames**. Region/phase
summaries partition that correspondence and its failures afterwards; they do
not reset history or independently rematch each group. Otherwise an ID switch
at the start of a pulse could disappear from the report.

False positives have no true object and hence no true Y region. Their counts
are reported overall and by scheduled phase. Regional false-positive fields
are `null` (not attributable), not misleading zeroes or arbitrary assignments.
Empty reference strata have undefined completeness and localization means.

## Existing evaluator, provenance and tests

The adapter uses the pinned package's `MotAccumulator` at IoU 0.5, with ideal
reference boxes and public output rows. It reads the accumulator's private
last-correspondence map **only for objects not missed in the current frame**.
This experiment-only adapter avoids a second assignment that might disagree
on ties; it is not a new public evaluator API. The runner verifies all package
source against the frozen baseline before execution and again after diagnostics,
including import origin checks. Drift must fail, not silently change evaluation.

All summary TP/FN/ID-switch/fragmentation totals and phase FP totals are checked
against the same evaluator's public result. Independent tests compare complete
fixtures against `evaluate_sequence`. Reference geometry enters scoring only,
never tracker detections or association. No tracking algorithm is run by the
diagnostic function itself, and held-out scene metadata is rejected.

The returned development record now includes `diagnostics`: overall and joint
region/phase summaries, sample counts, per-object-frame matching/error records,
canonical failure records, protocol/input hashes and limitations. It remains an
in-memory experiment record, not the Lab's supported `report.json` format or a
completed exported study bundle. The CLI adds a compact tracking summary.

```sh
python -m pytest tests/test_traffic_diagnostics.py tests/test_traffic_runner.py
python -m experiments.traffic_runner --scenario solo --seed 101 --condition control
```

Fixtures cover perfect, empty, shifted, extra, switched and fragmented outputs;
all four conditions on the three development geometries; exact region/pulse
boundaries; empty groups; missing-error semantics; public evaluator agreement;
invalid data; and held-out rejection. Ideal outputs hand-fed to diagnostics are
test oracles, **not claims about what the tracker achieves** on perturbed inputs.

## Next gates

1. Reproducible full-result export and complete development summaries: all four
   absolute conditions, paired differences, interaction and per-scenario seed
   means/ranges, with negatives retained. Seeds are noise repeats, not new sites.
2. Freeze the complete tested harness revision and input digests.
3. Only then open the one-pass held-out tracker evaluation. No tuning, claimed
   improvement, real-data transfer, flow-assignment validation or C++ port follows
   automatically from this diagnostic milestone. No owner recording is needed yet.
