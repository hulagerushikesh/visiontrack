# Releasing VisionTrack to PyPI

The package is publish-ready: metadata, a console entry point (`visiontrack`),
optional extras, and a build that produces a valid sdist + wheel
(`python -m build`). Publishing is automated on a version tag.

## One-time setup

1. **Check the name is free** on PyPI (`pip index versions visiontrack`, or the
   web). If taken, rename `project.name` in `pyproject.toml` (e.g.
   `visiontrack-mot`) — the import package stays `visiontrack`.
2. **Configure Trusted Publishing** (no API token needed): on the PyPI project's
   *Publishing* settings, add a trusted publisher for
   repo `hulagerushikesh/visiontrack`, workflow `release.yml`, environment `pypi`.
   (Do the same on TestPyPI first if you want a dry run.)

## Cut a release

```bash
# 1. bump the version in BOTH places (they must match):
#    - pyproject.toml  [project] version
#    - src/visiontrack/__init__.py  __version__
# 2. commit, then tag and push the tag:
git commit -am "release: v0.1.0"
git tag v0.1.0
git push origin main --tags
```

Pushing the `v*` tag triggers [`.github/workflows/release.yml`](../.github/workflows/release.yml),
which builds the distributions, runs `twine check`, and publishes to PyPI via
OIDC. Watch the Actions tab; on success `pip install visiontrack` works.

## Manual fallback

```bash
python -m build
python -m twine upload dist/*        # prompts for a PyPI token
```

## Notes

- Models and dataset caches are gitignored and are **not** shipped in the sdist/
  wheel — the package is code-only (the from-scratch core + optional extras).
- `dist/` and `build/` are gitignored; the workflow rebuilds from a clean tree.
