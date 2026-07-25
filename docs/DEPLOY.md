# Deploying the interactive demo (GitHub Pages)

The interactive demo (`viz/webdemo/index.html`) is a **single self-contained
static HTML file** — inference is pre-baked from the NumPy tracker, so there is
no build step, server, or dataset at serve time. It is published to GitHub Pages.

**Live URL:** https://hulagerushikesh.github.io/visiontrack/

## How it works

`.github/workflows/pages.yml` runs on every push that touches
`viz/webdemo/index.html` (or the workflow itself), and on manual dispatch:

1. `actions/configure-pages@v5` with `enablement: true` — creates the Pages
   site on the first run using the workflow's own `GITHUB_TOKEN`. No manual
   *Settings → Pages* toggle is required; the repo just needs Actions enabled
   (the default for public repos).
2. Copies `viz/webdemo/index.html` to `_site/index.html` so the demo is served
   at the site **root** (clean URL, not `/viz/webdemo/index.html`).
3. `upload-pages-artifact` + `deploy-pages` publish it.

The token is least-privilege (`pages: write`, `id-token: write`, `contents:
read`) and deploys run one-at-a-time via a `pages` concurrency group.

## Regenerating the demo before deploy

The committed `index.html` is generated from `index.template.html` +
`build_demo_data.py`:

```bash
make demo        # re-runs the tracker, re-inlines per-frame data into index.html
```

Commit the regenerated `viz/webdemo/index.html` and the push triggers a redeploy.

## First-run note

The very first workflow run both *enables* Pages and *deploys*. If a run ever
fails at the enablement step, confirm **Settings → Actions → General** allows
workflows to run, then re-dispatch the workflow — no other manual step is needed.
