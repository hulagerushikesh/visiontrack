# VisionTrack — next-step checklist

VisionTrack is the NumPy reference, research platform, and learning product.
Work here must protect readability, reproducibility, and the ability to explain
why a tracking change helps or hurts.

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

## Deferred research compute

- [ ] Run the SportsMOT real-detector pass only with suitable GPU compute and a
      pre-registered evaluation protocol.
- [ ] Do not restart the expensive DanceTrack YOLOX-X comparison unless model
      capacity and input resolution can be separated cleanly.

## Completion rule

Finish and verify one focus before moving to the next. New tracker behavior is
developed and evaluated here before any performance-relevant stable subset is
considered for the C++ sibling.
