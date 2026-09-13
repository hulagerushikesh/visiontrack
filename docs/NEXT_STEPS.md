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
- [ ] Add a NumPy-versus-C++ parity capstone.
- [ ] Complete mobile, keyboard, contrast, and reduced-motion QA.

The detailed curriculum plan is in
[`LEARNING_PRODUCT_PLAN.md`](LEARNING_PRODUCT_PLAN.md).

## Next focus — H3.3 product direction

- [ ] Choose one initial vertical: retail footfall, sports, or traffic.
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
