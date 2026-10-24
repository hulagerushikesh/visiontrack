# Why the first scored ID switch became visible

**Historical evaluator-v1 selection and receipt.** The actual tracker evidence
below remains valid for its 45–57 window. Corrected v2 correspondence puts the
last prior match at **37**, not 46. The subsequent
[36–57 actual-call trace](MOT17_COVERAGE_V2.md) now covers the complete corrected
window, with exact full-sequence parity. Track 19 stays updated/public throughout.
Use **36–57** for the current independent-review brief; do not silently relabel
this original receipt as having observed those earlier frames.

Checkpoint: **2026-10-24**. This completes the next bounded diagnostic after the
[baseline](REAL_DATA_BASELINE.md) and [miss coverage analysis](REAL_DATA_COVERAGE.md).
It observes the **unchanged** tracker on the same MOT17-04-FRCNN input, not a new
candidate, parameter search, appearance experiment or visual accuracy claim.

## The finding in plain language

**The old ID was not forgotten or deleted.** Track 19 continued receiving a
high-confidence detection on every inspected frame. Its box stopped overlapping
reference 85 sufficiently for scoring. A separate detection created track 31 at
source frame 52; three hits made it confirmed and publicly visible at frame 54.
The scorer then registered reference 85 changing from its earlier match 19 to 31.

There is an important ambiguity: track 19's output also overlaps nearby reference
89 more strongly, **even before** its last scored match to 85. We have explained
software decisions, not established which physical pedestrian each detection
depicts. Calling this a proven tracker drift, incorrect annotation, occlusion,
re-entry or recoverable identity-memory error would go beyond the evidence.

All numbers below refer to source frames, **one-based**. Detection rows are also
one-based and frame-local; they are not stable object/person identities.

## What actually ran and passed

- One fresh, default `ByteTracker` pass over **all 1,050 frames**, from cold start.
- Inputs checked against every saved baseline frame before use; source/cache,
  annotation admission, all baseline production fingerprints and baseline members
  checked before and after the replay.
- Every raw and scored output byte matches the baseline; all canonical failure
  records and CLEAR metrics match. **27,842 raw public boxes**, FN 21,825, FP 49,
  IDSW 43, TP 25,732. Identity/HOTA were not recomputed: their input scored pairs
  are exactly unchanged; no new independent evaluator is claimed.
- **441 observed events, 39 association stages, 13 selected frames**. Actual
  call locals supply masks, distances, costs, solver proposals, accepted matches,
  updates, births and misses. No tracker method is patched; no gate is recomputed
  to stand in for the actual decision. Main-thread profiler state is protected.
- No pixels, embeddings, new detections, tuning, C++ changes or network upload.

The first event was already selected by the sealed baseline: reference **85**,
**19 → 31**, source frame **54**. Before this replay, the method fixed the window
to **one frame before the last scored match through switch +3**: **45–57**,
because the last scored match is at 46. This explicitly extends the earlier
51–57 output context to cover its immediately preceding match/loss history;
it is not a new failure selected for a more attractive outcome.

## The actual sequence of decisions

"Best raw" below means maximum IoU to reference 85, not a verified physical
identity. The raw detection and track-to-detection IoUs answer different questions.

| Source frame(s) | Observed evidence | Actual consequence |
| --- | --- | --- |
| 45–46 | Track 19 accepts high-score row 16; output IoU to reference 85 is 0.5825 then 0.5215 | Still the scorer's previous correspondence to 85 |
| 47–50 | Track 19 keeps accepting high-score rows 18, 18, 17, 17. Even the best raw IoU to 85 declines from 0.3842 to 0.1912 | Reference 85 is missed; track 19 remains updated, confirmed and public |
| 51 | Row 26 overlaps 85 at **0.7604**, but scores **0.2960**. Track 19 already accepted high-score row 18 | Track 19 is not in low recovery; the weak box is not accepted and cannot spawn a new track |
| 52 | Row 25 scores **0.8170**, overlaps 85 at **0.8459**, remains unused by high/tentative association | Creates **31**, hit 1, tentative, not public; 19 continues taking row 18 |
| 53 | Track 31 accepts row 25 in the tentative stage; its predicted-box/detection IoU is **0.8554**, d² **0.4556** | Hit 2; still tentative, not public |
| 54 | Track 31 accepts row 23 in the tentative stage; IoU **0.9046**, d² **0.2841** | Hit 3; confirmed and public. The scored switch 19 → 31 occurs here |
| 55–57 | Both tracks receive high-stage matches, now as confirmed tracks | Both remain public; keeping 19 alive did not preserve its scored correspondence to 85 |

