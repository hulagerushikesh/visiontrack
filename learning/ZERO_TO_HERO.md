# VisionTrack zero-to-hero curriculum

This curriculum is for four different starting points: a completely
non-technical reader, a student entering computer vision, a software or ML
developer, and a project/research lead. Everyone studies the same system, but
not everyone needs the same depth or destination.

The goal is not to memorize VisionTrack. The goal is to explain what a tracker
knows, prove why it made a decision, recognize when the evidence is weak, and
change the system without hiding new failure modes.

## Choose your route

| Route | Starting point | Suggested pace | Finish line |
|---|---|---:|---|
| Curious, non-technical reader | No coding or mathematics | 6–8 hours | Explain detection, tracking, identity failure, privacy, and the product decision in plain language |
| Computer-vision student | Basic Python; school algebra | 8–12 weeks | Implement and evaluate a small tracker, reproduce a result, and write an honest experiment note |
| Developer / ML engineer | Comfortable with Python and tests | 4–6 weeks | Trace and modify the real tracker, produce a Reliability Lab bundle, and preserve its contracts |
| Research/product lead | Comfortable reading technical summaries | 6 weeks, alongside the project | Define falsifiable questions, control scope, judge evidence, and decide what earns a C++ port |

You may change routes. A non-technical learner can complete Levels 0–2 first;
a student can continue through Level 6; a developer should complete Levels
1–7; the research lead uses the companion
[`RESEARCH_LEAD_PATH.md`](RESEARCH_LEAD_PATH.md) throughout.

## The shared mental model

VisionTrack follows this chain:

```text
camera or video
  -> detector proposes objects
  -> tracker predicts where existing objects should be
  -> association matches detections to tracks
  -> lifecycle creates, confirms, loses, and removes tracks
  -> evaluation measures both accuracy and failure type
  -> Reliability Lab preserves the evidence behind a human decision
  -> accepted behavior may cross the parity gate into VisionTrack C++
```

The detector answers **what is visible now**. The tracker answers **which
recent trajectory owns this detection**. Neither answer proves a person's
real-world identity.

## Level 0 — See the problem without code

**Question:** Why does a box receive an ID, and why can that ID change?

Learn:

- a video is a sequence of images, not continuous understanding;
- a detection is a box, class, and confidence for one frame;
- a track is a time-bounded hypothesis connecting detections;
- disappearance, occlusion, blur, crowding, and camera motion make association
  uncertain;
- `track_id` is not a person's name and should not be treated as one.

Use the public teaching page, the live tracker with webcam processing kept in
the browser, and Stages 0–1 of [`LEARNING_PATH.html`](LEARNING_PATH.html).

**Completion proof:** explain to another person why returning to a webcam can
correctly produce a new track ID even when the human is the same.

## Level 1 — Learn the minimum computer-vision vocabulary

**Question:** What information reaches the tracker?

Learn pixels, frames, coordinates, bounding boxes, confidence, classes, frame
rate, resolution, false positives, false negatives, and intersection over union
(IoU). Then distinguish four scopes:

1. detection inside one frame;
2. tracking across nearby frames;
3. anonymous re-entry inside a bounded session;
4. named or global recognition, which is outside VisionTrack's scope.

**Student/developer practice:** complete the geometry exercise in
[`EXERCISES.md`](EXERCISES.md) and inspect `visiontrack/core/geometry.py`.

**Completion proof:** calculate IoU for two simple boxes and describe a case
where high IoU still gives the wrong identity.

## Level 2 — Understand motion and uncertainty

**Question:** Where should a temporarily missing object appear next?

Learn vectors, matrices, position, velocity, covariance, prediction, update,
measurement noise, process noise, and Mahalanobis gating. A Kalman filter does
not recognize an object; it maintains a motion estimate with uncertainty.

**Student/developer practice:** complete the Kalman exercise and trace
`visiontrack/core/kalman.py` for one predict/update cycle.

**Completion proof:** draw how uncertainty grows during missed detections and
explain why a gate should widen or reject a match.

## Level 3 — Understand association and lifecycle

**Question:** When several matches look plausible, how is one global decision
made?

Learn cost matrices, hard gates, Hungarian assignment, ByteTrack's two-stage
matching, track states, confirmation, retirement, fragmentation, and ID
switches.

**Student/developer practice:** complete the assignment and lifecycle exercises,
then inspect `visiontrack/core/assignment.py`, `visiontrack/tracking/track.py`,
and `visiontrack/tracking/tracker.py`.

