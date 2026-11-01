# VisionTrack release-readiness audit

## Candidate 0.5.1 — 2026-11-02

The [patch scope](RELEASE_NOTES_0.5.1.md) packages the existing streaming replay
and unambiguous persisted-JSON reader corrections. Candidate metadata identifies
0.5.1; no publication or tag is authorized by preparation. Public 0.5.0 and all
historical evidence below remain unchanged. Candidate-specific gate results are
recorded in the patch notes, separately from the earlier implementation checks.

## Published 0.5.0 verification — 2026-11-01

The [0.5.0 scope](RELEASE_NOTES_0.5.0.md) is frozen around the selected-pair
diagnostic. With explicit owner approval, `v0.5.0` was published from
`324c9135989537448b07244c982f246d39295399`. Its
[seven-job exact-commit CI](https://github.com/hulagerushikesh/visiontrack/actions/runs/41325567170)
and [trusted-publishing workflow](https://github.com/hulagerushikesh/visiontrack/actions/runs/41325995049)
pass. [PyPI 0.5.0](https://pypi.org/project/visiontrack-mot/0.5.0/) and the
[GitHub release](https://github.com/hulagerushikesh/visiontrack/releases/tag/v0.5.0)
are verified. This closes an installable-delivery gap, not the representative
traffic research gate. Older tags, artifacts and evidence remain unchanged.

- [x] Project/import metadata agree at 0.5.0; historical 0.3.0/0.4.0 evidence and
      both prepared lesson asset sets remain unchanged.
- [x] Full local Python suite: **1,288 passed, 3 skipped, 1 slow test deselected**,
      including the pinned evaluator and frozen historical regression checks.
- [x] All thirteen npm contracts/workflows, private-review control check,
      TypeScript, production app, Ruff, strict docs and canonical tracker parity pass.
- [x] Wheel and source archive pass `twine check` and separate clean core/Lab
      installations outside the checkout; installed source bytes match.
- [x] Installed CLI/API association output agrees, records the candidate producer
      and actual source hashes, refuses two invalid selectors without partial
      JSON, and leaves the existing bundle/demo unchanged.
- [x] Wheel/source report, initiation trace and association explanation IDs all
      agree. Each installation's actual Python-to-TypeScript initiation and
      fourteen-case association workflows pass.
- [x] All seven hosted jobs pass for candidate `a898b74` in
      [run 41325219952](https://github.com/hulagerushikesh/visiontrack/actions/runs/41325219952).
      The read-only release guard passes in a simulated matching-tag context;
      this creates no tag. A later selected tag commit requires its own CI.
- [x] Separate publication approval, matching tag and successful publication.
- [x] Both downloaded public files match the workflow distributions and its
      isolated-install receipt byte for byte. Their PyPI provenance metadata
      identifies this repository, `release.yml`, `pypi` environment and exact
      subject digests. No offline cryptographic signature verification is claimed.
- [x] Fresh public-index installation outside the checkout: core first, then Lab
      extras, actual CLI/API replay and invalid-selector refusal, all 64 installed
      Python sources and both Python-to-TypeScript diagnostic workflows agree.
      An initial simple-index propagation delay was retained and resolved; the
      ordinary pinned install succeeds without a direct-file workaround.

| Published file | SHA-256 |
| --- | --- |
| `visiontrack_mot-0.5.0-py3-none-any.whl` | `13aa43fcf576af5c12ba97bdd88469570fe550602c9037bd3abdb3bfa64d49ad` |
| `visiontrack_mot-0.5.0.tar.gz` | `8de36a680a7206f853f1c68ebba404374e3d5b54d082f6700510375fcbecccab` |

A separate fresh macOS ARM64 / Python 3.12.9 installed candidate-wheel and
public C++ 0.1.1 pairing passes all 279 tests with no skips and 35,387 exact
observations over 2,625 cached frames using NumPy 2.2.6. Its SciPy 1.15.3 test
reference failed to load locally; that first skipped run is retained, and the
complete pass uses the already working 1.16.2 reference. This is a local pairing
check, not the twelve-platform 0.4.0 matrix or accepted C++ oracle promotion.

The local receipt records artifact digests, installed versions/source identities,
all three fingerprints and explicit association/refusal checks. No C++ oracle
adoption, new accuracy result, browser QA or practitioner validation follows.

## Published 0.4.0 verification — 2026-11-01

The historical `0.3.0` publication audit below remains unchanged. The current
release adds `lab-initiation` and `lab-demo --with-initiation` in public
`visiontrack-mot 0.4.0`, tagged at `5df99d6013f15c43d3f73e62db0867c9d5fe7146`.
Historical reports and conformance fixtures retain their recorded versions.
Fresh demo/report/trace checks bind their version to the producing package.

- [x] Build the current wheel and source archive, then pass `twine check`.
- [x] Install each artifact in its own clean, non-editable Python 3.12 environment
      outside the checkout. First exercise the core CLI with NumPy only, then
      install the Lab extra without dev, plotting, inference or test dependencies.
- [x] Verify the installed import path, metadata/import version agreement and
      every installed package `.py` byte against the current package source.
- [x] Exercise actual console commands: no-write preview, guided generation in
      a path containing spaces, exact CLI/API replay, repeat-write refusal and
      unchanged bundle/demo bytes after read-only commands.
- [x] Check that wheel and source installs produce identical report and trace
      fingerprints. Verify the producer source hashes against the installed files.
- [x] Feed files generated by each installation through the existing TypeScript
      report/trace import, lifecycle, lineage and rendered-component contract.
      This does not constitute browser interaction or practitioner usability QA.
- [x] Add this clean-install check to normal CI and to the release build job
      before artifact upload/publication; retain a machine-readable receipt.
- [x] Freeze the [0.4.0 scope and migration](RELEASE_NOTES_0.4.0.md), distinguishing
      tracking behavior, corrected metric semantics, optional diagnostics and
      separately deployed website features. Both package declarations and the public
      release identify 0.4.0.
- [x] Guard publication against branch dispatch, tag/metadata mismatch and
      missing, failed or pending latest main-push CI for the exact release commit.
- [x] Prepare 0.4.0 metadata and version-dependent current fixtures without
      rewriting historical evidence or changing the tracker.
- [x] Complete local candidate gates: **1,256 Python tests pass**, 3 skip and one
      slow test is deselected, with the pinned TrackEval reference installed.
      The original 22-file regression suite also runs in its restored clone.
      Canonical Python/C++ fixture parity and deterministic reset, all web
      contracts/workflows, TypeScript, the production app, Ruff and strict docs pass.
- [x] Verify [exact-commit CI](https://github.com/hulagerushikesh/visiontrack/actions/runs/41201526847):
      all seven jobs succeed, including Python 3.10, 3.11 and 3.12.
- [x] Publish `v0.4.0` through the
      [successful trusted-publishing workflow](https://github.com/hulagerushikesh/visiontrack/actions/runs/41273860817).
- [x] Verify both PyPI files byte-for-byte against the release workflow artifacts
      and its clean-install receipt. Retain PyPI provenance records and check
      publisher repository/workflow/environment and attestation subject digests.
- [x] Install core and then Lab extras from public PyPI in a new environment
      outside the checkout. Core CLI, guided replay, every installed source hash
      and actual Python-to-Lab imports pass.
- [x] Verify the public [GitHub release](https://github.com/hulagerushikesh/visiontrack/releases/tag/v0.4.0).

| Published file | SHA-256 |
| --- | --- |
| `visiontrack_mot-0.4.0-py3-none-any.whl` | `a14d0cbbc6a233b38be32e2c2048348d42303f4c524711634cbea437c9d21495` |
| `visiontrack_mot-0.4.0.tar.gz` | `c10d7fcccc6a8c0e1da8e05304974ea744f7bc2daa014fd1b2085bc9f5f32a38` |

The tag and public package files are unchanged by this post-publication audit.
The README embedded in those immutable files retains pre-publication source-only
setup wording. The commands are present and verified in public 0.4.0; use the
corrected [five-minute guide](SHOWCASE_DEMO.md) and current Lab instructions.
Corrected embedded README wording will accompany a future package release.
Website deployment, browser interaction QA and practitioner usability are separate
checks; publication does not establish tracking accuracy.

Reproduce with the command in [Release to PyPI](RELEASE.md#check-installed-delivery).
The rewritten main history exposed a fresh-checkout regression: three tests
needed original commit objects that no longer arrived with a clone. A sealed
archive now retains 221 original commit headers (no alternate source/results).
Their original Git identities are verified; all referenced source trees already
exist unchanged in current main. Only a disposable regression clone restores
those objects and executes the exact 22-file historical suite. The legacy
preprocessing/body and current-source-drift tests use the same original tree
identities. No study record, source lock, result or default is rewritten.
A transport clone excludes unreachable local objects, exercising the CI failure
condition rather than relying on leftovers in the developer checkout.

The previous [main CI](https://github.com/hulagerushikesh/visiontrack/actions/runs/41188547359)
failed those historical-reference tests; its install/web checks passed. Older CI
success at another SHA does not substitute for CI on this candidate revision.
The receipt records artifact digests, installed source hashes, report/trace IDs,
core checks and whether the TypeScript contract was run. It contains local
installation paths and stays local or in the CI artifact; it is not a dataset,
tracking-accuracy result, digital signature or release authorization.

## Historical 0.3.0 publication audit

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
