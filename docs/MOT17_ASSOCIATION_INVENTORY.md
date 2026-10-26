# Where the ambiguity enters: detections before track IDs

Checkpoint: **2026-10-26**. Completed read-only diagnosis of every frame in the
existing **36–57** window. No tracker execution, new image acquisition, alternate
assignment, label change or intervention result. This extends the
[AI-assisted case note](MOT17_AI_REVIEW_DECISION.md), not independent visual validation.

## The useful distinction

Two reference trajectories do not necessarily have two usable supplied detection
boxes. In **all 15 frames from 36 through 50**, the raw detections with score
**>=0.1** cannot provide two distinct boxes overlapping references 85 and 89 at
**IoU >=0.5**. In seven of those frames, the **same single box** overlaps both;
in the other eight, reference 85 has no such eligible neighbour.

This is a geometric inventory, **not proof that the detector saw one physical
person, that a detection was merged, or that a different tracker could not help**.
The 0.5 diagnostic overlap rule differs from the tracker's 0.3 high-stage gate.
Do not substitute it for track feasibility or physical-person truth.

At frame **51**, two distinct eligible boxes finally appear in this window.
The reference-85 neighbour has score **0.296**: it belongs to low-score recovery,
not the high-score stage or new-track spawning. Track 19 has already accepted a
high-score detection, so **19 is not offered this low-score row** in recovery.
This is stage ordering, not a recorded rejection of that pair by the motion gate.

At **52**, the reference-85 neighbour scores **0.817** and enters the high stage.
Its pair with predicted 19 fails **both** minimum overlap and motion gating.
It instead starts track 31, which becomes public at 54 after three hits. A simple
“keep the old track alive longer” explanation misses this sequence: 19 never
stops receiving updates in the observed window.

## Full fixed-window inventory

“Capacity” counts distinct raw boxes for just these two references, not feasible
whole-scene matches. Every raw row is retained in the private numerical output;
there is no best-looking-frame selection or threshold search.

| Source frame(s) | Eligible reference-85 neighbour | Eligible reference-89 neighbour | Distinct-box capacity | Raw box selected by 19 overlaps |
| --- | --- | --- | --- | --- |
| 36 | Same row 22 | Same row 22 | 1 | Both 85 and 89 |
| 37–40 | None | One per frame | 1 | 89 only |
| 41–46 | Same row as 89 | Same row as 85 | 1 | Both 85 and 89 |
| 47–50 | None | One per frame | 1 | 89 only |
| 51 | Row 26, score 0.296 | Row 18 | 2 | 89 only |
| 52 | Row 25, score 0.817 | Row 18 | 2 | 89 only |
| 53 | Row 25, score 0.991 | Row 18 | 2 | 89 only |
| 54–55 | Row 23, score 0.999 | Row 18 | 2 | 89 only |
| 56 | Row 21, score 1.0 | Row 17 | 2 | 89 only |
| 57 | Row 20, score 1.0 | Row 13 | 2 | 89 only |

Detection row numbers are **frame-local**, not object identities. The selected
box supports both references in **7** frames and only 89 in **15**; this is not
seven correct matches and fifteen proven identity errors. A higher IoU does not
adjudicate physical identity or establish the scorer's history-aware assignment.

### Three different geometries must not be confused

1. **Raw detection vs reference:** used in the table above.
2. **Predicted track vs detection:** used by actual association gates/costs.
3. **Updated, filtered public box vs reference:** used by the evaluator.

For example, at **37** the selected raw box has IoU **0.476804** with reference
85, below the inventory threshold. The filtered public 19 still has IoU about
**0.503** with 85, and 37 remains its last prior scored match under v2. These
observations are compatible; a tracker output is not an unmodified detection.

## Actual stage evidence, not a counterfactual

