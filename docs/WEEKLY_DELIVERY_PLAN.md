# Daily checkpoints and the next weekly goal

## Work resumes alongside the Bath enquiry — 2026-11-04

The owner's latest direction supersedes a project-wide pause: **wait for Bath
on RoundaboutHD, while continuing independent work.** The traffic comparison
below remains the main external-validation goal; it is not the only useful
work the project can do. A reply may resolve only some admission questions.
No substantive reply has been newly verified for this planning update.

| Work | Current dependency | Action |
| --- | --- | --- |
| RoundaboutHD media/annotation intake and outcome evaluation | Precise reuse terms, annotation semantics and then a small independent label audit | Keep this route on hold; silence or an automatic receipt cannot admit it |
| Long-running reference execution | Repository code, generated inputs and existing parity fixtures | Investigate active-track history growth and design an explicitly compatible bounded option |
| Next research question | Existing findings and primary literature | Decision and opt-in capture complete; measure capture cost and audit added localization information |
| Practitioner usefulness | A willing practitioner | Keep open without treating internal checks as external validation |
| C++ | An accepted, useful reference change and explicit handoff | Maintain current compatibility; avoid a speculative port |

### Next work package and completion checks

- [x] Recheck the repository plans and distinguish the dataset dependency from
      independent engineering and research work. Both repositories are clean
      and locally synchronized with their tracked remote branches at this check.
- [x] **Engineering first: assess bounded track history.** Inventory all history
      consumers, including optional motion models and public inspection APIs;
      measure growth on generated long-lived tracks. Specify compatibility and
      retention semantics before changing storage. Success is a measured,
      reproducible improvement with unchanged supported tracking output, or an
      explicit incompatibility finding. Do not silently truncate default/public
      histories or claim bounded total memory from one component.
      Implemented an optional retention policy and applied it inside read-only
      Lab replay. Default full history remains available. Generated direct
      output hashes agree exactly; both 6,000-frame diagnostic probes use about
      57% less peak traced allocation than published 0.5.1 with exact diagnostic
      content agreement. See [measurements and limits](DIAGNOSTIC_REPLAY_SCALING.md).
- [x] **Research next: narrow the observation-quality question.** Compare the
      completed box-gate, initiation and observation-availability findings with
      prior work. Ask whether localization uncertainty can be distinguished from
      actual motion well enough to improve association without the false-count
      costs already observed. This is a candidate question, not a novel method
      or an approved improvement. Define observables available at inference,
      closest baselines, disconfirming cases and acceptance measures first.
      If existing work answers it or the distinction is not identifiable, reject
      or narrow it instead of running another broad synthetic grid.
      The [completed decision](LOCALIZATION_RESEARCH_DECISION.md) reviews eight
      primary sources (three at abstract level), verifies two identical-input/
      different-reference constructions, rejects a guaranteed box-only cause
      classifier and selects a capture-only detector feasibility step. Existing
      uncertainty methods are acknowledged; no novelty or accuracy gain is claimed.
- [x] **Decision checkpoint:** finish with one scoped implementation result and
      one go/no-go research proposal. Generated-data findings remain engineering
      or controlled-mechanism evidence; representative traffic claims still
      require admitted data and checked labels. Do not count more planning
      documents, release checks or another known-video replay as that outcome.

### Next independent step: preserve detector proposals

- [x] Add opt-in, bounded per-frame proposal/suppression capture to the YOLOX
      decoder, with exact default detection/tracker-output parity. Keep current
      suppression/class semantics explicit; no automatic covariance or runtime
      association change. Authored tensors cover both layouts, grid decode, ties,
      class interactions and truncated groups; multi-frame tracking/reset matches
      exactly with capture off/on. See the [API and limits](YOLOX_PROPOSAL_CAPTURE.md).
- [x] Measure generated-input capture storage/compute and prefix coverage;
      optimize counts-only/group bookkeeping and JSON conversion with exact
      old/new output parity. See [cost and limits](YOLOX_CAPTURE_COST.md).
      The default prefix misses all returned winners in one authored case, so
      offline research must require complete groups or explicitly abstain.
