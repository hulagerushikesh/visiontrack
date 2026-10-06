# VisionTrack release-readiness audit

- Audit date: 2026-10-06
- Baseline audit revision: `8d4266d100be35cd20a31b1f6522a57c0da198df`
- Released revision: `850e1b8d3b88173ecf48e71f04a2268b7584fb05`
- Published package: `visiontrack-mot 0.3.0`

## Result

VisionTrack `0.3.0` is released. The tracker, Reliability Lab, React site,
browser contracts, documentation build, and Python distribution passed their
local and hosted gates before `v0.3.0` was created. The tag-triggered workflow
built and published through PyPI trusted publishing, and both the public PyPI
artifacts and GitHub Release record were verified afterward.

## Verified gates

- [x] `main` equals `origin/main`; the working tree was clean at audit start.
- [x] The complete active Python suite passes; one slow, data-dependent test remains opt-in.
- [x] Ruff passes over the shipped Python, tests, experiments, and data tools.
- [x] Decision, playback, browser-workflow, benchmark, and live-tracker browser
      contracts pass.
- [x] TypeScript type checking and the production Vite build pass.
- [x] MkDocs builds successfully in strict mode. Repository source and evidence
      references are explicit GitHub/raw URLs, while local documentation links
      remain checked; there is no missing-link warning allowlist.
- [x] The `0.3.0` candidate sdist and universal wheel rebuild locally, pass
      `twine check`, install in a clean environment, and report matching package
      and import versions through a successful CLI smoke test.
- [x] The latest GitHub CI run for the audited revision is green.

## Release blockers and follow-ups

- [x] Freeze the exact `0.3.0` scope and write user-facing release notes in
      [`RELEASE_NOTES_0.3.0.md`](RELEASE_NOTES_0.3.0.md).
- [x] Update both package version declarations to `0.3.0` after freezing scope.
- [x] Replace the deprecated setuptools license table and classifier with an
      SPDX expression plus an explicit license file on `setuptools>=77`.
- [x] Make `mkdocs build --strict` the documentation release gate by converting
      repository source/evidence references to explicit external URLs.
- [x] Replace Node 20-era CI/release action majors with their current official
      Node 24-compatible majors and enforce the versions in the test suite.
- [x] Run the tag-triggered workflow and verify the public PyPI wheel, sdist,
      metadata, digests, digital attestations, and GitHub Release record.

## Scope boundary

At audit time, the Python and C++ packages did not yet consume one shared
fixture. That blocker is now closed: both public trackers consume the canonical
`visiontrack.tracker-parity/v1` fixture in normal CI, and VisionTrack C++ commit
`b8bc1b1` records strict machine-readable provenance for both implementation
revisions, the fixture digest, successful CI runs, and the exact local
reproduction environment. Product scope and release communication are also now
closed by the frozen release notes. The version, packaging cleanup, local and
hosted gates, tag, GitHub Release, and PyPI publication are now closed.
