# VisionTrack release-readiness audit

Audit date: 2026-10-06  
Audited revision: `8d4266d100be35cd20a31b1f6522a57c0da198df`  
Published package: `visiontrack-mot 0.2.0`

## Result

The repository is healthy and reproducible, but the work after `v0.2.0` should
not be described as released yet. The tracker, Reliability Lab, React site,
browser contracts, documentation build, and Python distribution all pass their
local gates. The next package should be a deliberate `0.3.0` candidate because
it contains a substantial new Reliability Lab surface rather than a patch.

No release tag was created by this audit.

## Verified gates

- [x] `main` equals `origin/main`; the working tree was clean at audit start.
- [x] 560 active Python tests pass; one slow, data-dependent test remains opt-in.
- [x] Ruff passes over the shipped Python, tests, experiments, and data tools.
- [x] Decision, playback, browser-workflow, benchmark, and live-tracker browser
      contracts pass.
- [x] TypeScript type checking and the production Vite build pass.
- [x] MkDocs builds successfully. Existing warnings are repository-source links
      that MkDocs cannot resolve as documentation pages, not missing source files.
- [x] The `0.2.0` sdist and universal wheel rebuild locally and pass `twine check`.
- [x] The latest GitHub CI run for the audited revision is green.

## Release blockers and follow-ups

- [ ] Choose the exact `0.3.0` scope and write user-facing release notes.
- [ ] Update the package version only after the scope is frozen.
- [ ] Remove the setuptools license-table/classifier deprecation before its
      2027 enforcement date; it is a warning, not a current build failure.
- [ ] Decide whether to make the current MkDocs repository-link warnings strict
      or suppress them intentionally. They do not block the current site build.
- [ ] Run the tag-triggered GitHub release workflow and verify the public PyPI
      artifact after the remaining scope, version, and release-note gates close.

## Scope boundary

At audit time, the Python and C++ packages did not yet consume one shared
fixture. That blocker is now closed: both public trackers consume the canonical
`visiontrack.tracker-parity/v1` fixture in normal CI, and VisionTrack C++ commit
`b8bc1b1` records strict machine-readable provenance for both implementation
revisions, the fixture digest, successful CI runs, and the exact local
reproduction environment. The remaining release hold is product scope and
release communication, not cross-runtime correctness infrastructure.