| Frame | Separate reference-85 row | What happened |
| --- | --- | --- |
| 51 | 26 | Not offered to 19 after its high-stage match; no track update uses this row; score is below the 0.6 spawning boundary |
| 52 | 25 | Offered to 19 in high stage: predicted IoU **0.084931 <0.3**, motion distance squared **17.981897 >9.4877**, forbidden cost **1.7 >0.7**; row spawns 31 |
| 53 | 25 | Pair with 19 remains forbidden; row updates tentative 31 |
| 54 | 23 | Pair with 19 remains forbidden; row updates 31, which becomes public |
| 55–57 | 23 / 21 / 20 | Rows continue updating 31; pairs with 19 remain forbidden |

The JSON field `assigned_track_id` means an actual `_apply_match` update, **not
spawning**. Its null at 52 must not be read as “row unused”: the existing lifecycle
trace records the spawn separately. Missing `offered_to_19` entries mean a pair
was not evaluated in that stage, not zero distance, a gate pass or a gate failure.

No alternative global assignment, gate setting, detector or motion model was
executed. Two-reference capacity ignores other objects, scoring ignore removal,
class/motion constraints and future consequences. It is **not achievable recall,
a recoverable-error count, or proof that Hungarian competition caused the event**.

## Decision and next research question

Keep Python defaults and C++ behavior unchanged. This episode motivates asking
how much continuity a motion-only tracker can retain when observations cease to
separate nearby trajectories—not adding persistent person memory or claiming that
disabling a gate fixes it.

The next bounded research design is a **paired observation-availability study**:
hold synthetic trajectories/tracker settings fixed and vary whether the supplied
boxes remain separated during overlap or lose that separation. Before execution,
fix all conditions, ranges, metrics and failure reporting. Distinguish missing
observations from ambiguous shared support; keep startup/confirmation effects
visible; report ID changes, misses and recovery rather than optimizing one ID
number. Do not use reference labels as an input to the deployed tracker.

The subsequent [prospective study recipe](OBSERVATION_AVAILABILITY_PROTOCOL.md)
now fixes these conditions and an unchanged-input control before execution.
It cannot establish the cause of this real episode or validate a remedy.
Any later intervention needs fresh validation; independent physical/reference
adjudication remains deferred. Practitioner usefulness is still untested.

## Reproduction and verification

The focused reader is `experiments/mot17_association_inventory.py` in the repository.
Run without arguments to preview its fixed question/rules without reading data.

```bash
PYTHONPATH=src:. python -m experiments.mot17_association_inventory \
  --baseline ../visiontrack-walkthrough/mot17-baseline-NvcCNo/bundle \
  --trace ../visiontrack-walkthrough/mot17-first-switch-v2-uIIDUY/replay \
  --output /path/to/a/new/external-directory --write
```

It verifies every member of both pinned input packets, requires trace raw output
to equal the saved baseline, writes the method **before analysis**, and rechecks
inputs/source afterwards. It never invokes the tracker or assignment solver.
Errors retain a failure receipt without a success manifest; existing output paths
are refused. This is exploratory analysis of an already known event, not a
preregistered or untouched validation result.

Actual private output:
`../visiontrack-walkthrough/mot17-association-inventory-j8iIND/analysis`.
All **1,120** reference/detection IoUs also agree with a separately written scalar
intersection/union calculation to absolute tolerance **1e-14**; **66** capacities
agree with exhaustive two-reference choices including unmatched options. These
arithmetic checks do not independently validate images, annotations or Kalman math.

Local verification: **1,070 Python tests pass, one slow test deselected**, including
25 authored inventory/receipt tests. Repository-wide Ruff, the offline staged-review
control check, the strict documentation build and `git diff --check` pass. These
checks do not constitute a new browser production build, remote CI or deployment.

| Artifact | SHA-256 |
| --- | --- |
| Method | `fb88b717b3c4df493056838a887d2f5695d2a1057748469b2fe37ca77934846f` |
| All frame/row findings | `2b9cdbc90d6894eb6cb706f8356258eb93cb1715f1e68ebec4748236addaef3f` |
| Summary | `c91f15213983ab1a44a361c34f616c80e001877b90b63d7a6282469c32ec3fe9` |
| Manifest | `34f101a10ab512dd88e597421166c806cafad90c775492c18fa0cf3fa311f494` |

No source pixels or private review notes are included in Git. No release,
deployment, public accuracy claim, outreach or new C++ port occurs in this step.