**Completion proof:** solve a small 3x3 cost matrix by hand, then explain why a
greedy match can hurt a later track.

## Level 4 — Measure the right failure

**Question:** What does “more accurate” mean for the real decision?

Learn precision/recall, MOTA, IDF1, HOTA, fragmentation, ID switches, paired
comparison, failure regimes, and operational measures such as count or dwell
error. One aggregate score cannot explain every product cost.

Read [`../docs/ERROR_TAXONOMY.md`](../docs/ERROR_TAXONOMY.md),
[`../docs/BENCHMARKS.md`](../docs/BENCHMARKS.md), and the generated benchmark
reports.

**Completion proof:** take one hypothetical failure and state which metric
would reveal it, which might hide it, and what a human must inspect.

## Level 5 — Reproduce instead of trusting a screenshot

**Question:** Can another person reconstruct the decision later?

Learn immutable inputs, hashes, configuration lineage, fixed detection streams,
controlled variants, ground truth, failure events, reports, and explicit human
acceptance decisions.

Run the dataset-free synthetic workflow described in
[`../docs/RELIABILITY_LAB.md`](../docs/RELIABILITY_LAB.md). Explore its report
without changing the sealed evidence.

**Completion proof:** produce one complete local Lab bundle and explain which
files establish input, configuration, result, failure evidence, and decision.

## Level 6 — Think like a researcher

**Question:** What observation would prove our preferred idea wrong?

Learn hypotheses, independent variables, controls, pre-registered thresholds,
ablation, paired evidence, uncertainty, negative results, and limits on
generalization.

Use the project's existing research questions and results as worked examples.
Do not start by adding a fashionable model. Start with a failure, competing
explanations, and a measurement that separates them.

**Completion proof:** write a one-page experiment proposal containing a
falsifiable hypothesis, baseline, controlled change, metrics, failure budget,
stopping rule, and expected negative result.

## Level 7 — Cross the runtime boundary

**Question:** How can a faster implementation be trusted?

Study the companion
[`VisionTrack C++ mastery path`](https://github.com/hulagerushikesh/visiontrack-cpp/blob/main/learning/MASTERY_PATH.md)
and complete [`PARITY_CAPSTONE.md`](PARITY_CAPSTONE.md). The NumPy repository is
the readable behavioral oracle; the C++ repository is allowed to optimize only
behavior that has a frozen contract and parity evidence.

**Completion proof:** run the canonical fixture through both runtimes, explain
the digest and trajectory evidence, and introduce one controlled mismatch that
the gate catches.

## Level 8 — Contribute responsibly

Before proposing a feature, answer:

1. Which observed user or research problem does it address?
2. What behavior is inside and outside its scope?
3. What evidence could falsify its benefit?
4. What privacy, retention, licensing, or deployment boundary applies?
5. Does it belong in the NumPy reference, the C++ runtime, the web product, or
   nowhere yet?
6. What test or artifact prevents the claim from silently drifting?

**Hero outcome:** you can move from a visible tracking failure to an honest,
reproducible explanation; design a bounded experiment; and accelerate only the
behavior that survives.

## Suggested weekly plans

### Non-technical — four sessions

1. Level 0 and the live demo.
2. Level 1 with hand-drawn boxes and IoU.
3. Levels 2–3 conceptually, using diagrams rather than equations.
4. Levels 4–5: compare two results and decide what evidence you trust.

### Student — twelve weeks

1. Python, arrays, images, and coordinates.
2. Detection and box geometry.
3. Linear algebra and probability essentials.
4. Kalman prediction/update.
5. Assignment and Hungarian reasoning.
6. Track lifecycle and ByteTrack.
7. Metrics and failure taxonomy.
8. Reproduction and testing.
9. Reliability Lab artifacts.
10. Read and summarize one tracking paper.
11. Run one controlled ablation.
12. Complete the parity capstone and present limitations.

### Developer — six weeks

1. Run tests, synthetic CLI, live UI, and source trace.
2. Complete the four dataset-free exercises.
3. Read schemas and produce a Lab bundle.
4. Trace one failure from report to frame evidence and decision.
5. Complete the cross-runtime capstone.
6. Propose one contract-preserving improvement with tests and measurements.

## Mastery rule

Do not mark a level complete because you read it. Mark it complete when you can
produce its completion proof without copying the lesson.
