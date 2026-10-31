# VisionTrack — next-step checklist

VisionTrack is the NumPy reference, research platform, and learning product.
Work here must protect readability, reproducibility, and the ability to explain
why a tracking change helps or hurts.

**Current delivery — 2026-10-31:** the Lab crossing diagnosis and its
[bounded threshold follow-up](INITIATION_THRESHOLD_FINDINGS.md) are complete.

- [x] Freeze and run 54 synthetic threshold pairs / 324 repeatability passes.
- [x] Retain recovered true crossings, false-count costs and all 36 exact controls.
- [x] Keep defaults unchanged after the no-harm gate fails; explain the result
      in `/lab/crossings` without presenting it as traffic accuracy.
- [x] Reusable opt-in offline birth/confirmation diagnosis on supplied local
      Lab detections, exact saved-output parity and compatible old reports.
- [x] Read-only terminal explanation and separate canonical JSON export with
      bounded windows, original detection keys and preserved warm-up history.
- [x] Optional local trace inspection in the Lab, verified against the
      active report/run/configuration, with a plain-language lifecycle timeline.
- [x] Simplify demo preparation to one opt-in command: keep the matching report,
      trace and five-minute guide together outside the unchanged sealed bundle.
      Check preview/refusal/failure behavior and the actual Python-to-Lab imports.
- [ ] Validate the walkthrough with a practitioner when available; preparation
      and rendered-component checks do not establish usability or product demand.
      Browser interaction QA is still unverified after the earlier access denial.
- [x] Check installable delivery for the source-only diagnostic and guided demo:
      separate wheel/sdist clean installs, core-only and Lab-extra commands,
      exact source/replay checks and actual Python-to-TypeScript imports. Retain
      the receipt and enforce the check in normal CI and the release build.
- [x] Freeze the [0.4.0 release scope and migration](RELEASE_NOTES_0.4.0.md),
      separating measurement corrections, optional tooling and the deployed site.
      Add an exact-tag/version/CI guard before the release build.
- [x] Prepare both 0.4.0 source declarations; preserve historical versioned
      fixtures and check fresh demo/report/trace producer versions. Restore exact
      frozen regression Git metadata only inside a disposable clone.
- [x] Pass local 0.4.0 candidate gates: 1,256 Python tests with the pinned metric
      reference, frozen historical regressions, parity/reset, web workflows,
      app/types/docs/lint and separate clean wheel/sdist installs.
- [ ] Verify exact-commit hosted CI and then the separate publication action
      using the [readiness checklist](RELEASE_READINESS.md).
      No automatic package release,
      new footage hunt, public accuracy claim or outreach follows from this list.
- [ ] Separate research gate: representative permitted traffic event/negative
      labels before accepting a detector+tracker change or proposing a C++ port.

For a short two-project snapshot of finished work, the current experiment's
eight milestone groups and remaining gates, see [Progress overview](PROGRESS_OVERVIEW.md).

## Active focus — H3.2 learning product

- [x] Create one public learning front door with three audience paths.
- [x] Add prerequisites, effort estimates, and completion outcomes.
- [x] Add previous/next stage navigation and automated route checks.
- [x] Refresh lessons that still describe shipped work as future work.
- [x] Link core concepts directly to their real source files.
- [x] Add dataset-free exercises for geometry, Kalman filtering, assignment,
      and track lifecycle.
- [x] Add a NumPy-versus-C++ parity capstone.
- [x] Complete mobile, keyboard, contrast, and reduced-motion QA.
- [x] Add a zero-to-hero curriculum for non-technical readers, students,
      developers, and the project research lead, plus a parity-focused C++
      mastery companion.
- [x] Surface zero-to-hero and research-lead paths from the deployed learning
      UI through `/learn/zero-to-hero` and `/learn/research-lead`, linking to
      their canonical source documents without copying the full curricula.

The detailed curriculum plan is in
[`LEARNING_PRODUCT_PLAN.md`](LEARNING_PRODUCT_PLAN.md).

## Next focus — H3.3 product direction

The product and research direction is defined in
[`PRODUCT_RESEARCH_STRATEGY.md`](PRODUCT_RESEARCH_STRATEGY.md). The immediate
goal is a local-first **VisionTrack Reliability Lab**, followed by research into
selective, bounded anonymous identity continuity. A vertical will be selected
only after user interviews and representative failure data identify the
strongest problem.

The first local workflow and its versioned records are defined in
[`RELIABILITY_LAB.md`](RELIABILITY_LAB.md).
The practitioner interview, evidence-rights, failure-intake, scoring, and
decision-gate process is defined in
[`PRACTITIONER_DISCOVERY.md`](PRACTITIONER_DISCOVERY.md).

- [x] Establish the React + TypeScript + Tailwind + shadcn/ui + Motion shell.
- [x] Migrate the landing, teaching, and real-footage routes first.
- [x] Keep the live tracker, study, roadmap, demo, and benchmark reports on
      their verified standalone implementations during the incremental migration.
- [x] Define the first Reliability Lab workflow, privacy boundary, immutable
      bundle layout, and v1 source/detection/experiment/output/failure schemas.
- [x] Implement typed Python records, canonical serialization, validation, and
      adapters for the first four v1 schemas.
- [x] Add deterministic JSONL readers/writers and an immutable local bundle
      scaffold for the four implemented v1 records.
- [x] Add a deterministic local comparison runner that replays one verified
      detection stream through baseline and variant tracker configurations.
- [x] Add an evidence-aware comparison summary with dataset-independent run
      diagnostics and explicit `insufficient_evidence` results for GT metrics.
- [x] Define and implement the portable ground-truth record plus a strict
      MOT-format importer before calculating tracking-quality metrics.
- [x] Compute verified per-variant tracking metrics from bundle-backed ground
      truth and update comparisons without introducing automatic selection.