- [x] Prepare the [offline localization-signal audit design](LOCALIZATION_SIGNAL_AUDIT.md)
      against size/class/score baselines. Proposal dispersion is a known
      approach, not a new method or trustworthy covariance by construction.
      No real-data outcome has been run.
- [x] Implement the small offline feature extractor and disconfirming controls.
      Arithmetic, abstention and counterexamples now run on authored captures;
      actual decoder output is also checked against ordinary detections.
- [ ] Pursue an independently checked, admitted input route for outcome
      comparison. Do not feed this signal into association yet.
      See the [acceptance and stop rules](LOCALIZATION_RESEARCH_DECISION.md#research-gate-after-capture).
      Real-domain conclusions require permitted inputs, independently checked
      labels and a frozen evaluation; the Bath route remains on hold. A
      [2026-11-11 UVH-26 image preflight](UVH26_LOCALIZATION_PREFLIGHT.md) proves
      capture works on one real permitted image, but the released annotations
      lack camera IDs for the required scene split and no outcome was scored.
      The [MV/ST label-stability audit](UVH26_CONSENSUS_AUDIT.md) now measures
      their overlapping image/box coverage; their shared annotation origin
      prevents either from acting as independent truth.

The initial literature check identifies relevant existing approaches:
[ByteTrack](https://arxiv.org/abs/2110.06864) recovers associations using low-score
detections; [OC-SORT](https://arxiv.org/abs/2203.14360) addresses motion-estimation
error accumulated during occlusion; [UCMCTrack](https://arxiv.org/abs/2312.08952)
models motion and projected uncertainty on the ground plane. These establish
prior art to examine, not a comprehensive novelty review or proof of a gap.

No dataset download, external follow-up, new package release or change to the
accepted C++ oracle is authorized merely by this work package. There is no
recording/setup task for the owner now. If the owner says "go next", proceed
with independent work and identify only the specific remaining dependency.

## Delivery update — 2026-11-02

[Python 0.5.1 is published](RELEASE_NOTES_0.5.1.md), with verified public
archives, fresh installs and both diagnostic workflows. The
[C++ 0.1.1 / Python 0.5.1 pairing](https://github.com/hulagerushikesh/visiontrack-cpp/blob/main/compatibility/prospective_oracle_0.5.1_evidence.json)
passes twelve platform/Python jobs, a fresh local suite and 35,387 exact cached
observations. This closes release-maintenance work, without changing tracking
defaults or the accepted C++ oracle. Bath's acknowledgement is still not a
rights/label answer. The main research outcome and conditional sequence below
remain open; no owner recording/setup task is required now.

## Current checkpoint — week ending 2026-11-01

This section supersedes the historical session sequence below. It summarizes
**2026-10-26 through 2026-11-01**, with next-week priorities for **November 2–8**.
Work happens during active sessions; the dates are planning windows, not a
scheduled job or a promise that external dependencies will resolve this week.

**Where we are:** a released tracking/reference engine, a verified C++ pairing
and an implemented Reliability Lab for explaining saved failures. We have not
yet demonstrated a better tracker for a representative traffic domain, validated
commercial demand or established a novel research contribution. Completion is
best reported by milestones below, not one percentage mixing these goals.

### This week's completed work

| Work package | Delivered and checked | What remains outside that result |
| --- | --- | --- |
| Installable Python delivery | [0.4.0 and 0.5.0 publication](RELEASE_READINESS.md), exact artifact checks, clean wheel/source installs and release CI gates | Association requires 0.5.0; older installed packages are not upgraded by a website update |
| Lifecycle diagnosis | [Offline initiation command](INITIATION_DIAGNOSTIC.md), matching Lab timeline and one-command prepared demo | Explaining a saved run does not improve its detections or tracking |
| Association diagnosis | [Actual gate/assignment explanation](ASSOCIATION_DIAGNOSTIC.md), published command/API, verified local import and optional numeric detail | No accepted gate/default change or proven tracking gain |
| Easier onboarding | No-install confirmation demo and separate three-step match-failure lesson in `/lab` | Browser interaction/visual QA and practitioner comprehension remain unverified |
| Controlled research | [54 paired initiation-threshold cells / 324 passes](INITIATION_THRESHOLD_FINDINGS.md), retained failures and unchanged controls | Candidate rejected: more true crossings also came with false counts; no traffic-accuracy claim |
| C++ compatibility | [Public Python 0.4.0 / C++ 0.1.1 evidence](https://github.com/hulagerushikesh/visiontrack-cpp/blob/main/compatibility/prospective_oracle_0.4.0_evidence.json): twelve platform/Python jobs and 35,387 exact cached observations locally | Accepted release oracle remains Python 0.3.0; no runtime port or new C++ release |

The [rain review](HVSD_RAIN_REVIEW.md), [source screen](REAL_TRAFFIC_EVIDENCE_GATE.md)
and stopped SVMOT detector case narrowed what we can responsibly test. They did
not supply the missing representative, independently checked traffic benchmark.
The latest delivered lesson passed 18 local checks and all seven hosted CI jobs;
those are engineering checks, not a substitute for that research evidence.

**Additional engineering capacity checkpoint (at the weekly close, now delivered in 0.5.1):**
[streaming diagnostics](DIAGNOSTIC_REPLAY_SCALING.md) remove full-file input and
output lists while retaining full replay and changed-evidence checks. A fixed
6,000-frame synthetic probe uses about 79% less peak Python-traced memory than
public 0.5.0, with matching explanation content. Active-track histories remain
a growth limit. This supports longer saved runs; it does not close the main
traffic comparison or usability outcome below.

### Wins, setbacks and what changes

- **Win:** users can now try a small explanation without installing Python or
  finding files. Engineers can inspect actual saved admission/gate/assignment
  decisions instead of inferring them from a box animation.
- **Win:** the released reference and C++ wheels have reproducible delivery and
  compatibility evidence. Historical reports and accepted defaults are retained.
- **Useful negative result:** lowering the birth threshold is not a generally
  safe fix. The controlled study exposed false-count costs before adopting it.
- **Missed outcome:** no admitted representative traffic comparison, proven
  accuracy gain, accepted new method or validated customer workflow this week.
- **Efficiency loss:** multiple dataset/video screens consumed effort without
  producing an admissible outcome study. Next week gets one bounded evidence
  route, with a stop decision; another broad source hunt is not the default.

### Next week — one main research outcome, with separate usability work

**Main aim:** get one narrowly scoped traffic comparison ready to execute on
permitted data with independently checked labels. If the evidence dependency
cannot be resolved, finish with a precise unresolved requirement and stop that
route, rather than count more synthetic/UI work as completion of this aim.

**Additional delivery checkpoint — 2026-11-01:** the existing association
diagnostic is now in [published 0.5.0](RELEASE_NOTES_0.5.0.md), after complete
local/hosted/install gates and a separate owner publication approval. Public
files and a fresh core/Lab installation are verified. This finishes an engineering
handoff gap while the main research outcome remains open. The single RoundaboutHD recheck
is complete and one clarification email was sent with owner approval. Resume
that route when the requested rights/label answers are available, rather than
repeat screening while waiting.

- [ ] **Check comprehension of the shipped lessons.** Walk through confirmation
      and match failure; record where the explanation is unclear and make only
      demonstrated corrections. Browser QA remains open while access is denied;
      static rendering and green CI cannot close it. The owner's comprehension
      is useful feedback, separate from target-practitioner validation.
- [ ] **Resolve one evidence route.** RoundaboutHD remains a rights-clarification
      lead, not admitted data. Reuse the [existing source gate](REAL_TRAFFIC_EVIDENCE_GATE.md)
      and spend at most one focused screening session on this route. Exact media
      rights, access, task fit and label provenance must be established before
      intake. No restricted download or outreach is authorized by this checklist.
      If permission needs an owner decision, prepare the concrete request first;
      waiting for a reply does not justify another speculative tracker feature.
- [ ] **Only after admission, audit a small development subset.** Fix the camera,
      frame range, label visibility/ambiguity rules and source versions; check
      labels independently of tracker output. Previously inspected rain/MOT17
      cases remain development material, not untouched validation.
- [ ] **Only after that audit, freeze one justified comparison before running it.**
      Keep detector inputs fixed for a tracker-only comparison; if the detector
      changes, name that separate factor explicitly. Retain baseline, controls,
      count misses/extras, identity errors, confirmation delay and compute costs.
      Choose no candidate solely because a known clip looks better.
- [ ] **Publish a bounded finding only when supported.** Report unchanged,
      harmful and ambiguous outcomes as well as gains. A lawful, reproducible
      diagnosis can be shown honestly; a better-tracker claim needs the relevant
      prospective evaluation. Public outreach remains a separate owner decision.
- [ ] **Keep C++ in maintenance.** Reuse the existing compatibility gates. Start
      another synchronization only when useful accepted Python behavior, frozen
      fixtures/API and an explicit handoff justify it. Lab lessons alone do not.

After usable data and labels are ready, the existing case-study estimate remains
**4–5 focused working days**; permission, annotation and external review time are
additional and currently unknown. A full research/product completion date cannot
be inferred from this estimate. There is no recording or setup task for the
owner now. Later, a short lesson review or a specific permission decision may
help; neither is silently treated as independent scene truth.

## Historical checkpoint — retained for provenance

The older plan below records how we reached this point. Its pending wording is
historical where the current checkpoint above records a completed delivery.

Planning checkpoint: **2026-10-26**. Days below mean focused work sessions, not
automatic work while the chat is idle or promised calendar dates. No reminder,
scheduled job, email, publication or new tracking study is authorized by this plan.

**Review-route update:** no separate reviewer is available, and the owner has
delegated the technical review to the assistant. The [bounded AI-assisted case
note](MOT17_AI_REVIEW_DECISION.md) is complete with a no-change recommendation;
independent scene/reference validation remains deferred. The owner confirmed
page/image/frame controls, not a completed trajectory review. This supersedes
the waiting dependency below **for exploratory documentation only**, not for
independently validated labels, causality or acceptance of a future fix.

**Next technical checkpoint:** the [fixed detection/association inventory](MOT17_ASSOCIATION_INVENTORY.md)
is complete without new tracker execution. It distinguishes missing/separately
unavailable detections from an unoffered low-score recovery pair. The
[prospective observation-availability recipe](OBSERVATION_AVAILABILITY_PROTOCOL.md)
now fixes all 12 small development cells, unchanged controls and complete
startup/episode/recovery reporting. [Execution and audit](OBSERVATION_AVAILABILITY_FINDINGS.md)
are now complete from the committed design: 36 repeatable passes, no skips or
selective retries, null effects and long-gap harms retained. The
[diagnostic-only warning protocol](CONTINUITY_WARNING_PROTOCOL.md) now fixes
the observable claim, one-frame support-capacity rule, 27 development cells,
size/motion controls and semantic counterexamples before implementation. The
offline observer, scenes, replay and separate auditor now pass hand fixtures and
tracker doubles. [All 27 cells and the separate saved-record audit](CONTINUITY_WARNING_FINDINGS.md)
are complete under the committed method. The registered synthetic screen passes,
but warnings cover only the shortage onset and cannot distinguish one object's
duplicate boxes from two objects. Next: specify the engineer's actual decision
and prospective representative evaluation before any UI or default change.
That decision is now fixed as a three-frame manual-inspection queue and the
[already known MOT17 case has been checked](CONTINUITY_WARNING_MOT17_FINDINGS.md):
five review tasks / 18 frames, only one of 44 corrected ID switches temporally
inside a queue, with different warned track IDs. A separate scalar audit passes.
This is exploratory transfer evidence, **not** the prospective representative
evaluation or independent physical review; v1 stays offline.
No promised fix, new public demonstration or C++ port; independent real-data
validation remains open. This is the current sequence, superseding the historical
waiting/review tasks below for explicitly exploratory work only.

## Big aim

**Give one tracking engineer a clear, reproducible explanation of a real tracking
failure and the trade-off behind a configuration choice.** A negative result is
valid; a prettier interface or one improved number is not the finish line.

The first audience hypothesis remains fixed-camera CV engineers and applied
researchers working on counts/trajectories. We must test usefulness with them;
we have not selected a validated commercial vertical or promised higher accuracy.

## Priority clarification: evidence before demonstration

The owner's clarification on 2026-10-23 supersedes a demo-first reading of this
plan. Do not wait for the owner walkthrough to advance technical research, or
create presentation work to fill time. The demo is an optional internal teaching
aid, not public readiness. Recommend a public demonstration only when the problem,
evidence and limitations are sufficiently clear and the owner agrees.

The [first real-data intake](REAL_DATA_CASE_INTAKE.md) has now verified the
existing MOT17-04-FRCNN cache against the pinned official annotations. This
admits **annotation-only diagnosis**, not a completed visual/checked-label
case study. The [unchanged baseline](REAL_DATA_BASELINE.md) now reproduces
byte for byte across two fresh full-sequence runs. The first chronological
switch (reference 85, 19 → 31 at source frame 54) has a bounded annotation
inspection; independent pixel review remains an explicit later gate.

## Weekly aim: establish the real-data baseline and its limits

Primary weekly target: a source-verified real-data input, a reproducible unchanged
baseline and one bounded, explainable diagnostic event (or an explicit absence).
Do not claim a causal visual explanation without pixels/review, or an improvement
without a prospectively fixed comparison. The owner walkthrough remains optional
teaching, not a prerequisite for this research work.

| Session | Our delivery | Owner help | Done means |
| --- | --- | --- | --- |
| Session 1 — intake | Verify the existing cache against official annotation members and define the limited admission | None for the annotation-only route | Done: exact source conversion, task/range and remaining visual/rights gates recorded |
| Session 2 — baseline | Run and reproduce an unchanged, full-sequence cold-start baseline with complete settings and outputs | None | Done: all four run files byte-identical; ignore handling, complete outputs and metrics retained |
| Session 3 — diagnose | Inspect the first chronological scored ID switch if present; document adjacent inputs/outputs without claiming a visual cause | Optional questions about the explanation | Done at annotation level: first switch at source frame 54, fixed 51–57 context plus same-event prior-match history; no visual cause claimed |
| Session 4 — review evidence | Fixed 22-image acquisition and preliminary AI-assisted triage done; private staged page ready. Independent human review remains | One separate reviewer can now use the ready local packet; no recording/setup needed | Record agreement/disagreement and ambiguity; preliminary AI inspection is not independent adjudication |
| Session 5 — decide scope | Summarize the baseline diagnosis; justify/freeze one comparison before outcomes, or stop if unsupported | Review the plain-language summary | A defensible next research decision, not a promised winner or demo deadline |

Sessions 1–3 are complete **at the annotation-only level**, as is the earlier
internal demo preparation. The [saved-box coverage diagnosis](REAL_DATA_COVERAGE.md)
now partitions all 21,825 misses: 19,387 without raw IoU ≥0.5 support, 149 with
only sub-threshold support, 270 losing eligible neighbours to ignore handling,
and 2,019 with eligible retained neighbours but no canonical match. These are
descriptive, not causal or recoverable-error counts. The
[unchanged association/lifecycle replay](REAL_DATA_TRACE.md) is now complete:
all 1,050 frames match, 19 remains updated, and 31 is created at 52 then confirmed
at 54. Nearby reference 89 overlaps 19 strongly; physical identity attribution
still needs independent pixels/label review. No intervention is justified yet.
The bounded review brief and reasons not to tune lifetime/gates/memory blindly
are recorded. A subsequent [independent metric check](REAL_DATA_METRIC_CHECK.md)
found IDSW 44 versus 43 and HOTA 0.52372649 versus 0.52554966. TP/FN/FP and IDF1
agree, but the equivalence check fails. **Evaluator alignment and a separately
versioned re-score of unchanged outputs now precede any new tracker comparison.**
Session 4's independent pixel/reference review remains a separate gate; do not
substitute a green test suite for metric agreement or visual evidence.

That [v2 evaluator correction](EVALUATOR_V2.md) is now complete: all 45 same-input
reference checks pass, legacy reports remain unchanged and frozen studies stay
at their original revision. Independent
[preprocessing verification](MOT17_PREPROCESSING.md), the general versioned
MOT17-policy correction, [v2 coverage and the extended same-event actual trace](MOT17_COVERAGE_V2.md)
are now complete as well. The corrected prior match at 37 changes the fixed
review window to **36–57**, not the old 45–57. Every raw/scored frame and v2
failure is reproduced exactly; track 19 stays updated/public throughout.
Visual/reference review is still separate and open.
This is measurement correctness, not improved tracking or public accuracy readiness.
The [Lab policy migration](LAB_EVALUATION_POLICY.md) is also complete: new schema-3
metrics explicitly carry preprocessing v2 through failures and reports, while
historical artifacts remain unchanged and mixed policies are rejected. This
does not replace Session 4's independent visual/reference review.
The [fixed source images and preliminary visual triage](MOT17_VISUAL_REVIEW.md)
are now ready: 22 images, exact annotation correspondence, private staged review
and no public pixels. The late boxes align with two separating figures; earlier
physical correspondence remains uncertain. No lifetime/memory/gate change is
justified. Independent human review, full case admission and the optional owner
walkthrough remain pending. These sessions need not consume five full
engineering days; permission/label availability may dominate calendar time.

The [read-only prior-prefix audit](MOT17_PRIOR_CONTEXT.md) now adds earlier saved
geometry: 19 is public from 3 and supports reference 85 alone through 35. No
additional pixels or tracker runs were needed. This makes the review question
more precise but does not complete Session 4 or justify an intervention.

The separate [file-to-score verification](MOT17_TEXT_ROUNDTRIP.md) is now complete:
actual reference text-file loading, preprocessing and all 45 corrected metrics
agree on the unchanged full baseline. This closes the adapter-only boundary of
the earlier checks. Independent scene/reference review is the next external
dependency; do not create another harness solely to occupy the waiting time.

Independent maintenance during that wait found and closed real gaps in the
existing C++ parity tools (omitted classes, signed-zero equality and ignored
unit-test failure). [The maintenance record](https://github.com/hulagerushikesh/visiontrack-cpp/blob/main/PARITY_GUARDS.md)
checks the published wheel against released and current NumPy separately.
Runtime behavior is unchanged. The earlier plan for owner review tomorrow is
superseded by the delegated-review update above; do not turn unused session
allowance into a speculative fix or additional data acquisition.

## Next big deliverable: one real-clip diagnostic case study

After a clip, permitted use and independently checked task labels are ready:

- [ ] Technical intake, task boundaries and label verification: about 1 focused day.
- [ ] Unchanged baseline plus one prospectively fixed comparison on identical
      detections; visual failure explanation and reproducible report: about 2–3 days.
- [ ] Review trade-offs/limitations, prepare the case study and seek one willing
      practitioner's workflow response: about 1 day, plus their availability.

This preserves the [milestone estimate](SHOWCASE_MILESTONE.md): **4–5 focused
working days after usable data/labels are ready**. Some intake work may already
be done in Week 1; do not count it twice. A real-clip draft is a stretch weekly
outcome only if dependencies are ready early. If they are not, the real-data goal
is **not achieved** by substituting the synthetic demo.

One clip can demonstrate diagnosis, not general accuracy, novelty, a tuned fix's
independent validation or product-market fit. Private footage can stay private;
sharing any pixels needs explicit permission. A consented two-person indoor
rehearsal is not automatically representative of traffic or a re-entry risk test.

## If data is unavailable

Spend at most one focused session assessing one suitable existing-dataset route.
If rights, task fit or labels fail, record the reason and stop that route. Do not
download restricted imagery or quietly reinterpret labels. A narrower annotation
diagnostic can proceed only if explicitly suitable; do not silently call it the
complete real-data goal or create another framework just to fill time.
Acquiring data, annotating it and independent review are real work, not included
in the post-readiness technical estimate. Escalate the specific missing choice.

## After the case study

With explicit approval, show the small example to a few relevant engineers or
researchers and ask whether it would help with a failure they actually face.
No automatic mailing, repeated follow-up or dependence on one contact. Record
whether they can use it, what input they have, and what decision it changes.
Continue broader discovery separately; interest is not a design partnership.

C++ stays in maintenance at its accepted Python contract. Do not port the rejected
gate-off or stopped counting-band candidate. A new C++ milestone starts only when
useful Python behavior, frozen fixtures/API and explicit adoption justify it.

## End-of-session update template

```text
Aim:
Finished artifact and verification:
What the evidence permits us to say:
Still open / blocked, and why:
Owner action (none unless needed):
Next bounded task and conditional effort:
Local / committed / pushed / deployed status:
```

Choose one main outcome per session. Judge weekly progress by understandable
evidence and user feedback, not commit count or an invented project percentage.
