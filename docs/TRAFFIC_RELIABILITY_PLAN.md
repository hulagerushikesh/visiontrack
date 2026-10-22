# Traffic reliability probe — bounded next milestone

Prepared 2026-10-21; updated 2026-10-22 with the verified synthetic input
generator. **No tracker experiment results, traffic deployment validation,
or selected product vertical.**

## Aim in plain language

Find out when a steady real-world journey looks unstable to a tracker because
of camera perspective or changing detection boxes, and whether that instability
changes a counting decision. Build an explainable experiment before proposing
a fix. We do not need a new email response or volunteer recording to start.

This is a focused application probe for the
[Reliability Lab strategy](PRODUCT_RESEARCH_STRATEGY.md), not a replacement for
the project or a new claim of algorithmic novelty. Private correspondence,
contact details and third-party project information are not reproduced here.

## Public-source inspection completed

Read-only review of [OTVision](https://github.com/OpenTrafficCam/OTVision) at
`a73cebe0d9fd737bba8ba7280cd782d4e5f7e9aa`:

- The inspected [IOU tracking plugin](https://github.com/OpenTrafficCam/OTVision/blob/a73cebe0d9fd737bba8ba7280cd782d4e5f7e9aa/OTVision/track/tracker/tracker_plugin_iou.py)
  greedily associates boxes by overlap, retains missing tracks for a configured
  age, and records detection-centre coordinates. It is not a Kalman tracker.
  This describes the inspected plugin, not every deployed or experimental system.
- The separate [coordinate transformation command](https://github.com/OpenTrafficCam/OTVision/blob/a73cebe0d9fd737bba8ba7280cd782d4e5f7e9aa/OTVision/transform/transform.py)
  reads existing track files and applies a reference-point homography. Therefore
  adding a post-tracking coordinate transform is not, by itself, an unfilled
  capability or an intervention in the association step.
- [Homography estimation](https://github.com/OpenTrafficCam/OTVision/blob/a73cebe0d9fd737bba8ba7280cd782d4e5f7e9aa/OTVision/transform/get_homography.py)
  and calibration diagnostics already exist. Do not present calibration or
  ground-coordinate output alone as a new contribution.

No upstream code was installed, executed, copied into VisionTrack, or changed.
No upstream issue, PR, dataset request, or benchmark access was created. Review
the upstream license and contribution policy before any future integration;
this plan does not authorize copying code or establish license compatibility.

## Ordered work checklist

### 1. Freeze the smallest useful experiment — recipe complete

The [v1 protocol](TRAFFIC_RELIABILITY_PROTOCOL.md) and locked JSON recipe now
specify these choices. Integrity and input-geometry checks do not run trackers
or open held-out tracking outcomes. The separate
[input generator](TRAFFIC_RELIABILITY_GENERATOR.md) is now implemented and tested;
the scorer and development tracker runner are next.

- [x] Define a separate, dataset-free ground-plane scene with an explicit
      camera projection and true object paths. Do not relabel our existing
      pixel-linear synthetic generator as a calibrated perspective model.
- [x] Define the measurement anchor explicitly. A box centre is not necessarily
      a ground-plane point; bottom-centre is also imperfect under occlusion and
      for different object shapes. Keep true contact points separate from both.
- [x] Register paired conditions: projection only; box-edge perturbation only;
      their combination; and an unperturbed control. Hold latent paths and
      random draws fixed across comparisons. Add missing detections only as a
      separately specified factor, not silently in the first comparison.
- [x] Freeze exact scene parameters, seeds, splits, tracker settings, anchor
      definitions, frame timing, crossing rules and scoring tolerances before
      inspecting comparative outcomes. Separate development and untouched
      scenario/seed groups. Record configuration and input digests.

Output: a reviewable protocol and deterministic fixture definition, protected
by a version-controlled digest lock. No modified
tracker, new public API, live-camera behavior or accuracy claim in this step.

### 2. Build and validate the failure-reproduction harness

- [x] Implement the separate projection/observation generator without changing
      old synthetic defaults, random streams or golden parity fixtures.
- [x] Test projection/inverse consistency for valid ground-plane points;
      reject singular transforms, nonfinite coordinates and near-horizon cases
      that invalidate the model rather than clamping them into good results.
- [x] Test anchor movement under box truncation independently of true motion.
      Verify that unperturbed controls remain unchanged.
- [ ] Replay fixed detections through the existing NumPy baseline with no
      appearance cue. Keep detector inputs identical between tracker variants.
- [ ] Export regime-labelled errors, input/configuration digests and known
      ground-truth events so another person can reproduce a failure.

Output: a reproducible mechanism demonstration. A mathematical projection model
is not a measured traffic camera, and box perturbations are not a real detector.

### 3. Connect errors to the operational outcome

- [ ] First specify a simple directed crossing event and a fixed counting
      window, including boundary, repeat-crossing, missing-frame and direction
      rules. Then extend to explicit origin-to-destination flows; a single line
      crossing is not already a complete flow-assignment evaluator.
- [ ] Score known crossings with one-to-one event matching, missed/extra counts
      and time-window errors. Prevent opposite errors from cancelling in a
      signed total. Test perfect, duplicated, missing and fragmented fixtures.
- [ ] Report ID switches, misses and trajectory completeness alongside counts,
      not as substitutes for them. Stratify by scene region and perturbation.
- [ ] Compare only predeclared interventions. Candidate later ablations include
      anchor choice and geometry-aware motion/noise; changing calibration,
      anchor, lifecycle and detector together cannot identify which helped.
- [ ] Report paired per-scenario effects and variation, including negatives.
      Do not tune on held-out results or treat correlated frames as independent
      statistical samples. Decide acceptance margins before the held-out run.

Output: an evidence-backed synthetic result, not proof of a better traffic
system. Do not build a traffic dashboard or announce a new tracker first.

### 4. Admit representative real evidence separately

- [ ] Find suitably licensed, representative fixed-camera traffic material and
      confirm annotations, privacy conditions and operational event truth.
      Public video availability is not complete permission or usable labels.
- [ ] Freeze recording/site-disjoint evaluation and detector versions. First
      hold detections fixed to compare tracking; then vary detector quality in
      a separate experiment. Evaluate class differences and actual blur/scale
      shifts rather than inferring them from noisy boxes.
- [ ] Validate on representative evidence before claiming transfer to traffic
      practice. Upstream unit-test assets are not automatically a representative
      benchmark, and another team's private benchmark is not available to us.

If suitable data is unavailable, publish only the appropriately scoped mechanism
result and limitations. Do not manufacture practical validation to close a task.

## Relation to the other work

- **RQ5 re-entry:** remains separate. The two-person recording is a rehearsal;
  it does not evaluate traffic flows or create a held-out-person study. MEVID
  remains on its [source-mapping hold](IDENTITY_CONTINUITY_DATASET_INTAKE.md).
- **VisionTrack C++:** no speculative geometry/identity feature port. Maintain
  the existing [runtime contract](CROSS_RUNTIME_CONTRACT.md). Port an accepted
  Python behavior only after a measured benefit, frozen input/output semantics
  and new parity fixtures justify the change.
- **Product discovery:** traffic is a candidate application. One written
  practitioner response is not a design partnership, representative market
  validation, permission to quote correspondence, or commitment to test our tool.

## When to reach out again

Only after we have a specific, reproducible, relevant result: exact public code
revision, small permitted fixture, baseline versus intervention, operational
metric, limitations and one concrete reason it might help their pipeline. Check
that it is not already implemented. A negative finding can be useful too.

Do not schedule automatic reminders or request meetings/private data as a
dependency. A future email, upstream issue or PR needs a separate owner request;
the current thank-you reply does not authorize continuing outreach indefinitely.