- [x] Extract structured, evidence-linked failure events from verified GT and
      tracker outputs for frame-level diagnosis.
- [x] Build a deterministic, read-only local Reliability Lab report from the
      verified comparison and failure artifacts before adding an interactive UI.
- [x] Add a read-only React Reliability Lab route backed by the versioned report
      model before introducing local-file import or interactive decisions.
- [x] Add private, client-side `report.json` import with strict validation and
      retain the deterministic fixture as an explicit sample mode.
- [x] Add ephemeral client-side failure filters and read-only event details
      without recalculating or mutating verified report evidence.
- [x] Define immutable, optional local image-evidence manifests with strict
      lineage, PNG, dimension, and privacy validation before rendering media.
- [x] Surface fully revalidated image-evidence availability and privacy
      metadata in deterministic reports without embedding image bytes.
- [x] Add an explicit privacy-aware producer for bounded local PNG evidence,
      including input provenance and deterministic crop/redaction operations.
- [x] Expose evidence production through a preview-first local CLI with
      explicit frame paths and separate full-frame source-pixel confirmation.
- [x] Verify and deliberately reveal explicitly selected local evidence in the
      React Lab without directory scanning, uploads, or automatic pixel access.
- [x] Define and immutably persist an explicit human decision tied to the exact
      verified comparison and report lineage without automatic selection.
- [x] Expose human decisions through a preview-first CLI that prints exact
      lineage and requires `--write` for immutable persistence.
- [x] Verify and display an explicitly selected local `decision.json` in the
      React Lab without uploads, mutation, or automatic winner selection.
- [x] Add deliberate React decision drafting with an exact preview and explicit
      local `decision.json` download, while leaving bundles untouched.
- [x] Lock Python and browser decision serialization to shared accepted and
      rejected-all conformance vectors and enforce them in CI.
- [x] Add a preview-first deterministic synthetic Lab command that produces a
      complete verified report bundle without requiring private data.
- [x] Close the browser-draft-to-bundle loop with a preview-first external
      `decision.json` importer that fully revalidates lineage and preserves
      immutable, idempotent storage.
- [x] Migrate the long-form research write-up into reusable article components.
- [x] Add a unified React benchmark front door while keeping generated dataset
      reports authoritative at stable, dataset-specific URLs.
- [x] Bring the generated dataset-report template into the current visual system
      without turning generated evidence into hand-maintained React content.
- [x] Define the content-addressed synchronized failure-playback contract with
      paired timing grids, explicit missing/redacted media, and full local
      report/run lineage before adding playback UI or video decoding.
- [x] Build synchronized playback deterministically from one exact sealed
      report event and explicitly stored full-frame evidence without copying,
      decoding, scanning for undeclared media, or mutating its bundle.
- [x] Expose synchronized playback as a metadata-only CLI preview with visible
      lane gaps, privacy counts, complete fingerprints, and no write mode.
- [x] Lock playback fingerprints, canonical bytes, strict structure, timing,
      privacy, and local-path semantics across Python and the browser in CI.
- [x] Add an explicit playback JSON export that writes only canonical contract
      bytes to standard output, keeps errors on standard error, and never
      mutates the sealed bundle.
- [x] Add deliberate local playback JSON selection to the React Lab with strict
      active-report lineage verification and metadata-only timing, lane,
      privacy, availability, and missing-frame views.
- [x] Verify explicit lane-scoped playback PNG selections by exact filename,
      SHA-256, and bounded PNG structure; add synchronized manual stepping,
      concealed pixels, explicit reveal, and object-URL cleanup.
- [x] Add deterministic synchronized play, pause, restart, scrub, and rate
      controls with verified timing, bounded timers, reduced-motion handling,
      and no automatic pixel reveal.
- [x] Run one checked-in deterministic synthetic browser workflow through the
      production report parser, playback lineage, both PNG lanes, privacy and
      missing-slot boundaries, and bounded transport in CI.
- [x] Guide first-time Lab visitors through synthetic report generation,
      local import, review, and decision preview.
- [x] Rehearse fresh Python-generated reports through browser decision drafts
      and Python import in CI; verify both outcomes, calendar validity, exact
      bytes, lineage, preview-only behavior, and immutable storage. Surface the
      explicit download-to-bundle save step in the Lab.
- [x] Prepare a first-user walkthrough with a synthetic report and feedback
      template; keep report controls accessible during bounded, cancelable imports.
- [x] Address observed beginner confusion with an explicitly illustrative,
      three-step visual lesson before import, plain-language failure meanings,
      optional technical details and researcher-only decision drafting, and a
      shorter walkthrough that requires no installation or acceptance choice.
- [x] Distinguish images listed in report metadata from files checked in the
      current browser and pictures deliberately revealed; explain the optional
      manifest selection without treating file integrity as tracking accuracy.
- [x] Explain whole-report metric comparisons with baseline/change examples,
      plain-language meanings and per-metric directions, optional recorded
      settings and secondary metrics, and explicit trade-off/significance
      boundaries; preserve the report's values without selecting a winner.
- [ ] Complete the owner usability walkthrough and prioritize its observed
      blockers before inviting a practitioner to the same workflow.
- [x] Ship the first versioned, strictly validated, read-only benchmark explorer
      slice without replacing the generated reports.
- [x] Export structured experiment results as canonical schema-v1 benchmark
      JSON and enforce the same payload contract in Python and the browser.
- [x] Add deliberate local benchmark JSON selection to the explorer, validate
      before display, and retain the bundled sample as a safe reset path.
- [x] Add ephemeral benchmark view controls for metric and variant focus while
      keeping the complete validated report immutable and one-click restorable.
- [x] Lazy-load the Lab and benchmark explorer routes so research tooling does
      not inflate the default product-site bundle as these workflows grow.
- [x] Lock the existing `/live` tracker behavior and privacy contract before
      moving its UI into the shared React product shell.
