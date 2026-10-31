# Releasing VisionTrack to PyPI

The package is publish-ready: metadata, a console entry point (`visiontrack`),
optional extras, and a build that produces a valid sdist + wheel
(`python -m build`). Publishing is automated on a version tag.

## One-time setup

1. **Name** — the plain `visiontrack` is already taken on PyPI by an unrelated
   project, so the distribution is published as **`visiontrack-mot`**
   (`project.name` in `pyproject.toml`; the import package stays `visiontrack`).
   Nothing to do here unless you want a different available name.
2. **Configure Trusted Publishing** (no API token needed): create the PyPI
   project **`visiontrack-mot`** (it's created on first publish, or reserve it),
   then in its *Publishing* settings add a trusted publisher for
   repo `hulagerushikesh/visiontrack`, workflow `release.yml`, environment `pypi`.
   (Do the same on TestPyPI first if you want a dry run.)

## Cut a release

`0.3.0` is already published; its [notes](RELEASE_NOTES_0.3.0.md) are historical.
The next [0.4.0 scope](RELEASE_NOTES_0.4.0.md) is frozen, with candidate metadata
prepared but unpublished. Complete the current [readiness gates](RELEASE_READINESS.md).
Freezing scope or checking a
local artifact does not authorize a version bump or tag by itself. Replace
`X.Y.Z` below with that chosen version; never reuse an existing release tag.

```bash
# 1. bump the version in BOTH places (they must match):
#    - pyproject.toml  [project] version
#    - src/visiontrack/__init__.py  __version__
# 2. commit, then tag and push the tag:
git commit -am "release: vX.Y.Z"
git tag vX.Y.Z
git push origin main vX.Y.Z
```

Pushing the `v*` tag triggers [`.github/workflows/release.yml`](https://github.com/hulagerushikesh/visiontrack/blob/main/.github/workflows/release.yml),
which builds the distributions, runs `twine check`, verifies both exact
distributions in clean installations, and publishes to PyPI via OIDC. Watch
the Actions tab and verify the published version and artifacts afterward.

Before building, `scripts/check_release.py` requires a stable `vX.Y.Z` tag
matching both version declarations, version-specific notes, the checked-out
GitHub SHA and the newest successful **main-push CI** run for that exact commit.
A branch-based manual dispatch is refused. Dispatching on a valid tag can
publish; it is not a dry run. If CI is still pending or a newer run failed,
resolve it and retry the release workflow after CI succeeds. The read-only
GitHub Actions token needs `actions: read`; a network/API failure blocks release.
Use the installed-delivery command below for a non-publishing rehearsal.

## Check installed delivery

From a current source checkout, using a Python with pip available:

```bash
python -m pip install build twine
# Use a new output path; all retained files and environments are local.
python scripts/check_installed_package.py --output ../visiontrack-install-check
```

This builds both distributions and installs each into a separate virtual
environment outside the checkout's import path, first with core dependencies
and then the Lab extra. It verifies the real console entry point, guided demo,
read-only initiation replay, exact installed source and report/trace agreement.
It writes `receipt.json` only after all checks pass; failed runs remain available
for inspection. An existing output directory is refused. Package dependencies
and build tools are downloaded; no videos, detectors or datasets are downloaded.

After `npm ci`, add `--with-web-contract` to run the existing Python-to-TypeScript
initiation workflow against each installed environment. This is the normal CI
gate, not an interactive browser test. For an already built release pair, pass
`--dist-dir dist`; exactly one wheel and one `.tar.gz` source archive are required.
The release workflow checks that exact pair before uploading it for publication.
Normal CI and this command do not publish anything or change version declarations.

## Manual fallback

```bash
python -m build
python -m twine upload dist/*        # prompts for a PyPI token
```

## Notes

- Models and dataset caches are gitignored and are **not** shipped in the sdist/
  wheel — the package is code-only (the from-scratch core + optional extras).
- `dist/` and `build/` are gitignored; the workflow rebuilds from a clean tree.
