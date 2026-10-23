# VisionTrack — next-step checklist

VisionTrack is the NumPy reference, research platform, and learning product.
Work here must protect readability, reproducibility, and the ability to explain
why a tracking change helps or hurts.

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
- [ ] Run and independently audit all 120 development pairs from the committed
      harness without tuning the candidate, margins or case selection.
- [ ] Build/freeze the separate new held-out gate before its first opening;
      retain one complete grid or stop with partial evidence, never selective retries.
- [ ] Independently audit and report combined results, preserving failure,
      no-effect and inconclusive outcomes, not just an average gain.
- [ ] Validate any transfer claim on representative rights-reviewed evidence.

## Deferred research compute

- [ ] Run the SportsMOT real-detector pass only with suitable GPU compute and a
      pre-registered evaluation protocol.
- [ ] Do not restart the expensive DanceTrack YOLOX-X comparison unless model
      capacity and input resolution can be separated cleanly.

## Completion rule

Finish and verify one focus before moving to the next. New tracker behavior is
developed and evaluated here before any performance-relevant stable subset is
considered for the C++ sibling.
