# Continuity warning on MOT17 — exploratory triage result

Checkpoint: **2026-10-26**. The [fixed decision and method](CONTINUITY_WARNING_MOT17_PLAN.md)
were committed at `b2027eec8a5a786d01ddfa3768239e4607a3ed3b` before this
replay. This checks transfer from synthetic development to **one already opened,
previously investigated** MOT17-04-FRCNN sequence. It is not untouched
validation, independent physical-person truth or a calibrated deployment rate.

## Bottom line

**Keep v1 offline; do not add a user-facing continuity alert or a C++ port.**
It queued only five short review intervals, so its workload in this sequence was
small. But of **44** corrected scored ID switches, **43** were outside its fixed
three-frame review windows. The one switch *inside* a review window is only a
frame-level coincidence: at source frame **52** the warning concerns recent
tracks **14 and 20**, while the frame-54 scored switch is reference **85**
changing from track **19 to 31**. The earlier frame-49 warning includes 19, but
its fixed review window ends at 51. Do not describe either warning as having
identified the frame-54 identity change. No threshold or window was retuned
after seeing this result.

## Complete workload and event check

The unchanged default tracker replayed source frames **1–1,050**, with the v1
observer inspecting current detections *before* each update. All cached
detection rows/scores and every public output ID/box matched the sealed baseline
exactly. Events come from the separately corrected v2 scoring packet, whose 45
reported reference-metric checks passed. A warning at source frame `w` queues
`[w,w+2]`; overlapping/adjacent windows are merged only to count review tasks.

| Measure | Observed |
| --- | ---: |
| Warning frames / component warnings | 6 / 6 |
| Source warning frames | 49, 52, 126, 239, 312, 575 |
| Merged review tasks | 5 |
| Queued review windows | 49–54; 126–128; 239–241; 312–314; 575–577 |
| Distinct frames queued | 18 / 1,050 (1.71%) |
| Frames with at least one previous public track | 1,047 / 1,050 |
| Frames with two supported previous public tracks | 1,047 / 1,050 |
| Corrected scored ID switches in queued frames | **1 / 44** (43 missed) |
| Review tasks with / without a scored ID switch | 1 / 4 |
| Corrected fragmentations in queued frames | **3 / 108** (105 missed) |
| Review tasks with / without a scored fragmentation | 3 / 2 |

The warning is an observation-support diagnostic, not an ID-switch detector, so
these event counts are a **descriptive task-fit check**, not sensitivity or
false-alarm estimates. A no-event review task might still expose a legitimate
box shortage. Conversely a temporal event match is not proof the warning was
useful. The frame-240 fragmentation for reference 123 does involve a warned
recent track (44); that post-hoc correspondence does not rescue the overall
coverage or establish a physical cause. The frame-54 and 576 fragmentations do
not have that same recent warned-track linkage in their nearby windows. No
camera-level count, flow assignment or human review time was scored.

## Integrity and scope

- The run used the previously source-verified FRCNN cache and official
  annotation archive, the historical manifest
  `4ff57df09d5b4cf06491e984cf7b61f37b79ee22c0a087677f6587d5081984a8`
  and corrected v2 metric manifest
  `87403372f0a9158da83b4b8dddacb2c6b244db0a08ea7cc92bfb9ac5084a8e4a`.
  No pixels, embeddings, new detector or changed tracker settings entered the
  replay.
- The complete private warning packet is outside Git at
  `../visiontrack-walkthrough/continuity-warning-mot17-kTAuTd/study`.
  Its success manifest SHA-256 is
  `b73f9229a2539a079135bcb9ac41a6704fd611a0e25659669946a9597383a6c8`.
  It contains **all 1,050 positive and negative observer records** and no image
  bytes. There was one complete run, no skipped frame or selective retry.
- A separate saved-record pass rechecked source/observer fingerprints, scalar
  IoU, edges, maximum matching capacity, warnings and public-output parity for
  all **1,050 frames / 27,659 support components**. It also recomputed the
  temporal triage arithmetic from the saved records and corrected events. Its
  private `audit.json` SHA-256 is
  `1ba1e3e1e898ca67733da16cb19d055d53faf97186d59a524513b224722af534`.
  This arithmetic audit is not independent scene or reference-label review.

## Next decision, not a speculative fix

The specific three-frame queue is not a useful broad ID-switch-catching
feature on this known case. Do **not** enlarge the warning window after seeing
the switch, adjust IoU, add sticky identity memory, claim low false alarms or
ship the warning. The earlier synthetic study already showed that duplicate
detections of one object can imitate two-object shortage; this real sequence
does not resolve that ambiguity.

If this direction continues, first obtain permitted observations from a
representative fixed-camera setting, independently review the relevant
scene/reference labels, and ask an actual tracking engineer what action they
would take when shown each queued interval. Record count/flow or trajectory
consequences where those are the target task, plus warnings that consume time
without changing a decision and important problems not queued. Freeze any v2
rule and evaluation *before* running on that future material. The owner has not
yet supplied a consented pilot or practitioner decision; neither can be inferred
from these outputs. Meanwhile the Reliability Lab and C++ accepted contract
remain unchanged.
