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
- [ ] Add an evidence-aware comparison summary with dataset-independent run
      diagnostics and explicit `insufficient_evidence` results for GT metrics.
- [ ] Migrate the long-form research write-up into reusable article components.
- [ ] Design a data-driven benchmark explorer before replacing generated reports.
- [ ] Port the interactive tracker shell without changing tracker behavior or
      browser privacy guarantees.
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
