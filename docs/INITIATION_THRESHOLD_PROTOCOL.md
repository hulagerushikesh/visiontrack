# Initiation threshold — bounded synthetic feasibility protocol

Fixed on 2026-10-30, before this study's tracker grid. The previous rain replay
suggested that earlier births might restore a crossing. Its 0.55 choice was
post-hoc. These new scripted streams test that mechanism and its costs; they are
not an independent traffic benchmark, a held-out test or a novelty claim.

Question: does changing only `new_track_thresh` from 0.60 to 0.55 recover public
crossings, and what false-output/confirmation/continuity costs accompany it?
The package must be byte-identical to `6ca1d9f`. All other settings, including
`high_score_thresh=0.5`, `n_init=3`, `max_age=30`, class and Mahalanobis gates,
remain unchanged. No threshold sweep, default change, new API or C++ port.

The method, generator, tests and this protocol must be committed before the
actual grid. Method checks are workflow/provenance guards, not tamper-proof
authentication. Pre-grid checks use generated inputs, hand-fed output fixtures
and tracker doubles; actual study tracking starts only after the method commit.

## Fixed inputs: 54 pairs

Nine cases × three proposal scores (0.54, 0.57, 0.61) × two horizontal speeds
(2, 6 pixels/frame). Scores exercise below-both, candidate-only and above-both
birth ranges. Every row is retained. There are no randomized trials, statistical
power claim or representative prevalence assumptions.

Each box is 40×40, class 2. Its center is `x=500+speed*(local_frame-crossing)`
and y=300, except clutter at y=370. A normal passage has 12 frames and crosses
at local frame 4.5. Ground truth and detections are separate records; only
copied detection payloads enter either tracker.

| Case | Fixed perturbation / purpose |
| --- | --- |
| steady_true | One true object, proposals throughout |
| late_strong | True object; proposal score becomes 0.9 at frame 4, testing delayed births |
| short_true | True object exists only at frames 0–3; crossing at 2.5 |
| confirmation_gap | True object throughout; missing proposal at frame 1 before confirmation |
| confirmed_gap | True object throughout; missing proposals at frames 5–6 straddling the crossing |
| brief_false | No true object; proposals at frames 0–1 crossing at 0.5 |
| persistent_false | No true object; proposals **identical to steady_true** |
| true_and_clutter | True passage has score 0.9 at y=300; persistent false proposals have the selected score at y=370 |
| long_absence | Same scripted reference visible 0–7 and 40–47, a fresh passage at each appearance; 32 absent frames exceed max_age |

The identical-observations/different-truth pair deliberately exposes an
information limit. It does not estimate how frequent realistic false proposals
are. Long-absence truth stipulates a known synthetic identity and hidden route;
it does not imply real-world identity recognition.

## Measures and decision

Use the existing evaluator v2 at IoU≥0.5 for TP/FN/FP, IDSW and fragmentation.
Also report tentative births, births never reaching public output, public boxes,
public IDs, IDs with any FP box, extra matched IDs per reference, and first
matched-public delay for each contiguous visible truth segment (`null` if never
matched). Extra matched IDs are not the same measure as standard fragmentation.
Fragmentation is reported exactly with v2's documented empty-frame semantics.

Crossings use the existing rain rule: adjacent frames, same public ID,
left-to-right box-center crossing x=500, y within [205,432]. No coasting fill,
backfill or retrospective tentative output. Truth uses the same extraction on
scripted reference boxes. One-to-one maximum-cardinality matching allows ≤1
frame time error and ≤10px y error; minimum total time error then index order
break ties. Report crossing TP/FP/FN separately; aggregate counts cannot cancel
misses against false events. At most two truth events and four predictions are
allowed by this bounded scorer.

Success for a **global threshold recommendation** would require a recovered
true crossing without any increase in FP boxes, crossing FP, IDSW or extra
matched IDs in any cell. Any such harm blocks that recommendation. No effect is
not a success. A synthetic pass would still require representative permitted
real-traffic evidence before adoption; no automatic acceptance follows.
Inspect controls and the lower-score noise/confirmation limitations even if a
true passage improves. Do not average arbitrary case proportions into an
accuracy claim or tune a replacement threshold on these results.

## Execution and retention

Each cell starts both variants cold, then compares fresh/reset/fresh output
bytes: 54 pairs × two variants × three passes = 324 tracker passes. Preserve
inputs, outputs, scores, source/config/environment hashes and any failed attempt
outside both repos. Retain all cells, check exact input immutability, and verify
the package/method before and after execution. Stop on an error rather than
silently skipping or selectively rerunning cells.

```bash
python -m experiments.initiation_threshold \
  --output ../visiontrack-walkthrough/initiation-threshold-v1
```

The next deliverable is the complete per-cell summary plus a short findings
note, including regressions and a proceed/stop decision. Further work should
follow that result, rather than reopen source screening or grow this toy grid.