- [x] Port the interactive tracker shell without changing tracker behavior or
      browser privacy guarantees.
- [x] Audit release readiness across Python, browser contracts, documentation,
      and package artifacts; record the remaining `0.3.0` release decisions.
- [x] Define the versioned Python-to-C++ synchronization boundary and exact
      dataset-free parity test plan before changing C++ tracker behavior.
- [x] Implement the canonical v1 golden fixture, SHA-256 identity, strict NumPy
      validator/runner, reset determinism check, and normal-CI CLI gate.
- [x] Mirror the exact fixture bytes in `visiontrack-cpp`, add a digest guard,
      and run exact output plus reset through its public binding in normal CI.
- [x] Record strict machine-readable synchronization evidence with both source
      revisions, fixture identity, successful CI runs, and the exact local
      numerical/toolchain reproduction context.
- [x] Freeze the `0.3.0` package/site scope, compatibility statement, explicit
      non-goals, known limitations, and user-facing release-candidate notes.
- [x] Modernize package licensing to SPDX metadata and turn documentation into
      a strict missing-link gate with explicit repository source/evidence URLs.
- [x] Bump both package version declarations to `0.3.0` only after scope and
      packaging gates were frozen; keep tagging and publication separate.
- [x] Move CI and release workflows to current Node 24-compatible official
      action majors and lock that release-harness policy in tests.
- [x] Publish `visiontrack-mot 0.3.0` through trusted publishing and verify the
      tag, GitHub Release, public wheel, sdist, metadata, digests, and attestations.
- [x] Prepare a consistent practitioner discovery playbook with screening,
      interview, lawful evidence intake, failure-case registration, scoring,
      synthesis, and an explicit proceed/narrow/stop gate.
- [x] Create an owner-only local discovery workspace outside both repositories
      with blank candidate, interview, rights, case, synthesis, and deletion
      records; keep all participant data and evidence out of Git.
- [x] Source a ten-lead, six-domain practitioner list from current public project
      channels without contacting anyone or treating public maintainership as
      validation; require review and screening before qualification.
- [x] Review contact-channel appropriateness, prioritize a mixed five-lead first
      wave, and prepare unsent, owner-gated outreach and follow-up drafts.
- [x] Prepare accurate personalized drafts for the four public first-wave leads
      while keeping the commercial deployment slot blocked on a real warm
      referral and retaining explicit per-recipient send approval.
- [x] Make the discovery round operationally ready with response/screener
      templates, consent-aware scheduling, a facilitator guide, anti-bias and
      data-boundary scripts, post-call scoring, and a private audit log.
- [x] Audit the four personalized first-wave messages against the research and
      privacy boundaries and prepare a single owner-facing review sheet with
      per-recipient approval, channel, risk, and staged-cadence checks.
- [ ] Interview 5–10 tracking practitioners and collect representative failure
      clips that can legally be evaluated.
- [x] Register the first selective anonymous re-entry experiment, including
      its outcome taxonomy, fixed controls, operating points, split policy,
      and stop gates; implement independent event-level scoring.
- [x] Implement the registered dataset-free re-entry stress probe and four
      decision policies; report held-out results for 10–10,000 candidates,
      including the 1,000-candidate margin rule's failed risk bound.
- [x] Export the complete original fixed-grid synthetic coverage/risk/recall
      trade-offs with development-only selection, explicit denominators and
      undefined rates, and untouched held-out reporting; reproduce the original
      results at all four gallery sizes without selecting a new test-set winner.
- [x] Audit the locally available DanceTrack annotation gaps and official
      dataset terms to identify a possible non-commercial research path.
- [x] Add a reproducible GT gap-candidate extractor with sequence-scoped IDs,
      deterministic duration-stratified audit sampling, and a frozen candidate
      digest; confirm its 1,370 candidates against the earlier read-only audit.
- [x] Triage the five pre-selected 100+-frame gaps at sparse checkpoints; record
      all five as *not verified*, without treating them as negative examples or
      changing the frozen sample.
- [x] Triage the five frozen 30–99-frame gaps at sparse checkpoints; record
      all five as *not verified*. Ten of 20 candidates have preliminary review,
      but none has a verified re-entry label or an untouched test status.
- [x] Complete preliminary triage of all 20 frozen DanceTrack GT gaps; identify
      two likely visible-but-unannotated short gaps and zero verified returns.
      Do not turn these audit dispositions into an accuracy or prevalence rate.
- [x] Define a consented, same-camera pilot capture and two-reviewer truth
      protocol with novel, return, lookalike, occlusion, expiry, and reset
      controls; keep collection owner-gated and separate from product use.
- [x] Add a metadata-only capture-ledger validator: require two distinct
      reviewer codes, ordered exit evidence for returns, and a private stable
      participant-group key to detect development/test identity leakage.
- [x] Add a pre-recording pilot-manifest contract for the camera, exit rule,
      absence/expiry intervals, bounded gallery, retention, rights-process
      references, and scenario counts; fingerprint owner-local frozen choices
      without creating a real participant record.
- [x] Add a strict, metadata-only owner-local preflight command with synthetic
      example inputs: freeze a private manifest fingerprint before recording,
      recheck a two-reviewer ledger against it, and output aggregate counts
      without reading media or claiming real-data accuracy.
- [x] Reconcile every frozen planned take slot against a private, strict
      recorded/missing/excluded inventory and its reviewed event link; report
      aggregate gaps without claiming footage, consent, or visual truth.
- [x] Add seeded, dependency-grouped descriptive intervals for RQ5 event risk
      and eligible-return recall; do not treat a zero-error or one-group pilot
      as passing the registered 1% risk gate.
- [x] Deprioritize DanceTrack GT gaps as the **first** RQ5 real-data source:
      preliminary review found zero verified returns, and independent dense
      adjudication has not occurred. Preserve the frozen audit; do not count
      these gaps as re-entry events or as a held-out test set.
