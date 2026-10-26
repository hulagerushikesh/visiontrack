# Corrected coverage and the same first-event trace

Checkpoint: **2026-10-24**. The measurement milestone is complete for this
annotation-only case: [metric v2](EVALUATOR_V2.md), independent
[MOT17 preprocessing](MOT17_PREPROCESSING.md), corrected missed-object coverage,
and an extended actual-call replay of the same first switch. **No new tracking
behavior or accuracy gain is claimed.** Public outputs are unchanged.

## What the corrected miss breakdown says

The saved 1,050-frame outputs still score **TP 25,732 / FN 21,825 / FP 49**,
**IDSW 44**, **Frag 108**, **HOTA 52.37%**, **IDF1 61.32%** under evaluator v2.
Every v2 failure event and CLEAR result is regenerated exactly before the
diagnostic runs. The independently verified MOT17-v2 policy also exactly
reproduces saved public preprocessing on every frame. Score selection precedes
ignore handling separately for each raw-detection pool.

| Descriptive group, checked in this order | V2 missed object-frames | Share | Historical v1 |
| --- | --- | --- | --- |
| No supplied raw detection at IoU ≥0.5 | **19,393** | **88.86%** | 19,387 |
| Overlap exists only below the original 0.1 score boundary | **149** | **0.68%** | 149 |
| Eligible overlaps exist but none survives ignore handling | **270** | **1.24%** | 270 |
| Eligible retained neighbour exists but no canonical scored match | **2,013** | **9.22%** | 2,019 |
| **Total** | **21,825** | **100%** | 21,825 |

The broad lesson survives the corrected correspondence: most missed reference
boxes lack sufficient raw detector overlap. This does **not** prove why: missing
detection, localization, partial visibility or label ambiguity need evidence.
The 2,013 are **not guaranteed recoverable misses** or proven gate failures.
Counts refer to object-frames, not 21,825 different people.

The 270 concern scoring pedestrians whose neighbouring detections were removed;
they are not ignored people incorrectly counted as FN.

| Raw score pool | Input / kept boxes | Maximum disjoint GT/raw-box pairs | V2 missed GT with any retained neighbour | V2 FN-only disjoint capacity |
| --- | --- | --- | --- | --- |
| All scores | 28,406 / 26,338 | 26,241 | 2,162 | 2,116 |
| Eligible ≥0.1 | 28,230 / 26,162 | 26,096 | 2,013 | **1,971** |
| High ≥0.5 | 27,824 / 25,756 | 25,739 | 1,863 | 1,821 |
| Spawn-score ≥0.6 | 27,753 / 25,685 | 25,672 | 1,840 | 1,798 |

All raw-pool retained counts and full-GT capacities happen to remain unchanged
in this case under corrected preprocessing. The FN-only subsets change with the
corrected scorer. Maximum-cardinality matching prevents counting the same raw
box twice, but **1,971 cannot be added to actual TP**: already matched objects
also need detections, and filtering changes output geometry. This is not an
achievable recall ceiling or simulated alternate tracker settings.

Indeed **12 matched GT object-frames have no raw geometric neighbour**, and
**13 have none in the retained eligible pool**. Conversely **1,610 misses** have
a scored output neighbour but are unmatched by the canonical scorer. These are
geometry/correspondence diagnostics, not evidence that an output was free to reuse.

## Correcting the earlier “54 changed misses” shorthand

The v2 event-difference receipt retains **54 added and 54 removed miss records**
when the key includes previous tracking history. At the actual missed-object
level `(source frame, GT id)`, the change is **29 added, 29 removed, 21,796
unchanged**. Another **25 unchanged object/frame pairs** have changed
`previous_hyp_id` context. They are not 25 additional different missed objects.
The earlier checklist wording overstated the object/frame replacement count;
the original receipts are unchanged and this distinction is now explicit.

## The same first event under corrected correspondence

The first switch remains **reference 85, track 19 → 31, source frame 54**.
Its preceding scoring history changes:

| Item | Historical v1 | Corrected v2 |
| --- | --- | --- |
| Last prior scored match for reference 85 | Frame 46 | **Frame 37** |
| Missed reference-85 frames immediately before switch | 47–53 | **38–53** |
| Same fixed rule: one frame before last match through switch +3 | 45–57 | **36–57** |

This changes **scoring correspondence**, not what the tracker did. V2 assigns
the shared geometry at frames 42–46 differently between references 85 and 89.
The original 45–57 trace therefore covered only part of the corrected history.
We retained it and performed **one new full-sequence unchanged replay**, observing
the same event's newly derived **36–57** window. No new attractive event, tuned
candidate, held-out input or retry was selected.

All **1,050 raw/scored output frames** and all **v2 failure records** reproduce
exactly. The bounded observer records **738 events / 66 association stages**
across **22 frames**. Track **19 is actually updated once, confirmed and public
on every observed frame**, with time-since-update zero. Track 31 is still created
at 52, confirmed at 54. Increasing lifetime or storing persistent identity is
therefore not justified by this episode. The earlier gate/overlap findings in
the unchanged 51–54 tail remain applicable.