At frame 51 the actual low-stage tracks are **9, 21, 25**, versus detection row
26, with no accepted match. Track 19 is absent because it was already updated
in the high stage. There is **no observed low-stage 19/26 gate distance**; absence
must not be represented as a measured zero or a measured rejection. Low boxes
do not enter the high-only tentative/birth path under these defaults.

At 52 the actual high-stage pair **19 / row 25** has:

| Quantity | Actual value | Existing rule |
| --- | --- | --- |
| Predicted-track/detection IoU | **0.08493064255082543** | Requires ≥0.3 |
| Mahalanobis d² | **17.98189652351658** | Requires ≤9.4877 |
| Class mismatch | **false** | Not the blocker |
| Forbidden mask / cost | **true / 1.7** | Accepted cost must be ≤0.7 |

Both overlap and distance prohibit this pair in the recorded state. This is
**not a gate-only failure**. At 53 the analogous old-track pair has IoU 0.0693
and d² 21.6515; at 54, IoU 0.0469 and d² 24.5677. Meanwhile track 19 accepts
another high detection on all these frames. No lost-track timeout is involved.

## Why neighbouring references prevent a simple identity story

| Source frame | Track 19 output IoU to reference 85 | Same output IoU to reference 89 |
| --- | --- | --- |
| 45 | 0.5825 | **0.8972** |
| 46 | 0.5215 | **0.8271** |
| 47 | 0.4033 | **0.8905** |
| 51 | 0.1367 | **0.9705** |
| 54 | 0.0395 | **0.9121** |

The canonical scorer preserves previous correspondences while IoU remains ≥0.5;
it does not simply choose the nearest reference anew every frame. One output
can overlap two reference boxes, but it cannot count as two true positives.
Reference 89 is a saved canonical miss at 45–46. These geometric/history facts
explain why "the ID followed the wrong person" is not established by the switch
count or the strongest-overlap box alone. This is a limitation to investigate,
not a reason to rewrite reference labels or change scoring after seeing results.

## Research decision: which fixes are justified now?

| Proposed next change | Decision from this evidence |
| --- | --- |
| Keep IDs longer / increase `max_age` | Not the demonstrated issue: 19 never became unmatched in this inspected window |
| Add re-entry memory or a person database | Not justified: no expired-ID recovery or physical re-entry is established here |
| Turn off the gate | Not justified as a fix: low IoU also blocks the recorded 19/25 pair. A full gate-off run would have different earlier states; we did **not** run it or claim its result |
| Reduce three-hit confirmation | Would change when 31 may appear, not demonstrate restoration of 19. Earlier visibility and false starts require a separately fixed evaluation |
| Lower the low-score threshold | Does not address the frame-51 routing fact: row 26 already qualifies for the low pool |
| Replace/tune the detector | Important future detector–tracker question given the full miss partition, but not tested or justified as a specific intervention by this event alone |

**No candidate is accepted, registered for a trial or ported to C++ in this step.**
The narrower research question is now clearer: when overlapping detector support
changes, how do staged association, confirmation and scoring correspondence affect
anonymous trajectory continuity, and what trade-off would an intervention create?
This is an investigable question, **not a claim of novelty or superiority**.

### Next evidence gate: a small, independent visual review

The review packet is specified now, so the next action is not another framework:

1. Confirm lawful local access to the corresponding pixels and reviewer availability;
   do not assume annotation access grants every image use. Retain data outside Git
   and do not send it to OpenTrafficCam or publish it without the needed rights.
2. Review **45–57**, especially 45–47, 51–52 and 54. Initially inspect source
   imagery/reference boxes **85 and 89 without tracker IDs**, to reduce anchoring.
   Check their distinctness, box extent, visibility, overlap and label continuity.
3. Then inspect the already sealed detections and outputs: does the box used by
   19 correspond to 89, 85, mixed/partial support, or something unresolvable?
   Record **uncertain** if the available context cannot establish this. If more
   context is necessary, document why before inspecting a larger interval.
