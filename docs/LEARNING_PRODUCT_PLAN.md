# Horizon 3.2 — VisionTrack learning product

## Outcome

Turn the existing teaching page, project study guide, computer-vision roadmap,
and C++ guide into one coherent learning product. A learner should always know
where to start, what to study next, and which repository contains the working
implementation.

## Audience paths

1. **Curious reader** — understand detection, tracking, identity switches, and
   why the problem matters without needing code.
2. **VisionTrack builder** — trace one frame through geometry, Kalman prediction,
   assignment, lifecycle, evaluation, and the research ablations.
3. **Performance engineer** — follow the same tracker from the NumPy oracle into
   the parity-gated C++ implementation, profiling, packaging, and the GPU
   feasibility decision.

## Delivery checklist

### Milestone 1 — one front door

- [x] Group learning artifacts under `learning/` in both repositories.
- [x] Keep `/study` and `/roadmap` stable after the file moves.
- [x] Add a module library to `/teaching` with a clear audience and outcome for
      each path.
- [x] Add automated link checks for the three learning paths.

### Milestone 2 — guided progression

- [x] Give every module a short prerequisite, estimated effort, and completion
      outcome.
- [x] Add explicit “previous / next” navigation between learning stages.
- [x] Update stale lessons whose “next work” has already shipped.
- [x] Link concepts to exact source files in the NumPy and C++ repositories.

### Milestone 3 — exercises and verification

- [x] Add small exercises for geometry, Kalman filtering, assignment, and track
      lifecycle.
- [x] Provide runnable checks or expected outputs without requiring MOT datasets.
- [x] Add a final parity exercise that compares the NumPy and C++ trackers.
- [x] Keep progress local to the learner's browser; no account is required.

### Milestone 4 — release-quality course

- [x] Test the complete path on mobile and desktop.
- [x] Run an accessibility pass for keyboard navigation, focus order, contrast,
      and reduced motion.
- [ ] Add learning-product analytics only if a privacy-preserving requirement is
      explicitly chosen.
- [ ] Mark H3.2 complete when all three audience paths have a beginning, guided
      sequence, exercises, and a concrete finish.

## Guardrails

- The course teaches from the real repository; it does not duplicate source
  documentation into a second system that can drift.
- Claims remain tied to reproducible experiments and the NumPy oracle.
- The C++ path stays a sibling performance story, not a replacement for the
  readable reference implementation.
- Dataset-free exercises come first so the learning path works on an ordinary
  laptop.