- [x] Screen official PersonPath22 and BDD100K sources as possible backups
      without downloading data; record their use/fit caveats and keep the
      consented fixed-camera pilot as the first-study priority.
- [ ] For a chosen rights-reviewed source, freeze the event list and a
      participant- and recording-disjoint development/test split before any
      real-data comparison.
- [x] Start the owner-selected existing-dataset route with an official MEVID
      annotation-only audit: verify chip-table alignment and upstream participant
      separation, expose the empty row, and retain source-time/exit truth as
      unpassed gates. Document why ordinary MOT17 IDs are not re-entry truth.
- [x] Prepare a plain-language recording-day guide for the separate volunteer
      pilot, with owner choices and consent/storage/freeze checks before capture.
- [x] Investigate the official MEVID annotation toolchain without running it;
      document the unrecovered source mapping and hold admission rather than
      treating crop-local frames as chronological re-entry evidence.
- [x] Add an optional owner-local recording metadata check for resolution,
      reported rates, audio and frozen-plan mismatches, with synthetic tests
      and explicit unverified timing/consent/accuracy boundaries. Keep the
      two-person rehearsal separate from a disjoint-participant study.
- [ ] Establish MEVID tracklet-to-original-recording/time provenance and resolve
      its empty annotation row before freezing a development-only visual audit.
      Stop this same-session route if the mapping cannot be established.
- [ ] Secure rights-reviewed, identity-annotated re-entry data and freeze the
      detector, crop, identity/session split, and memory-expiry protocol before
      any real-data RQ5 claim.
- [ ] Validate the Reliability Lab problem with at least three prospective
      design partners.
- [ ] Choose one initial vertical only after that validation: retail footfall,
      sports, traffic, warehouse, or another evidence-backed domain.
- [ ] Write a one-page problem statement with user, input, output, and success
      measure before building an application.
- [ ] Identify which product value comes from tracking and which depends on the
      detector, data rights, or deployment infrastructure.
- [ ] Build only a small evidence-producing prototype after the vertical is
      chosen.

Owner walkthrough progress: the owner confirmed that the three-step teaching
example makes sense and opened an ID-switch event with the new explanation.
This is partial comprehension/navigation feedback, not a completed usability
review, research decision, or real-data validation. Image selection and optional
researcher decisions have not been reviewed by the owner in this walkthrough.

## Next independent milestone — traffic reliability probe

The bounded plan is [TRAFFIC_RELIABILITY_PLAN.md](TRAFFIC_RELIABILITY_PLAN.md).
It does not require volunteer capture or another external reply and does not
replace RQ5 with an unregistered traffic claim.

- [x] Inspect the public OTVision IOU plugin and post-tracking coordinate
      transformation at a pinned revision without changing or running upstream.
- [x] Define the ordered projection/box-instability probe, crossing-to-flow
      evaluation stages, real-data admission and Python/C++ handoff boundaries.
- [x] Freeze a separate ground-plane synthetic protocol and deterministic
      fixture definition before running or inspecting comparative outcomes:
      [v1 recipe](TRAFFIC_RELIABILITY_PROTOCOL.md), byte-level integrity
      preflight, explicit four-condition inputs and disjoint scenario/seed sets.
      No tracker comparison or held-out tracking run has been performed.
- [x] Implement the separate projection/observation input generator with
      validity/replay checks, paired noise and separate true/measured anchors:
      [input milestone](TRAFFIC_RELIABILITY_GENERATOR.md). No tracker outcomes.
- [x] Implement/test the frozen crossing scorer on hand-checked fixtures,
      preserving missed/extra events, matching priorities and time-window errors:
      [scorer milestone](TRAFFIC_RELIABILITY_SCORER.md). No tracker outcomes.
- [x] Implement/test the development-only baseline replay adapter, including
      pinned source/configuration verification, reset/fresh equality, public-row
      validation, provenance and crossing scores from the same output stream:
      [runner milestone](TRAFFIC_RELIABILITY_RUNNER.md). Development smoke and
      fixture cases only, not the complete study report or held-out tracking.
- [x] Add tracking/completeness and separate observation/matched-track contact
      localization diagnostics with region/pulse strata and canonical evaluator
      agreement checks: [diagnostic milestone](TRAFFIC_RELIABILITY_DIAGNOSTICS.md).
      Missing position estimates remain undefined; regional FP is not fabricated.
- [x] Add full-result export and complete paired development summaries; execute
      all 120 registered development cases from a committed clean harness, and
      verify the retained bundle's hashes. [Findings](TRAFFIC_RELIABILITY_DEVELOPMENT.md)
      preserve box-error failures, mixed interactions and the primary negative
      perspective-only result. This is not real-data validation or held-out tracking.
- [x] Freeze the complete harness/input digests before one-pass held-out tracking:
      [freeze and execution gate](TRAFFIC_RELIABILITY_HOLDOUT.md). Prepared and
      read-only verified from `fe88a16`; all 120 held-out input manifests are
      locked before held-out tracker outcomes or an opening claim. Public
      development commands still reject held-out inputs.
- [x] Execute the registered held-out grid once through the saved freeze and
      retain all runs/errors: 120/120 completed from `5ac67f2`, no failures,
      skips or selective reruns. Independently verify both bundles and all
      fixed endpoint summaries; record the [scoped development/held-out findings](TRAFFIC_RELIABILITY_FINDINGS.md)
      without tuning or a winner claim. The original opening is now consumed.
- [x] Register a separate minimal intervention question, comparator, practical
      margins and new untouched scenarios before changing behavior:
      [one-switch box-gate ablation](BOX_GATE_ABLATION_PROTOCOL.md). Geometry and
      exact-byte checks only; no new tracker outcomes or implementation freeze.
      Do not reuse the opened v1 characterization set as untouched evidence.
