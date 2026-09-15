# VisionTrack Product and Research Strategy

## Executive conclusion

VisionTrack is not an object detector and should not try to become a generic
computer-vision platform. It is an **inspectable multi-object tracking research
and reliability system**: detections enter; stable trajectories and anonymous
short-lived identities come out; every association decision can be reproduced,
ablated, explained, and measured. The NumPy repository is the behavioral oracle
and experimental laboratory. The C++ repository is the parity-gated execution
engine proving that an accepted behavior can be made much faster without
quietly changing its output.

The strongest product direction is therefore not “another ByteTrack SDK” and
not “recognize everyone forever.” Both are poor fits. Tracking backends are now
readily available in full detector ecosystems, and persistent human recognition
creates a much harder open-set identification, governance, and privacy problem.
Ultralytics exposes ByteTrack, BoT-SORT, OC-SORT, Deep OC-SORT, FastTracker, and
TrackTrack behind one tracking interface; NVIDIA DeepStream supplies multiple
accelerated trackers and ReID galleries; OpenVINO publishes person-tracking and
ReID examples; Roboflow offers tracking as composable workflow blocks.^1,2,3,4

The recommended strategy has two mutually reinforcing parts:

1. **Product — VisionTrack Reliability Lab.** A local-first tool that evaluates
   a detector/tracker on a customer’s clips, identifies failure regimes, compares
   controlled alternatives, and exports an evidence-backed configuration and
   runtime. Its promise is not “we have another tracker”; it is “know why your
   IDs fail before deployment, and ship only a behavior you can reproduce.”
2. **Research — Selective Identity Continuity.** Study when a tracker should
   restore a recently retired anonymous identity and, more importantly, when it
   should abstain. The core question is how re-entry accuracy, false restoration,
   candidate-gallery size, crop quality, memory budget, and retention interact.

The first product proof should use **one bounded site and anonymous session
identities**—for example, a single retail entrance/zone or controlled workspace
lab—not global identity, named people, or indefinite retention. The vertical is
an evidence generator for the reliability product, not yet the company identity.

## 1. What VisionTrack is today

### 1.1 The NumPy repository

`visiontrack` is already three coherent assets:

- A readable, from-scratch online MOT implementation: 8-state Kalman filtering,
  rectangular Hungarian assignment, ByteTrack two-stage association, and a
  tentative/confirmed/deleted lifecycle.
- A controlled research harness: cached detections and embeddings, seeded
  experiments, paired comparisons, effect sizes, HOTA/IDF1/CLEAR-MOT metrics,
  failure taxonomy, and cross-checking against TrackEval.
- A communication layer: installable Python package, CLI, browser demonstration,
  live webcam tracker, benchmark reports, write-up, and learning modules.

Its existing research results reveal the project’s actual advantage. Appearance
helps identity association modestly and depends on crop/detector quality; a
learned motion residual can improve open-loop prediction while making the closed
tracking loop worse; Kalman “miscalibration” can act as robustness rather than a
defect. Those are system findings, not implementation checkboxes.

### 1.2 The C++ repository

`visiontrack-cpp` is not a second research fork. It is an execution contract:

- The NumPy tracker is the oracle.
- C++ optimization is accepted only after trajectory-level parity.
- The released core is roughly 55–74× faster on recorded MOT17 cases and
  71–91× faster across the recorded synthetic scaling sweep.
- Cross-platform wheels test compiler flags, NumPy provenance, tie-breaking,
  trajectory output, and numerical boundary behavior.
- GPU work was closed by measurement because the eligible workload and dispatch
  economics did not justify it.

That relationship is strategically valuable. Research can move quickly and
remain legible in Python; behavior that survives evidence can later cross a
formal parity gate into the runtime. The repositories should not be merged.

### 1.3 What the system currently does not do

- It does not train or own a competitive general-purpose detector.
- The browser tracker is motion/IoU based and has no appearance embedding path.
- Active appearance galleries disappear when tracks are deleted.
- It does not separate a continuous `track_id` from a re-entry-level
  `anonymous_identity_id`.
- It does not maintain bounded retired-identity memory.
- It does not evaluate false re-identification as a first-class error.
- It is not a multi-camera topology or calibrated 3D tracking system.
- It has no production event store, tenant model, retention enforcement, or
  operational dashboard.