4. A second person checks the interpretation independently; retain disagreements.
   Do not silently repair labels, discard the event or select a different winner.
5. Only then justify **one** intervention and freeze its task, identical inputs,
   primary endpoint, false-assignment/localization safeguards and fresh validation
   split before testing. Otherwise record a reasoned stop. MOT17-04 is already
   development evidence, not untouched validation.

Private volunteer recording is a separate route, not required to understand
this existing case. The full visual case study, improvement comparison and
practitioner usefulness validation remain open. The annotation-only weekly
baseline/diagnosis goal is met; public accuracy readiness is not.

**Subsequent same-session check:** the [independent metric cross-check](REAL_DATA_METRIC_CHECK.md)
found non-equivalence: TrackEval gives IDSW 44 versus our historical 43 and
HOTA 0.52372649 versus 0.52554966 on the same saved scored pairs. Actual lifecycle
observations remain exact, but event selection and the FN partition are tied to
our historical scorer, not independently validated reference correspondences.
Evaluator alignment now precedes a new accuracy comparison; pixel review remains
a separate open gate. Green mechanism tests do not approve metric equivalence.

## Reproduction and retained evidence

```bash
PYTHONPATH=src:. python -m experiments.mot17_case_trace \
  --baseline ../visiontrack-walkthrough/mot17-baseline-NvcCNo/bundle \
  --cache data/cache/mot17/MOT17-04-FRCNN.npz \
  --labels ../visiontrack-walkthrough/mot17-label-audit-NQQO7d/MOT17Labels.zip \
  --output /path/to/a/new/replay-directory

PYTHONPATH=src:. python -m experiments.mot17_case_trace_notes \
  --trace ../visiontrack-walkthrough/mot17-first-switch-trace-ft0NqU/replay \
  --output /path/to/a/new/notes.json
```

The replay creates a method and attempt receipt **before** constructing its
tracker. It refuses existing output, stops at the first disagreement, retains
partial records and writes no success manifest on failure. The notes extractor
reads the specifically pinned successful trace and verifies all seven members;
it executes no tracker. No retries or rejected actual attempts occurred.

Actual replay: `../visiontrack-walkthrough/mot17-first-switch-trace-ft0NqU/replay`.
Enriched interpretation: its sibling `notes-with-neighbors.json` (13 frame rows).
An earlier `notes.json` without neighbouring-reference fields is retained, not
overwritten; the enriched file is the cited table source. Execution used new
untracked diagnostic files on revision **4ddb1cd**, with source hashes recorded
before the run. Original baseline manifest remains
`4ff57df09d5b4cf06491e984cf7b61f37b79ee22c0a087677f6587d5081984a8`.

| Artifact | SHA-256 |
| --- | --- |
| Replay implementation | `196d09c42ee7110463b6b4a5ad6967b24adc81aa322202cca4559984e0c05093` |
| Replay tests | `846e9715f2ca96122b0ce8563057240c591177f71045bbd94f842a65fd3d0593` |
| Method | `79d39bbeb6387adaf3066a23fc4de600108d6c179c9f6310d72c208a132ac89a` |
| Actual observed events | `5531e1bbdda5cdc0b402b5672e6f008e9e2ffdbf99993dcaff813f09acc30330` |
| Replay summary | `c770780c88b40650cddcd9f6c8416b64778666ca5503d050e3f532d74e4365e0` |
| Replay manifest | `d15c90d36cc851e4fa80b06438bcae3443b4343e70545878fef4c5630b12fdd9` |
| Notes extractor | `2b9d27ce9f3e02fe2c3dd0ad2db0432dac39087f1d22b0bf10c4e42d98eb964b` |
| Notes tests | `1985533904c67cba5612cfe8c265178f02882a033e4fe659c5adcf2187cdce2c` |
| Enriched frame notes | `55a637018a7a557a5e7d96711b9ded9ad400787919bae967657af85b9f121055` |

The 27 new authored tests cover actual stage captures/solver masks, three-hit
publication, low-score recovery versus birth, live-but-unpublished tracks,
profiler cleanup, full replay disagreement stops and shared reference geometry.
They are mechanism tests, not extra real-data trials or independent visual truth.
