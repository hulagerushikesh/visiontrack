# Localization quality: research decision

Decision date: **2026-11-04**. The independent research checkpoint is complete:
**do not build an unconditional jitter-versus-motion classifier from the current
box stream. Proceed with a bounded detector-information feasibility step.**
No better-tracker or novelty result has been established.

## What this means

A rectangle moving on screen can mean that the object moved, the detector's
rectangle shifted, or both. A confident class prediction is not automatically
a precise location. The current tracker receives a rectangle, score, class and
optional appearance vector. It receives no per-box localization distribution.
Its own Kalman covariance describes its assumed state uncertainty; it is not a
second independent observation of why a rectangle changed.

Our useful next question is narrower:

**Does information preserved from detector proposals before suppression predict
localization error beyond box size, class and score, on the intended domain?**

This starts as a replication and feasibility question. Only if that signal is
useful should we ask whether using it in association improves counts without
the false-output and timing costs in our earlier studies. Building an existing
uncertainty-aware tracker would not, by itself, establish an original contribution.

## What we already know from VisionTrack

| Completed work | Binding lesson for this question |
| --- | --- |
| [RQ3](PHASE5.md) | Tightening noise from clean reference trajectories harmed tracking under injected detector noise. This rejects that tested calibration procedure, not uncertainty modeling in general. Historical metrics keep their original evaluator/protocol scope. |
| [Box-gate study](BOX_GATE_FINDINGS.md) | Removing a rejection gate reduced ID switches but failed the registered safety requirements; held-out results included 206 endpoint violations. A stable ID alone is insufficient. |
| [Observation availability](OBSERVATION_AVAILABILITY_FINDINGS.md) | Missing and shared boxes can give different identity outcomes even with similar miss totals. Uncertainty cannot create an absent observation. |
| [Initiation threshold](INITIATION_THRESHOLD_FINDINGS.md) | Earlier true recovery also confirmed persistent false proposals. Identical detector inputs with different scripted truth already defeated a universal score-only solution. |

The new construction below concerns *localization/motion ambiguity*, rather
than rerunning these grids or changing their verdicts. Previously inspected
MOT17/rain cases remain development material.

## Primary literature reviewed

Targeted review, accessed **2026-11-04**; not an exhaustive novelty search or a
reproduction of the authors' results. Version and inspected scope are explicit.
Performance claims in the papers have not been independently verified here.