These are boundaries, not automatically a backlog. Each addition needs to serve
the product/research thesis.

## 2. The surrounding landscape

### 2.1 Algorithms and packaged developer stacks

| Alternative | What it already provides | Consequence for VisionTrack |
|---|---|---|
| Ultralytics tracking | Detector-integrated tracking with six selectable trackers; several include ReID, camera-motion compensation, or duplicate-ID suppression.^1 | Competing on one-command tracking or number of tracker choices is weak differentiation. |
| NVIDIA DeepStream | GPU video pipelines, IOU/NvSORT/NvDeepSORT/NvDCF-style tracking, TensorRT ReID, feature-history galleries, batching, and multi-camera capabilities.^2 | VisionTrack cannot beat NVIDIA on GPU integration breadth; it can beat opaque tuning with reproducible diagnosis. |
| OpenVINO | Apache-licensed inference toolkit plus person detection/tracking/ReID examples and cosine embedding matching.^3 | An edge ReID demo is not novel by itself; OpenVINO is a plausible deployment/model runtime rather than the competitor to reimplement. |
| Roboflow Workflows | Cloud or self-hosted composable vision workflows with tracking blocks and external storage integration.^4 | Workflow composition is already productized; VisionTrack needs deeper tracking-specific evidence. |
| ByteTrack / Deep SORT / BoT-SORT / OC-SORT | Strong, well-known association baselines spanning low-score recovery, appearance, camera motion, and occlusion repair.^5,6,7,8 | New work must pose a falsifiable question rather than combine familiar components and label it novel. |

The open-source default is increasingly “choose a detector, select a tracker
configuration, and run.” This is convenient but often leaves teams without an
answer to which cue helped, whether an improvement generalizes, or what failure
cost is hidden behind one aggregate metric.

### 2.2 Evaluation and data tooling

TrackEval is the reference evaluation implementation for HOTA and supports
CLEAR, identity, and other metric families across major benchmarks.^9
MOTChallenge supplies common datasets, detections, evaluation, and leaderboards
to standardize comparisons.^10 FiftyOne provides interactive sample-level model
evaluation and data exploration, while CVAT provides manual and assisted video
annotation/tracking workflows.^11,12

These tools are strong adjacent products, but they leave room between them:

- TrackEval calculates metrics but is not a deployment-oriented diagnostic and
  configuration recommendation product.
- FiftyOne is a broad visual-data platform rather than an association-specific
  controlled ablation lab.
- CVAT creates and edits labels; it does not establish tracker reliability.
- Benchmark leaderboards reward dataset scores, not necessarily reliable
  decisions under a customer’s detector, camera, retention, or error costs.

VisionTrack should integrate with these formats instead of rebuilding their
general functionality.

### 2.3 Vertical products

RetailNext already combines foot traffic, shopper journeys, POS, operations,
asset protection, dashboards, and a conversational analytics layer, and states
that it measures billions of shopping journeys.^13 FootfallCam sells people
counting and retail metrics with edge processing and source masking.^14 Density
avoids RGB cameras entirely, using depth/radar sensors and positioning anonymity
as a hardware property.^15 BriefCam offers searchable video analytics, alerts,
counts, people/vehicle search, and face-recognition capabilities.^16

The lesson is not that product entry is impossible. It is that a credible
vertical product needs much more than tracking:

- Hardware selection and placement
- Calibration and site commissioning
- Detector quality under the site’s conditions
- Event semantics and data integration
- Dashboards, alerts, user permissions, and auditability
- Privacy, retention, security, and support
- Ground-truth audits and operational accuracy guarantees

A generic “people counter” would enter a mature category without using
VisionTrack’s strongest differentiator.

### 2.4 Research frontier

Current work continues beyond single-camera online MOT. MTMMC supplies a
large-scale real-world benchmark with 16 synchronized RGB/thermal cameras and
highlights the difficulty of generalizing across environments, seasons, and
camera configurations.^17 Recent multi-camera work combines geometry, time,
appearance, corrective association, and 3D reasoning.^18,19 Long-video and
multi-perspective work explicitly identifies long-term identity as a separate
challenge from ordinary MOT.^20

