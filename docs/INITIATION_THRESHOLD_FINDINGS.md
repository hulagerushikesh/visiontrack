# Earlier track initiation: recovery and false-count costs

Completed 2026-10-30. **Keep the default birth threshold at 0.60.** The fixed
0.55 candidate recovers scripted true crossings but also confirms persistent
false proposals and emits false counts. It fails the registered no-harm gate.
This is a synthetic development finding, not traffic accuracy or a novel method.

## What we tested

The [protocol](INITIATION_THRESHOLD_PROTOCOL.md) and executable method were
committed as `7cf2be7dcbf0457df32417dd1dae764531c06522` before the actual grid.
All package bytes match `6ca1d9f`; only `new_track_thresh` differs. All **54
paired cells / 324 fresh-reset-fresh passes** completed without errors. There
was no threshold search, change of confirmation/gating, held-out test or replay
on a new traffic video. The previous rain clip motivated this candidate and
remains exploratory.

The [complete result](https://github.com/hulagerushikesh/visiontrack/blob/main/experiments/initiation_threshold_v1_results.json)
retains every cell, configurations, input/output digests, environment and source
hashes. Its file SHA-256 is
`fb947930ba3b1a2bf73596a5ffcdb5f76b1d56372edbb4ef47c93e7dbd20fc8d`.
Full inputs, public outputs and scored records are retained outside the repos
under `../visiontrack-walkthrough/initiation-threshold-v1/`. The summary contains
no footage, personal/contact records or absolute local paths.

## Result at proposal score 0.57

Each row below has the same outcome at **both** tested speeds, 2 and 6px/frame.
Arrows mean baseline 0.60 → candidate 0.55. These hand-selected case proportions
must not become a combined accuracy estimate.

| Scripted case | Correct crossings | False crossings | False public boxes | Other observation |
| --- | --- | --- | --- | --- |
| Steady true passage | 0 → 1 | 0 → 0 | 0 → 0 | Candidate first public match after 2 frame intervals |
| True passage, strong scores only from frame 4 | 0 → 1 | 0 → 0 | 0 → 0 | First match delay falls from 6 to 2 intervals |
| Short true passage, four visible frames | 0 → 1 | 0 → 0 | 0 → 0 | Candidate outputs only the final two frames |
| Missing proposal before confirmation | 0 → 1 | 0 → 0 | 0 → 0 | Two tentative births; one dies; first public match at frame 4 |
| Missing proposals across counting line | 0 → 0 | 0 → 0 | 0 → 0 | Candidate tracks before/after gap, but cannot emit an adjacent-frame crossing |
| Two-frame false proposal | 0 → 0 | 0 → 0 | 0 → 0 | Candidate creates one provisional track; it never confirms |
| Persistent false proposal | 0 → 0 | 0 → 1 | 0 → 10 | Three observations confirm a false track |
| Strong true passage plus persistent clutter | 1 → 1 | 0 → 1 | 0 → 10 | True count retained; clutter adds a second, false count |
| Same scripted reference after 32 absent frames | 0 → 2 | 0 → 0 | 0 → 0 | Candidate uses two public IDs, one scored switch and one extra matched ID |

The baseline emits nothing in several weak-score cases, so its zero ID switches
there is **not evidence of better identity continuity**. The long-absence
candidate produces observations the baseline lacks, but still cannot retain an
expired identity. The false-output violations alone are sufficient to reject
a general threshold recommendation. Six cells violate at least one registered
no-harm endpoint: four persistent-noise cells and two long-absence cells.

## Controls and interpretation

- All **36 controls** at scores 0.54 and 0.61 produce exactly identical output
  bytes and metrics under both configurations. At 0.54 neither threshold admits
  those births; at 0.61 both admit them. Both trackers can confirm persistent
  false proposals above their threshold; 0.60 does not solve false detection.
- `steady_true` and `persistent_false` have identical detector input digests
  and identical output digests for every score/speed. Only scripted truth
  differs. A lower score threshold supplies no new information to distinguish
  those worlds. This exposes a limitation, not its real-world prevalence.
- Three-match confirmation filters two-frame noise, but not persistent noise.
  Ordinary first confirmation at frame 2 still needs observations at 0, 1, 2.
  A missing tentative match restarts the process; there is no retrospective
  public output before confirmation.
- Expiry, detection absence and counting rules are separate limitations.
  Surviving internally through a gap does not supply public observations on
  the missing frames. This experiment does not test an alternative counter.
- Standard v2 fragmentation is zero across these cells, including empty-output
  gaps, under its documented history semantics. Explicit unmatched frames,
  IDSW and extra matched IDs prevent interpreting that zero as perfect continuity.

Saved-record verification checked all **218 manifest entries**, recomputed all
108 variant scores/output digests, and checked TP/FP/FN using separate scalar
box-overlap arithmetic on saved rows without rerunning the tracker or using
the canonical evaluator for that arithmetic. These are technical checks, not
independent human scene review. No real labels or detector model were evaluated.

## Product and next action

The [Lab crossing diagnosis](https://visiontrack.hulage.in/lab/crossings) now
includes a separate, labelled controlled-result section sourced from the full
committed summary. It explains true recovery, persistent false counts and the
remaining detection-gap failure. Publishing code does not itself verify the
hosted deployment; the linked route is available after its deployment succeeds.

- [x] Finish the bounded mechanism study and retain negative findings.
- [x] Make its benefit/cost explanation accessible from the existing Lab UI.
- [x] Make birth/confirmation diagnosis reusable for a local detection stream
  rather than limited to this curated rain example. The opt-in
  [offline initiation diagnostic](INITIATION_DIAGNOSTIC.md) now explains saved
  Lab runs with exact public-output parity and a separate bounded trace.
  It preserves old report compatibility and distinguishes observed lifecycle
  decisions from truth/accuracy claims. Optional Lab trace inspection is next.
- [ ] Research acceptance remains a separate gate: permitted representative
  traffic evidence with independently checked event/negative labels, frozen
  detector+tracker comparison and false-count/miss costs. Do not repeatedly
  tune this threshold or expand this toy grid to claim generalization.
- [ ] C++ receives only an explicitly accepted, frozen behavior change after
  that evidence gate. This rejected configuration needs no C++ port or release.

No owner recording, interview, new email or manual review task is required for
the next offline diagnostic implementation. No outreach is sent by this study.