| Source and inspected scope | Relevant existing approach | Consequence for our decision |
| --- | --- | --- |
| [ByteTrack, v3, method §3](https://arxiv.org/html/2110.06864v3) | Associates high-score detections first and then uses low-score detections to recover unmatched tracks. | Score-based recovery is established prior art; it does not supply a localization distribution. |
| [OC-SORT, v3, §§3–4](https://arxiv.org/html/2203.14360v3) | Addresses accumulated motion-estimation error through observation-based re-update and direction consistency. | Re-update and observation-direction ideas are not new; neither promises per-event causal identification. |
| [UCMCTrack, v2, Method](https://arxiv.org/html/2312.08952v2) | Projects bottom-centre observations and measurement covariance to a ground plane, then uses mapped Mahalanobis distance. Camera parameters are required or estimated. | Perspective-aware motion and projected uncertainty already exist; unknown geometry and contact-point error remain separate assumptions. |
| [UncertaintyTrack, v2, §§III–IV](https://arxiv.org/html/2402.12303v2) | Learns box covariance with a probabilistic detector; uses it in filtering, matching and box relaxation. Assesses uncertainty as well as tracking. | Adding detector covariance to a Kalman tracker is established. We must check information quality before trusting it. |
| [UTrack, v1, §3](https://arxiv.org/html/2408.17098v1) | Uses dispersion of proposals around suppression to estimate localization uncertainty and propagate it into tracking. | Preserving pre-suppression proposals is a plausible low-training-cost feasibility route, not our invention. Correlated proposals are not independent repeated measurements. |
| [Deep LG-Track, v1, abstract only](https://arxiv.org/abs/2504.01457v1) | Reports confidence/disappearance-adaptive measurement noise and localization/confidence-weighted association. | Confidence-adaptive filtering/fusion is occupied prior art. Implementation and performance details were not reviewed. |
| [CANMOT, v2, abstract only, October 2026](https://arxiv.org/abs/2606.03590v2) | Studies class-specific, object-aligned noise and uncertainty consistency in **3D** nuScenes tracking. | Class-aware noise is not an unclaimed idea; its 3D findings cannot be transferred directly to our 2D fixed-camera setting. |
| [Schröder et al., VEHITS 2026, authors' university abstract only](https://portal.fis.tum.de/de/publications/improving-ekf-consistency-in-3d-multi-object-tracking-via-heteros/) | Integrates heteroscedastic detector variances into 3D EKF tracking and distinguishes consistency from accuracy. | Better-calibrated covariance and better task outcomes require separate evaluation. No full-paper assessment was made. |

A potential contribution would need evidence about detector/tracker behavior
and downstream counting costs under a precisely defined domain shift. This
review has **not** established that this gap is novel or that we can improve it.
The cited 2026 abstracts broaden the screen; they are not complete method audits.

## An executable limit, not another benchmark

[`experiments/localization_observability.py`](https://github.com/hulagerushikesh/visiontrack/blob/main/experiments/localization_observability.py)
constructs two fixed pairs of hidden worlds, with 12 frames in each world:

| Pair | World A | World B | What reaches the tracker |
| --- | --- | --- | --- |
| Horizontal translation | The reference box moves across a line; observation error is zero. | The reference stays still; a correlated localization bias produces that same moving box. | Exactly identical boxes, scores, classes, absent appearance and frame order. |
| Lower-edge change | The reference extent/bottom anchor changes across a line. | The reference extent stays fixed; lower-edge measurement bias produces that same extent change. | Exactly identical inference rows again. This is box geometry, not a physical 3D motion model. |

Each world is reconstructed as `observation = reference + scripted error`.
Only reconstructed observations enter the unchanged default tracker. Reference
boxes and errors remain outside that boundary. Each pair gives exactly identical
tracker output, including a reset replay, although its two reference anchor
crossing totals are **1 and 0**. The small crossing calculation is explicitly
defined on reference bottom-centre points; it is **not** our production traffic
evaluator or a claim about the tracker's predicted count.

The result follows from identical inputs, not the choice of tracking algorithm.
Any deterministic function of these same inputs and fixed priors gives the same
answer in both worlds; a randomized method has the same output distribution.
Temporal history does not break these deliberately identical finite histories.
The scripted correlated bias is allowed by this construction; excluding it is
an additional modeling assumption.

This establishes a counterexample to a **universal per-event guarantee**. It
does not estimate how often this happens, show that statistical noise estimation
is useless, or prove a detector's real errors follow this toy. Longer sequences,
known stochastic models, pixels, geometry or added measurements can provide
useful evidence. Calibration labels help evaluate a signal; labels must not
enter the inference path.

For a Kalman model with the usual independent-noise assumptions, innovation
covariance combines predicted state covariance and measurement noise:
`S = H P_pred Hᵀ + R`. A large innovation alone does not identify which component
or model assumption failed. Estimating process/measurement noise statistically
requires additional assumptions and checks; the witness is not a general
impossibility theorem about identifying those parameters.

Run from this checkout with NumPy installed, without footage, models or network
access. Explicitly select its sources (or use an editable installation). The
probe refuses a different installed package rather than attach checkout source
hashes to its output:

```bash
PYTHONPATH=src python -m experiments.localization_observability > /new/path/observability.json
pytest -q tests/test_localization_observability.py
```

The [compact result](https://github.com/hulagerushikesh/visiontrack/blob/main/experiments/localization_observability_v1_result.json)
retains input/output hashes, reference crossing totals, runtime and executable/
package source hashes. The full output includes every generated observation,
reference/error row and tracker output. This is an authored construction with
verification, not a preregistered outcome study or independent ground truth.

## Go/no-go and the next implementation

**No-go now:** infer a guaranteed jitter/motion cause from current box jumps;
add a new confidence-to-noise heuristic as a claimed contribution; loosen gates
or lower birth thresholds on the basis of one recovered ID.

**Go now: a capture-only research seam in the existing YOLOX decoder.** It
already computes decoded proposals before greedy suppression but returns only
kept `Detection` objects. Preserve the associated proposal groups in an opt-in,
bounded per-frame diagnostic result. This is preparation to test the UTrack-style
information source, not an implementation or reproduction of UTrack.

Completion checks for that next engineering step:

1. Identical default detections and downstream tracker output with capture off
   versus on, including threshold ties, overlapping objects, class policy and
   both supported output layouts. Preserve the actual existing suppression
   semantics, including any class interactions; do not silently fix them.
2. Explicit original proposal indices, coordinate/scale convention, scores,
   thresholds and suppression relationships. Distinguish proposals dropped before
   suppression from proposals suppressed by a kept box. No reference labels,
   images or appearance data in the capture record.
3. Bound the optional retained record; declare truncation and incomplete groups.
   Avoid retaining raw outputs across frames. Default execution incurs no new
   proposal-history storage. Missing/one-member groups do not become zero-variance
   certainty or an automatic covariance estimate.
4. Tests with authored model-output tensors and a fake session, requiring no
   download, recording or Bath response. Measure additional storage and compute
   later on fixed permitted inputs before any real-time claim.

The capture-only step is now [implemented and documented](YOLOX_PROPOSAL_CAPTURE.md)
in the checkout (2026-11-04), with opt-in bounded records, explicit incomplete
groups and exact on/off detection/tracker checks. This closes the engineering
seam above; the localization-signal gate below remains open.

## Research gate after capture

First audit the signal offline, outside association; do not change production
`Detection`, the Kalman filter or C++ merely because capture works.

- **Baselines:** constant/size-conditioned quality and score/class/size quality;
  then a fixed proposal-dispersion candidate. Compare on the same kept detections
  from the same detector bytes. Training a probabilistic head is a separate,
  more expensive alternative requiring a new design decision.
- **Target:** independently checked box/bottom-anchor localization errors,
  conditional on a disclosed fixed detection/reference matching policy. Retain
  unmatched proposals, reference misses, visibility and group-size coverage;
  accepted tracker matches alone would censor difficult examples. Matched-box
  localization does not measure missing-object recovery.
- **Disconfirming cases:** tightly clustered but coherently biased proposals;
  one proposal or none; nearby objects merged by suppression; blur/occlusion;
  true acceleration and true extent changes; small objects and geometry error.
  A high spread can reflect two objects rather than noisy estimates of one.
- **Acceptance measures:** localization-error ranking and risk versus retained
  coverage against both baselines, stratified by class, size and scene; if a
  predictive distribution is actually defined, assess calibration and sharpness
  separately. Predeclare the correspondence rules, error scale, minimum group
  sizes, comparisons and uncertainty intervals before looking at outcome data.
  Correlated frames are not independent trials.
- **Stop:** if proposal capture changes outputs, its engineering gate fails.
  If localization signal adds no reliable value beyond baselines on separate
  scenes, do not implement a noise-adaptive association candidate. Generated
  tests can check arithmetic and failure cases, not satisfy this signal gate.
- **Only later:** freeze one justified association comparison with fixed
  detections, retaining count misses/extras per flow/time window, crossing delay,
  false output, coverage and ID errors. Improved covariance, IDSW or a pooled
  average alone cannot establish count safety. Decide acceptance margins before
  outcomes, and report regressions and abstentions as well as improvements.

Real-domain evaluation still needs permitted inputs and checked labels.
RoundaboutHD is one pending route, not a prerequisite for capture or the only
possible future source. Existing MOT17 material can support an explicitly
exploratory tooling check, never a relabeled untouched traffic test.

Python remains the readable reference and research environment. C++ stays on
its verified execution/compatibility path until an accepted useful method,
frozen behavior and an explicit handoff justify a port. No owner setup is
needed for the capture step; no external outreach or release is part of it.