Research is also moving away from hand-designed association alone. MOTIP frames
tracking as in-context ID prediction, arguing that fixed handcrafted priors limit
domain adaptability.^21 This does not invalidate VisionTrack’s approach; it makes
the controlled oracle valuable as a baseline and diagnostic instrument.

Privacy is part of the research frontier, not merely a deployment footnote.
Person de-reidentification work explicitly treats the ability to unlearn matching
for specified people as an unsolved ReID problem.^22 Commercial occupancy vendors
differentiate by not capturing identifying imagery at all.^14,15

## 3. Where existing approaches remain weak

### 3.1 Configuration without causal evidence

Developer stacks expose many trackers and thresholds, but a user still has to
choose. An aggregate HOTA or IDF1 improvement does not explain whether the gain
came from better detections, crop quality, appearance, motion, camera
compensation, or more permissive lifecycle settings.

VisionTrack already has the machinery to make one change at a time and compare
paired outcomes. Productizing that loop is more defensible than adding another
tracker name.

### 3.2 Forced identity decisions

Many systems optimize closed-set association: every candidate belongs somewhere.
Re-entry in a real deployment is open-set. A new person may resemble somebody in
memory, and the correct output can be “unknown/new identity.” The cost of falsely
restoring an old identity can exceed the cost of fragmentation.

The missing product and research primitive is **selective association**:
confidence that is calibrated against candidate-pool size and permission to
abstain.

### 3.3 Benchmark-to-deployment mismatch

VisionTrack’s existing results already show that detector localization and crop
quality control whether ReID helps. A tracker selected on one detector and
dataset can fail after a camera angle, compression level, illumination condition,
or detector changes. Published trackers rarely provide a local, paired,
failure-regime acceptance test for a specific deployment.

### 3.4 Unbounded memory assumptions

Long-term identity is often described as “keep embeddings and search them.” That
ignores gallery growth, false-match probability, representation drift, deletion,
latency, and privacy. The meaningful problem is bounded identity continuity:
what to remember, for how long, at what fidelity, and with what rejection rule.

### 3.5 Metrics that hide product costs

HOTA balances detection, association, and localization; IDF1 measures identity
consistency.^9 But a site product also needs:

- False restoration rate
- Correct re-entry rate at a fixed false restoration budget
- Unknown/new-person rejection
- Duplicate anonymous identities per visit
- Accuracy versus gallery size and retention time
- Time-to-recover identity
- Count, dwell, and zone-event error
- Compute, memory, energy, and latency

These should become VisionTrack’s application-facing metric family.

## 4. Strategic options

Scoring uses 1 (poor) to 5 (strong).

| Direction | Repository fit | Differentiation | Product effort | Research depth | Overall |
|---|---:|---:|---:|---:|---:|
| Generic tracking SDK | 4 | 1 | 3 | 2 | 2.5 |
| Full retail analytics platform now | 2 | 2 | 1 | 2 | 1.8 |
| Long-term/global person recognition | 2 | 2 | 1 | 4 | 2.3 |
| Privacy-first local people counter | 3 | 2 | 2 | 3 | 2.5 |
| Tracking Reliability Lab | 5 | 4 | 4 | 5 | **4.5** |
| Selective bounded identity continuity research | 5 | 4 | 3 | 5 | **4.3** |

### Rejected as the primary direction

**Generic SDK.** It is useful packaging, but Ultralytics, DeepStream, OpenVINO,
and Roboflow already make basic tracking easy. The C++ package can remain a
runtime component without becoming the whole product.

**Global identity database.** Storage and vector search are technically
solvable; reliable open-world identification and responsible governance are the
real blockers. False matches grow more dangerous as the candidate population
grows. This direction also abandons the project’s transparent, bounded tracking
scope.

**Full vertical suite immediately.** Retail, security, sports, and traffic each
require domain data, integrations, and workflows. Choosing one before proving a
specific painful decision would turn the roadmap into speculative application
work.

## 5. Recommended product: VisionTrack Reliability Lab

### 5.1 User

The first user is a computer-vision engineer or small team deploying tracking
on proprietary video who can run a detector but cannot confidently answer:

- Which tracker/configuration should we ship?
- Why are identities switching or fragmenting?
- Will ReID help with this detector and camera?
- What changed after a model, threshold, or camera update?
- Can the fast runtime reproduce the accepted reference behavior?

### 5.2 Product promise