The trace captures actual Python calls, cost masks and assignments; it is **not
an independent implementation of the tracker math**. Neither the scorer nor
the trace identifies physical people. References 85/89 need lawful, independent
pixel/label review before attributing a physical identity error or changing labels.

## Reproduction and receipts

```bash
PYTHONPATH=src:. python -m experiments.mot17_coverage_v2 \
  --baseline ../visiontrack-walkthrough/mot17-baseline-NvcCNo/bundle \
  --rescore ../visiontrack-walkthrough/mot17-metric-v2-IV6rTC/rescore \
  --preprocessing-check ../visiontrack-walkthrough/mot17-preprocessing-v2-0UcNhb/check \
  --preprocessing-manifest-sha256 7091e51a25dd059d3915e5ecdfb1cf69232d89bdfcb20518103247e43b179898 \
  --output /path/to/a/new/coverage-directory
```

The trace uses `python -m experiments.mot17_trace_v2` with the same baseline,
rescore and preprocessing arguments, plus the cache and label archive paths in
the [preprocessing command](MOT17_PREPROCESSING.md). Use a separate new output.
The method and no-retry attempt are written before tracker execution; failed
attempts retain their partial evidence rather than producing a success manifest.

Actual coverage: `../visiontrack-walkthrough/mot17-coverage-v2-QFcZa4/diagnosis`.
Actual trace: `../visiontrack-walkthrough/mot17-first-switch-v2-uIIDUY/replay`.
Both methods fingerprint source and input receipts before execution and verify
them afterwards. Every original baseline member remains unchanged. The old
frozen entry-point source guards are not weakened; versioned wrappers explicitly
admit current evaluators while checking all tracker/input code against its
original fingerprints.

Local verification: **960 tests pass, one slow test deselected**. That run
includes the isolated bootstrap executing all **1,099 historical tests** at
their original revision; it does not relax their production-tree guards.
All eight browser contract/workflow scripts, TypeScript checking, the app build,
Ruff and strict documentation also pass. These are local checks; remote CI and
deployment must be confirmed separately after pushing.

| Artifact | SHA-256 |
| --- | --- |
| Coverage method | `cbfcc9d36ad34bc26370f4696fbd70591ac97472c6dd9ed187cf5c08f9be3a2b` |
| Coverage summary | `5706c24b49c8cc5683da6c08574749fdb715756363e8bff0bbe17d06059485d9` |
| All v2 miss descriptions | `c240f304198ccebf1ab9b3bca7b531ad8cab8a0f9cd524a1b51d39984ecc7442` |
| Coverage manifest | `0d58512e43c1ea161132e316bb1a113f12bf4e243e7f32538666ec51071f29f8` |
| Trace method | `dacb7495f134a01369d7f493ea1e42f56413d00af9c81b14f5272ac3083a80ba` |
| Actual trace events | `1a1a5a2871d174eb07b9c02b1bdb7378392f73185c0ee337fcd7b6962a8bc568` |
| Trace summary | `b99ede13d1079f9ac48e76a13ea79aa629a8ff313317dc59642c367fff854c6d` |
| Trace manifest | `4fef0282c0c8ec68fb5339256846abc37439764e050303795fd6e0ebb283c471` |

## What remains before an intervention

Update **2026-10-26**: independent review below is deferred, not passed. The owner
delegated [AI-assisted technical review](MOT17_AI_REVIEW_DECISION.md), and the
[fixed detection/association inventory](MOT17_ASSOCIATION_INVENTORY.md) is complete.
Neither changes labels or justifies an intervention. The limited exploratory
case note no longer waits on a second person; stronger validation remains open.

- [x] Correct metrics and retain legacy reports/studies.
- [x] Independently verify preprocessing on this actual case.
- [x] Correct the general MOT17 policy with legacy reproduction and regressions.
- [x] Re-derive the full v2 coverage partition and history distinctions.
- [x] Extend the actual same-event trace using corrected prior-match history.
- [x] Obtain local source pixels for **36–57** with a bounded non-commercial
      admission, verified annotation correspondence and retained receipts; see
      [the preliminary visual review and handoff](MOT17_VISUAL_REVIEW.md).
- [ ] Independently review that window, especially 36–38, 42–46, 51–52 and 54;
      start with unlabeled scene context, then references 85/89 and outputs.
      AI-assisted triage is not a completed human review. Record ambiguity.
- [ ] Justify and prospectively freeze one useful comparison plus fresh validation,
      or record a reasoned stop if the evidence supports no change.
- [ ] Produce the reproducible visual case study and review its usefulness with
      an interested practitioner. No assumed partnership or market validation.

Volunteer recording is not needed for the completed annotation/metric work.
C++ remains in maintenance until an accepted useful **tracking** change earns a
parity handoff. No release, outreach or public accuracy claim occurs in this step.