- [x] Implement and validate the separate [ablation input generator](BOX_GATE_INPUTS.md):
      all 120 development input combinations, paired detector fingerprints,
      immutable arrays and independent arithmetic/draw-order checks. No new
      tracker comparisons or held-out observations generated in this milestone.
- [x] Implement/test the separate [development reference scorer](BOX_GATE_SCORING.md):
      all 37 inherited endpoints, input regeneration, canonical match history,
      missing-value handling and hand-worked crossing/count/ID-switch fixtures.
      No new tracker comparisons or held-out inputs/outcomes in these tests.
- [x] Implement/test the [development replay adapter](BOX_GATE_REPLAY.md) using
      doubles: isolated one-switch configurations, actual pre-update detector
      receipts, reset/fresh checks, scorer lineage and drift failures. Actual
      new tracker comparisons remain unmeasured; no new held-out opening.
- [x] Implement/test the [development export and numerical-rule harness](BOX_GATE_REPORT.md)
      with hand-worked tables/doubles: full coverage, lineage/re-scoring, exact
      margins, nulls, all per-case regressions and retained partial variants.
      Commit before development comparisons; no new actual tracker outcomes yet.
- [x] Run and independently audit all 120 development pairs from the committed
      harness without tuning the candidate, margins or case selection:
      [development findings](BOX_GATE_DEVELOPMENT.md). All 240 variants / 720
      passes completed from `817e6f7` without errors or selective retries.
      Zero gate-off ID switches did not imply acceptance: 174 safety endpoint
      violations affected all 60 box-error pairs. Candidate not accepted;
      development-only numerical summary remains inconclusive by design;
      the combined interpretation is now recorded below.
- [x] Implement/test the [new held-out code/input/evidence freeze](BOX_GATE_HOLDOUT.md)
      and read-only verifier (milestone 7a): exact clean committed revision,
      runtime, reviewed negative development audit and all 120 future input
      manifests. Recheck the actual saved development evidence without tracker
      execution. The real freeze/opening subsequently completed below.
- [x] Implement/test the separate held-out scorer/replay/export execution gate
      (milestone 7b): exclusive opening before replay, ordered full coverage,
      reference re-scoring, retained variants/attempts, stop-on-error and no retry.
      Shared-core development scoring exactly reproduces 24 saved variant
      records. Tests use explicit doubles, separate from actual outcomes below.
- [x] Issue and verify the real exact-revision freeze from the complete committed
      harness, then execute the new held-out grid once through its exclusive gate;
      [all 120 pairs / 240 variants / 720 passes completed from `c99c4e7`](BOX_GATE_HELDOUT_RESULTS.md)
      without errors or selective retries. The 365-file artifact inventory and
      480-entry ordered ledger agree with the freeze, settings and replay receipts.
      Saved endpoints contain 206 safety violations in all 60 box-error pairs;
      no candidate acceptance. The opening is consumed and remains untouched.
- [x] Audit saved arithmetic and report [combined findings](BOX_GATE_FINDINGS.md):
      all 240 pairs / 480 variants / 1,440 recorded passes; 17,760 endpoint values,
      8,880 contrasts and exact margins checked without a new tracker run.
      Final registered classification **failure**: 174 development + 206 held-out
      safety violations across 120 affected pairs. Keep defaults/C++ unchanged.
      The pinned development auditor and original indices are not rewritten.
- [x] Inspect all 120 saved development pairs in a read-only
      [symptom diagnosis](BOX_GATE_DIAGNOSIS.md). Separate missing public output,
      below-threshold overlap, ID continuity and crossing timing; retain all
      conditions and common-frame localization without any new tracker run.
      Internal gate causes remain unproven because those traces were not saved.
- [x] Specify/test [opt-in association/state tracing](BOX_GATE_TRACE.md) outside
      production, capturing actual masks/costs/assignments and state transitions.
      Authored fixtures verify exact outputs/state, budgets and cleanup; they
      are not a replay of saved development evidence or a new validation study.
- [x] Build/test and commit the [development-only replay wrapper](BOX_GATE_TRACE_REPLAY.md),
      requiring complete exact saved-output parity and retaining failure receipts
      before any exploratory study trace or next intervention.
- [x] Run the [complete-grid development diagnostic](BOX_GATE_TRACE_FINDINGS.md), retain failures,
      and require exact saved-output parity before interpreting internal causes.
- [x] Independently audit its 482 files, all 240 exact output comparisons and
      55,578 recorded association stages; explain scoped startup, pulse rejection
      and same-ID line-recrossing mechanisms. No accepted fix or held-out replay.
- [x] Register the narrower [counting-only confirmation-band study](CROSSING_BAND_PROTOCOL.md)
      with identical tracker outputs, fresh paths/seeds, genuine shallow/start/end
      passages and explicit count/delay safety gates. The read-only preflight
      and deterministic geometry tests produce no noisy observations or outcomes.
- [x] Implement the [isolated counter](CROSSING_BAND_COUNTER.md) and 64 authored
      boundary/gap/reversal/timing tests. Retain real short-passage misses,
      unfinished/canceled state and excessive delay; no association/default change.