> Turn representative clips into a reproducible tracking acceptance report,
> then export the exact accepted behavior to a verified runtime.

### 5.3 Minimum workflow

1. Import a video or MOT-format detections; optionally import ground truth.
2. Run a baseline with a recorded detector/configuration fingerprint.
3. Run controlled variants using the same detections.
4. Compare HOTA/IDF1/CLEAR plus failure-regime and operational metrics.
5. Inspect identity switches, fragmentation, missed re-entry, and ambiguous
   decisions frame by frame.
6. Receive an evidence summary: what helped, what was neutral, what hurt, and
   where confidence is insufficient.
7. Export a versioned configuration, report, and—where supported—the parity-
   checked C++ runtime contract.

### 5.4 Product boundaries

- Bring-your-own detector initially; detector inference is an adapter.
- Local-first processing; upload is not required.
- No named-person identification.
- No global identity gallery.
- No claim that one configuration generalizes outside evaluated conditions.
- Reports always record code version, detector fingerprint, dataset/clip hashes,
  configuration, thresholds, and environment.

### 5.5 Why it can win

The product uses assets already present rather than inventing a new moat:

- From-scratch, understandable behavioral reference
- Controlled ablation surface
- Cached compute and reproducible experiments
- Paired statistics and failure taxonomy
- Exact Python/C++ trajectory gate
- Browser-based explanation and teaching surface

Its competitors are not just trackers. They are internal notebooks, ad hoc
threshold tuning, screenshots, and unrepeatable “this looked better” decisions.

## 6. Recommended research program: selective bounded identity continuity

### 6.1 Research thesis

Re-entry should be formulated as a **selective, open-set association problem
under a bounded memory budget**, not as indefinite person recognition.

Normal tracking asks which active track owns a detection. Re-entry asks whether
an unmatched detection belongs to any recently retired anonymous identity—or to
none. The system must estimate uncertainty and may abstain.

### 6.2 Identity contract

Keep two identifiers:

- `track_id`: one continuous visible trajectory.
- `anonymous_identity_id`: one or more tracklets linked within an authorized
  scope and retention window.

Every identity belongs to:

```text
organization / site / camera-group / session / anonymous-identity
```

No identifier is global. Identity profiles expire. Public webcam mode uses
memory only and clears everything on stop/reset.

### 6.3 Proposed research questions

**RQ5 — Selective ReID.** At a fixed false-restoration budget, when should the
tracker restore a retired identity and when should it abstain?

**RQ6 — Gallery scale.** How do candidate population, retention time, prototype
count, and quantization change correct restoration and false restoration?

**RQ7 — Crop quality versus model capacity.** Does quality-gating a small ReID
model outperform blindly applying a larger model to poor detections?

**RQ8 — Memory policy.** Which bounded policy—centroid, exponential average,
diverse prototypes, quality-weighted prototypes, or reservoir sampling—best
preserves identity per byte and millisecond?

**RQ9 — Contextual gating.** How much do time, entry/exit zone, camera topology,
size, and direction reduce false restoration beyond appearance alone?

**RQ10 — Confidence transfer.** Do thresholds calibrated on one detector,
camera, or gallery size remain valid after domain change? If not, which
calibration signal detects the failure before deployment?

These questions extend existing findings naturally. They are not “add ReID”; they
measure where identity memory becomes unsafe or ineffective.

### 6.4 Evaluation matrix

Experiments should vary independently:

- Absence duration: frames to minutes
- Gallery size: 10, 100, 1,000, 10,000 identities
- Prototypes per identity: 1, 2, 4, 8
- Representation: float32, float16, int8
- Crop quality: resolution, blur, truncation, occlusion, detector localization
- Appearance ambiguity: uniforms/similar clothing
- Illumination and viewpoint change
- Entry/exit geometry and camera movement
- Known return versus genuinely new person

Primary curves:

- Correct restoration versus false restoration
- Coverage versus risk as abstention threshold changes
- Accuracy versus gallery size
- Accuracy versus memory/latency
- Operational count/dwell error versus identity-level metrics

### 6.5 Storage model

Do not persist frame-level data by default. The pipeline should reduce frames to
bounded, purpose-specific state:

| Data | Default location | Default lifetime |
|---|---|---|
| Active motion/track state | Process/browser memory | Seconds |
| Retired identity prototypes | Bounded memory | Minutes |
| Tracklet summary | Local encrypted database when enabled | Policy-defined days |
| Zone/count events | Local or customer database | Business-defined |
| Aggregated analytics | Customer analytics store | Longer-term |
| Raw frames/video | Not stored | Explicit diagnostic opt-in only |

A 256-dimensional int8 prototype is about 256 bytes before index/metadata
overhead. Four prototypes for 10,000 recent anonymous identities are roughly
10 MB of raw vector payload, which is operationally manageable. The research
problem remains false association and governance, not byte capacity.

Retrieval should be hierarchical:

```text
active tracks in camera
  → recent retired identities in camera
  → authorized site/camera-group candidates filtered by time and topology
  → approximate-nearest-neighbor candidates
  → exact multi-cue reranking + ambiguity margin
  → restore or abstain/create new identity
```

## 7. Repository responsibilities

### 7.1 VisionTrack checklist

**Product foundation**

- [ ] Define stable input/output schemas for detections, tracks, tracklets,
  anonymous identities, events, and experiment manifests.
- [ ] Accept MOT-format files and a simple detector-adapter protocol.
- [ ] Turn the existing HTML benchmark into a data-backed React report explorer.
- [ ] Add synchronized error playback for ID switches and fragmentation.
- [ ] Save immutable experiment manifests and paired comparison outputs.
- [ ] Add exportable acceptance reports and configuration bundles.

**Research foundation**

- [ ] Add `track_id` / `anonymous_identity_id` separation to an experimental
  branch without changing the default tracker contract.
- [ ] Implement retired identities as a bounded component outside `Track`.
- [ ] Add explicit restore, reject, expire, and evict decisions.
- [ ] Build synthetic re-entry generation with controllable absence, ambiguity,
  drift, gallery size, and new-person probability.
- [ ] Define false-restoration and selective-risk metrics.
- [ ] Cross-check existing long-video/multi-camera metrics where applicable.
- [ ] Pre-register RQ5–RQ8 hypotheses and thresholds before real-data evaluation.

**Product proof**

- [ ] Run a same-camera, same-session public demo entirely on-device.
- [ ] Show active tracks, recent anonymous identities, confidence, and expiry.
- [ ] Include “clear identity memory” and a tracking-only mode.
- [ ] Validate one bounded vertical metric such as unique visits, dwell, or zone
  transitions using consented or license-compatible data.

### 7.2 VisionTrack C++ checklist

- [ ] Keep version 0.1.x focused on its released parity contract.
- [ ] Regenerate release parity/benchmark reports and support matrices.
- [ ] Do not implement identity-memory research independently.
- [ ] Once Python behavior freezes, port only the accepted gallery, candidate
  scoring, abstention, and lifecycle mechanics.
- [ ] Keep embedding inference outside the C++ tracking core; accept vectors from
  an adapter/runtime.
- [ ] Extend parity from `(frame, track_id, box)` to include tracklet termination,
  restore/reject decisions, `anonymous_identity_id`, expiry, and eviction.
- [ ] Benchmark latency and memory at 10–10,000 retired identities.
- [ ] Permit approximate indexing only behind a separate, explicitly inexact
  mode; do not weaken the default exact contract silently.

## 8. Delivery plan and gates

### Stage 0 — Direction freeze (1–2 weeks)

- Finish this strategy review and select the first user workflow.
- Interview 5–10 CV engineers or teams that have deployed tracking.
- Ask for their last failed tracking deployment, not feature requests.
- Collect representative failure clips that can legally be used.
- Write a one-page product problem statement.

**Gate:** At least three teams describe a repeated, expensive tracker-selection
or failure-diagnosis problem and agree to test a local prototype.

### Stage 1 — Reliability Lab alpha (3–5 weeks)

- Import detections/video and optional ground truth.
- Run existing baselines and controlled variants.
- Produce manifests, paired metrics, and a failure list.
- Build React drill-down from metric to frame/track.
- Export a shareable local report.

**Gate:** One external user can identify a real failure and make a different,
evidence-backed configuration choice without reading source code.

### Stage 2 — Selective ReID benchmark (4–6 weeks)

- Implement synthetic re-entry and bounded retired identities in Python.
- Define false-restoration, restoration, rejection, and risk/coverage metrics.
- Run gallery-size and crop-quality studies.
- Publish honest negative results and failure examples.

**Gate:** The system demonstrates a useful operating point under a declared
false-restoration budget and degrades visibly/quantifiably as scale changes.

### Stage 3 — Same-camera product proof (4–6 weeks)

- Integrate a compact, license-compatible ReID model.
- Add local-only browser/session memory where technically feasible, or provide
  a local edge process with a browser UI.
- Add identity-memory controls, expiry, and audit display.
- Measure end-to-end unique-count/dwell value.

**Gate:** The product metric improves over tracking-only while meeting latency,
memory, privacy, and false-restoration budgets.

### Stage 4 — Verified runtime (3–5 weeks after behavior freeze)

- Port accepted mechanics to C++.
- Extend trajectory and decision parity.
- Package the new version across supported platforms.
- Export the accepted configuration from the Reliability Lab.

**Gate:** Identical exact-mode decisions and a measured deployment advantage.

### Stage 5 — Vertical decision

Choose retail, sports, traffic, warehouse, or another domain only after the
alpha reveals who has the sharpest problem and accessible data. Then build the
smallest event workflow around that evidence.

## 9. Decision rules that prevent direction drift

Accept a proposed feature only if it satisfies at least one of these:

1. It makes tracking behavior more measurable, explainable, or reproducible.
2. It tests a falsifiable association/identity hypothesis.
3. It converts a verified reference behavior into a faster deployment contract.
4. It validates a concrete user decision with a measurable outcome.

Reject or defer it when:

- It merely duplicates a detector or tracker already available in mature stacks.
- It requires a global or indefinite identity database.
- It improves a benchmark number without a controlled explanation.
- It adds C++ behavior before the NumPy oracle and evaluation are stable.
- It starts a vertical application without data, user access, and a success
  measure.
- It depends on weights or software whose commercial terms have not been
  reviewed. Ultralytics, for example, distinguishes AGPL and enterprise use;
  OpenVINO is Apache 2.0.^23,24 This is a product design constraint, not a late
  packaging detail.

## 10. Immediate next actions

1. Treat the existing UI migration as support work, not the roadmap’s center.
2. Turn the benchmark report into the first Reliability Lab workflow before
   redesigning every remaining static page.
3. Draft the detection/tracklet/identity/experiment schemas.
4. Implement only a synthetic selective-ReID evaluation harness first—no live
   identity storage yet.
5. Define the acceptable false-restoration budget and abstention metrics.
6. Recruit three design partners with real clips and deployment failures.
7. Keep C++ in maintenance mode until a Python behavior passes the research gate.

## 11. Positioning

Avoid:

> VisionTrack is another fast object tracker.

Prefer:

> VisionTrack is an open, reproducible tracking reliability lab: it shows when
> identity logic helps, when it fails, and exports only behavior that survives a
> parity gate into production.

For the research program:

> VisionTrack studies selective identity continuity—how to reconnect short-lived,
> anonymous tracklets under bounded memory while refusing unsafe matches.

This preserves the project’s original character: build the mechanism from first
principles, ask a question that can be disproved, measure the result honestly,
and accelerate only what survives.

## Sources