- [x] Review structural misses/delay: [stop at engineering feasibility](CROSSING_BAND_COUNTER.md#feasibility-decision-2026-10-23).
      Retain genuine-passage misses and the excessive-delay example. This is
      not an executed study verdict; registration/locks remain unchanged.
- Not undertaken after this stop: full-grid input/replay/report harness,
      development/held-out execution and audit. Do not mark these complete,
      silently tune v1 or relabel consumed evidence as untouched validation.
- [x] Screen nine public traffic/camera candidates against rights,
      annotation/task fit and access; record why none is yet admitted in the
      [real-traffic evidence gate](REAL_TRAFFIC_EVIDENCE_GATE.md). This is
      source triage, not a benchmark run or validated utility.
- [x] Check browser-imported `report.json` against its producer's canonical
      content fingerprint before treating it as usable Lab evidence. Preserve
      Python numeric bytes; keep the check distinct from authorship, source
      authenticity and tracking accuracy.
- [x] Label browser-checked report integrity precisely in the Lab UI: a local
      fingerprint is not a source-file, label, author or accuracy verification.
- [ ] Admit one official, rights-verified dense sequence, independently audit
      its development labels/task truth, and freeze detector/split/decision
      measures before comparative outcomes. No alternate mirror or inspected
      sequence becomes an untouched holdout by relabeling it.
- [ ] Validate any transfer claim on representative rights-reviewed evidence.

## Active delivery goal — one understandable case study

See the [showcase milestone, audience and conditional effort estimates](SHOWCASE_MILESTONE.md).

- [x] Prepare the [five-minute existing-report demo](SHOWCASE_DEMO.md): generated
      and separately reproduced report, Python/browser import validation,
      one miss, an honest tie and a separate completed synthetic trade-off.
- [ ] Complete the owner's short walkthrough and record actual comprehension
      feedback; preparation is not a completed usability study.
- [ ] Admit one permitted real clip with an explicit task, detector and checked
      labels; data acquisition/permission is not assumed complete.
- [x] Verify [one existing real-data cache against official annotations](REAL_DATA_CASE_INTAKE.md):
      MOT17-04-FRCNN, annotation-only diagnosis admitted; full visual case still held.
- [x] Reproduce its [unchanged full-sequence baseline](REAL_DATA_BASELINE.md):
      two fresh byte-identical runs, all metrics/raw/scored outputs retained;
      first chronological switch at source frame 54 inspected at annotation level.
- [x] Complete the [saved-box coverage decomposition](REAL_DATA_COVERAGE.md):
      all 21,825 misses partitioned with score/ignore rules, unique assignment
      capacity and explicit non-causal limits; no new tracker execution.
- [x] Inspect [unchanged association/lifecycle evidence](REAL_DATA_TRACE.md) for
      the same first switch: all 1,050 replay frames exactly match the baseline;
      19 remains updated, 31 is created at 52 and confirmed at 54. Shared geometry
      with reference 89 prevents a confident physical-identity interpretation.
- [x] Record the resulting intervention decision and a bounded independent-review
      brief: no gate-off, lifetime, memory or confirmation change is justified yet.
- [x] Acquire the fixed 36–57 source-image window for bounded local non-commercial
      research, verify annotation correspondence, retain receipts and perform
      [preliminary AI-assisted visual triage](MOT17_VISUAL_REVIEW.md). No public pixels.
- [x] Prepare a private scene/reference/output review page with explicit local
      notes and offline control tests; do not claim independent human review.
- [x] Audit [all saved prior frames 1–35](MOT17_PRIOR_CONTEXT.md) without new
      images/replay: public 19 supports reference 85 alone at IoU >=0.5 in all
      33 public frames. This strengthens reference-relative history, not physical
      identity truth or permission to bypass independent visual review.
- [ ] Independently review references 85/89 in the sealed event context; record
      disagreement, do not silently change labels/scoring or hunt a new event.
      Deferred on 2026-10-26: no separate reviewer available; not marked passed.
- [x] Complete the owner-delegated [AI-assisted exploratory case review](MOT17_AI_REVIEW_DECISION.md)
      and reasoned no-change recommendation using existing 36–57 pixels and saved
      evidence. This is not independent validation or a completed owner review.
- [x] Inventory [every supplied detection and actual offered pair](MOT17_ASSOCIATION_INVENTORY.md)
      in the same 36–57 trace. Frames 36–50 cannot provide two distinct eligible
      neighbours for references 85/89 at diagnostic IoU >=0.5. The low-score row
      at 51 is not offered to already high-matched 19; no tracker rerun or fix.
- [x] Prospectively fix the [observation-availability development study](OBSERVATION_AVAILABILITY_PROTOCOL.md):
      fixed trajectories/settings, distinct versus missing or shared support,
      unchanged-input control, startup/recovery strata and complete failure reporting.
      Generator/scorer/replay-double tests precede actual tracker outcomes.
- [x] Execute and [audit all 12 observation-availability cells](OBSERVATION_AVAILABILITY_FINDINGS.md):
      36 repeatable passes, exact unchanged controls, short-gap null ID effects
      and long-gap harms retained. Same miss totals can conceal different ID
      histories; a same-ID first recovery can subsequently switch.
      No tracker candidate, real-case causal validation or C++ adoption.
- [x] Specify the [diagnostic-only continuity-warning study](CONTINUITY_WARNING_PROTOCOL.md)
      before implementation: previous-public/current-detector inputs, distinct
      support capacity, 27 development cells, size/motion/false-alarm controls,
      indistinguishable semantic pairs and explicit usefulness/error/stop limits.
      No GT-fed runtime, identity confidence or automatic fix; no outcomes yet.
- [x] Implement the offline warning and recipe with hand-written boundary,
      capacity, input/GT-separation and non-interference fixtures. Commit the
      implementation/test freeze before actual tracking; do not change defaults.
- [x] Run and [audit all 27 frozen warning cells](CONTINUITY_WARNING_FINDINGS.md):
      108 tracker passes, all replay/integrity gates and the predefined synthetic
      screen pass. Warnings occur only at episode onset; zero warnings do not
      imply stable identity, and duplicate detections mimic shared support.
      Keep the diagnostic offline; no post-outcome retuning, identity-correctness
      claim or real-world false-alarm estimate.
- [x] Fix one engineer triage decision and run the [complete exploratory MOT17
      transfer check](CONTINUITY_WARNING_MOT17_FINDINGS.md) from committed
      method `b2027ee`: all 1,050 detector/public-output frames match the sealed
      baseline, all saved warnings pass a separate scalar audit, and the
      three-frame queue covers only 1/44 corrected ID switches by *time*—not by
      implicated track. Do not retune this known case or ship the alert.
- [ ] Prospectively evaluate whether this bounded warning helps a fixed-camera
      tracking engineer with a specified decision, permitted representative
      observations and independent reference review. Record missed problems and
      warning burden before considering user-facing UI or a v2 design.
- [x] Recheck the official GRAM route and screen three other official
      fixed-traffic sources against the actual decision and terms. GRAM's kit
      remains inaccessible here; AI City 2021 offers count labels rather than
      dense ID truth; CityFlowV2's multi-camera-only annotation rule leaves
      single-camera coverage incomplete; UA-DETRAC needs asset-level terms.
      No new source is admitted, downloaded, scored, or called a holdout.
- [x] Extend the [official source screen](REAL_TRAFFIC_EVIDENCE_GATE.md) to
      sixteen candidates: UTUAV v2 B/C offers MOT labels but requires publisher
      contact and credentials; MEVDT's repository is blocked here and its DOI
      metadata lacks dataset rights; eTraM's modalities and license statements
      need resolution; FLUID's derived tracks are not independent truth. This
      selects an access lead, not an admitted benchmark or a tracker result.
- [x] Replace the owner-recorded traffic-footage dependency with a
      [public-source feasibility path](PUBLIC_TRAFFIC_VIDEO_FEASIBILITY.md):
      verify all three HVSD V1 publisher-hosted MP4 bytes and decoded timelines,
      retain the night header/decoded-frame discrepancy, and reproduce an
      unchanged 194-frame rain detector/tracker smoke run. Add I24V and TrafficMOT
      to the rights/task screen (18 candidates total). None supplies an admitted
      complete dense outcome study here; no accuracy or continuity claim follows.
- [x] Prepare a private source-only, frame-by-frame rain review page with an
      explicit lower-road crossing line, `clear`/`uncertain` event marks and a
      local JSON download. The question was selected after the aggregate smoke
      run and is exploratory development work, not a prospective test.
- [x] Audit the owner's six source-only JSON downloads against the pinned rain
      clip/line and deduplicate the repeated frame-57 mark. Five distinct clear
      crossing marks remain. Reproduce the unchanged pipeline receipt and
      compare one precisely defined adjacent-frame public-track crossing rule:
      one model event near frame 27, none near the other four marks. See
      [rain review](HVSD_RAIN_REVIEW.md). No accuracy or dense-ID claim follows.
- [x] Obtain the owner's attestation that all 194 frames were reviewed and
      inspect ±4-frame detector/public/tentative-track diagnostics around all
      five marks. The frame-92 window has no retained near-line road-class
      detection; frame 160 has repeated detector proposals but fragmented
      tentative tracks. See [rain review](HVSD_RAIN_REVIEW.md).
- [x] Inspect source frames around the four non-reported rain marks and compare
      them with frozen detector/public/tentative traces. Record approximate
      crossing timing, the frame-160 car/van ambiguity, and the stage of each
      visible gap in [the bounded diagnosis](HVSD_RAIN_REVIEW.md). This is an
      AI-assisted second look, not independent dense truth or causal proof.
- [x] Trace tentative association gates on the pinned rain replay without
      changing tracker output. At frame 162 a near-line candidate passes IoU
      but fails the Kalman distance gate; record the exact values and retained
      receipt in [the bounded diagnosis](HVSD_RAIN_REVIEW.md). Do not treat the
      candidate pairing as verified physical identity or tune defaults on it.
- [x] Run a one-setting paired replay on the rain clip: lower only the new-track
      threshold from 0.60 to 0.55 after the frame-57 inspection. It emits one
      additional near-mark crossing, but also changes public output elsewhere.
      Keep the default unchanged until independent dense truth and a frozen
      protocol can measure both gains and errors; see [rain review](HVSD_RAIN_REVIEW.md).
- [x] Recheck SVMOT's publisher metadata: its record API supplies CC BY-NC 4.0
      despite a blank rendered Rights field. Verify the five small release
      files and the 21/9 scene-disjoint split in a [metadata-only intake](SVMOT_INTAKE.md).
      Keep it as a non-commercial research candidate; no archive or test labels
      were opened.
- [x] Read a bounded SVMOT development sample by publisher byte ranges and
      [audit its labels and supplied detections](SVMOT_INTAKE.md). Four sampled
      training sequences have 30,762 exact GT/detection box matches and three
      sequence-name mismatches. This is source triage, not a tracker result;
      test scenes remain unopened and dataset admission remains on hold.
- [x] Extend the SVMOT development audit to verify occlusion/GT cross-references
      and inspect separated camera frames and ROI masks. The four selected
      sequences have 30,762 structurally matching occlusion records and 25,607
      valid occluder links; visual spot checks and ROI coverage do not establish
      independent label truth or flow-count utility. See [bounded intake](SVMOT_INTAKE.md).
- [x] Preselect and visually inspect a bounded SVMOT training occlusion span.
      The 22-frame severe-overlap event in `seq_04_morning` plausibly preserves a
      silver sedan's ID, but frame 297 is fully hidden, so identity there is an
      inference. All 25,607 sampled occlusion links are exact GT-box
      intersections, and all 30,762 visibility values follow overlap geometry
      to three decimals. These are correlated annotation fields, not separate
      quality checks. Source admission remains on hold; see [intake](SVMOT_INTAKE.md).
- [x] Count the SVMOT visibility-policy denominator before scoring: 188 of
      30,762 sampled GT rows are fully hidden, and 2,795 have visibility below
      0.5. A future protocol must state how detector coverage and track
      continuity treat those rows; no cutoff or outcome was selected here.
- [x] Run a [pinned detector-only SVMOT preflight](SVMOT_INTAKE.md) on the 29
      already reviewed training frames. YOLOX nano emitted 24 car boxes but none
      overlapped the selected car's box at all, including seven clear boundary
      frames. This model/input setting cannot test that identity-continuity case;
      it is not a tracker score or a whole-dataset recall estimate.
- [x] Freeze and run a [second detector feasibility screen](SVMOT_INTAKE.md)
      on the same SVMOT development event. YOLOX-X overlaps the selected car's
      box in 1/3 clear frames before and 3/4 after, failing the predeclared
      two-on-each-side rule. Stop this event as a tracker-comparison candidate;
      the mid-occlusion overlaps do not prove physical identity.
- [x] Add a reusable numeric MOT GT/detection geometry screen with exact input
      hashes, duplicate-aware counts and explicit unverified-independence
      semantics. Recheck the four bounded SVMOT training pairs: all 30,762
      supplied detections mirror GT box geometry. The private receipt is
      source triage, not a tracker outcome or proof of annotation quality.
- [x] Inspect the official RoundaboutHD ZIP64 index and small README by bounded
      byte ranges. Four single-camera GT members and manually checked detection
      labels are declared; no media or tracking labels were opened. Its media
      licence and full archive checksum remain unresolved, so admission stays
      on hold despite stronger annotation-format fit.
- [x] Screen the small official Khan/Kelly V2 description against the traffic
      question before its 7.9 GB archive. The publisher-hash-matched file says
      some video uses a moving dashboard camera and describes detection labels,
      so reject it as fixed-camera MOT truth without opening the archive.
- [x] Run a [bounded DroneTrafficZA2020 count-source audit](DRONETRAFFICZA_INTAKE.md)
      on publisher-hash-verified small files. A malformed reference row,
      mismatched entry/crossing semantics and unverified output interval hold
      a count comparison; the drone scene has no dense ID truth for the main gate.
- [ ] Admit a separate permitted, independently annotated traffic source only
      after camera provenance, exact asset rights, label quality, integrity and
      a scene-disjoint frozen protocol pass. Resolve the remaining object-level
      and association-gate questions there, without tuning on the inspected
      rain clip or calling it a holdout.
- [x] Run an [independent metric check](REAL_DATA_METRIC_CHECK.md) on all saved
      scored pairs; retain the discrepancies and three non-tie/history/fragmentation
      counterexamples. This is a completed diagnostic, not a metric-equivalence pass.
- [x] Complete [evaluator v2](EVALUATOR_V2.md): corrected HOTA/CLEAR, explicit Lab
      versions, preserved legacy reports/studies, unchanged-output re-score and
      all 45 reference metric checks passing. No tracker tuning or old-result rewrite.
- [x] Independently check [MOT17 preprocessing](MOT17_PREPROCESSING.md): all
      1,050 frames agree. Correct/version the broader policy, retain legacy
      reproduction and keep existing Lab preprocessing explicit.
- [x] Close the separate [real text-loader/export gap](MOT17_TEXT_ROUNDTRIP.md):
      original GT bytes and 27,842 saved predictions pass the actual reference
      loader, exact 25,781-output processed correspondence and all 45 corrected
      metric checks. No tracker execution or physical-label acceptance.
- [x] Re-derive [v2 missed-object coverage](MOT17_COVERAGE_V2.md): 19,393 without
      raw overlap, 149 low-score-only, 270 ignore-removed, 2,013 eligible retained.
      There are 29 replaced object/frame misses, plus 25 changed history records;
      the earlier 54-object/frame shorthand was incorrect.
- [x] Extend the same first-event actual trace under corrected history:
      prior scored match is frame 37; window 36–57; all 1,050 frames match,
      738 events/66 stages recorded, track 19 updated/public throughout.
- [x] Adopt [explicit preprocessing in new Lab artifacts](LAB_EVALUATION_POLICY.md):
      metric schema 3, policy-bearing failure/report lineage, mixed-policy
      rejection and exact historical report/event byte preservation. No tracker
      change, rewritten receipt or new C++ port.
- [ ] Produce one fixed comparison and reproducible, visually understandable
      report. Retain negative results; one clip is not a general accuracy claim.
- [ ] Review it with an interested practitioner if available; record workflow
      feedback without calling it a validated partnership or product demand.

Follow the [daily/weekly delivery checkpoints](WEEKLY_DELIVERY_PLAN.md). The owner
clarified that substantive evidence takes priority over demonstrations. The
weekly baseline/annotation-diagnosis target is now met;
presentation and owner teaching are not prerequisites or accuracy evidence.
Evaluator alignment, independent case preprocessing, corrected coverage and the
extended same-event trace are complete. The Lab now explicitly versions new
filtering policies while preserving old artifacts. The **36–57** source images
and private staged review are now available, with a preliminary overlapping-figure
interpretation. The delegated AI review now records an exploratory case note and
reasoned no-change recommendation. Independent human/reference validation and
the final independently validated case study remain; no speculative comparison
is required merely to keep work moving.
The earlier saved prefix is now checked as well: 19 first becomes public at 3
and supports 85, not 89, through 35. Earlier pixels remain unviewed; no tracker
intervention follows automatically from rectangle overlap.
The real MOT-file loading/preprocessing/metric chain is now checked as well;
that completes a measurement gap, not the independent visual-review gate.
No new C++ port is required; owner recording was not needed for these checks.

## Deferred research compute

- [ ] Run the SportsMOT real-detector pass only with suitable GPU compute and a
      pre-registered evaluation protocol.
- [ ] Do not restart the expensive DanceTrack YOLOX-X comparison unless model
      capacity and input resolution can be separated cleanly.

## Completion rule

Finish and verify one focus before moving to the next. New tracker behavior is
developed and evaluated here before any performance-relevant stable subset is
considered for the C++ sibling.