1. Ultralytics. “[YOLO Multi-Object Tracking in Video](https://docs.ultralytics.com/modes/track).” Accessed September 14, 2026.
2. NVIDIA. “[Gst-nvtracker](https://docs.nvidia.com/metropolis/deepstream/8.0/text/DS_plugin_gst-nvtracker.html).” DeepStream documentation. Accessed September 14, 2026.
3. Intel OpenVINO. “[Person Tracking with OpenVINO](https://docs.openvino.ai/2024/notebooks/person-tracking-with-output.html).” Accessed September 14, 2026.
4. Roboflow. “[What is Workflows?](https://docs.roboflow.com/workflows)” and “[Workflow Blocks](https://docs.roboflow.com/workflow-blocks).” Accessed September 14, 2026.
5. Zhang et al. “[ByteTrack: Multi-Object Tracking by Associating Every Detection Box](https://arxiv.org/abs/2110.06864).” ECCV 2022.
6. Wojke, Bewley, and Paulus. “[Simple Online and Realtime Tracking with a Deep Association Metric](https://arxiv.org/abs/1703.07402).” 2017.
7. Aharon, Orfaig, and Bobrovsky. “[BoT-SORT: Robust Associations Multi-Pedestrian Tracking](https://arxiv.org/abs/2206.14651).” 2022.
8. Cao et al. “[Observation-Centric SORT: Rethinking SORT for Robust Multi-Object Tracking](https://openaccess.thecvf.com/content/CVPR2023/html/Cao_Observation-Centric_SORT_Rethinking_SORT_for_Robust_Multi-Object_Tracking_CVPR_2023_paper.html).” CVPR 2023.
9. Luiten and Hoffhues. “[TrackEval](https://github.com/JonathonLuiten/TrackEval).” Official HOTA and tracking evaluation implementation. Accessed September 14, 2026.
10. MOTChallenge. “[Multiple Object Tracking Benchmark](https://motchallenge.net/).” Accessed September 14, 2026.
11. Voxel51. “[Evaluating Models](https://docs.voxel51.com/user_guide/evaluation.html).” FiftyOne documentation. Accessed September 14, 2026.
12. CVAT. “[Annotation Modes](https://docs.cvat.ai/docs/annotation/manual-annotation/modes/)” and “[AI Tools](https://docs.cvat.ai/docs/annotation/tools/ai-tools/).” Accessed September 14, 2026.
13. RetailNext. “[AI Retail Analytics Platform](https://retailnext.net/).” Accessed September 14, 2026.
14. FootfallCam. “[People Counting System](https://www.footfallcam.com/)” and “[Privacy-First AI](https://www.footfallcam.com/Home/PrivacyFirstAI).” Accessed September 14, 2026.
15. Density. “[Do Density sensors use a camera?](https://support.density.io/hc/en-us/articles/1260804189489-Do-Density-sensors-use-a-camera)” Updated September 25, 2024.
16. BriefCam. “[Advanced Surveillance Systems for Business](https://www.briefcam.com/).” Accessed September 14, 2026.
17. Woo et al. “[MTMMC: A Large-Scale Real-World Multi-Modal Camera Tracking Benchmark](https://openaccess.thecvf.com/content/CVPR2024/html/Woo_MTMMC_A_Large-Scale_Real-World_Multi-Modal_Camera_Tracking_Benchmark_CVPR_2024_paper.html).” CVPR 2024.
18. Specker. “[OCMCTrack: Online Multi-Target Multi-Camera Tracking with Corrective Matching Cascade](https://openaccess.thecvf.com/content/CVPR2024W/AICity/html/Specker_OCMCTrack_Online_Multi-Target_Multi-Camera_Tracking_with_Corrective_Matching_Cascade_CVPRW_2024_paper.html).” CVPR Workshops 2024.
19. Wang et al. “[MCBLT: Multi-Camera Multi-Object 3D Tracking in Long Videos](https://openaccess.thecvf.com/content/ICCV2025W/AICity/html/Wang_MCBLT_Multi-Camera_Multi-Object_3D_Tracking_in_Long_Videos_ICCVW_2025_paper.html).” ICCV Workshops 2025.
20. Wojtulewicz, Liu, and Carlsson. “[Advancing Player Identification and Tracking with Global ID Fusion](https://openaccess.thecvf.com/content/WACV2026/html/Wojtulewicz_Advancing_Player_Identification_and_Tracking_with_Global_ID_Fusion_GIF_WACV_2026_paper.html).” WACV 2026.
21. Gao, Qi, and Wang. “[Multiple Object Tracking as ID Prediction](https://openaccess.thecvf.com/content/CVPR2025/html/Gao_Multiple_Object_Tracking_as_ID_Prediction_CVPR_2025_paper.html).” CVPR 2025.
22. Peng et al. “[Person De-reidentification: A Variation-guided Identity Shift Modeling](https://openaccess.thecvf.com/content/CVPR2025/html/Peng_Person_De-reidentification_A_Variation-guided_Identity_Shift_Modeling_CVPR_2025_paper.html).” CVPR 2025.
23. Ultralytics. “[Licensing](https://www.ultralytics.com/license).” Accessed September 14, 2026.
24. OpenVINO Toolkit. “[OpenVINO GitHub Repository](https://github.com/openvinotoolkit/openvino).” Apache License 2.0. Accessed September 14, 2026.
