# Deploying the interactive demo (GitHub Pages)

The interactive demo (`viz/webdemo/index.html`) is a **single self-contained
static HTML file** — inference is pre-baked from the NumPy tracker, so there is
no build step, server, or dataset at serve time. It is published to GitHub Pages.

**Live URL:** https://hulagerushikesh.github.io/visiontrack/

## How it works

`.github/workflows/pages.yml` runs on every push that touches
`viz/webdemo/index.html` (or the workflow itself), and on manual dispatch:

1. `actions/configure-pages@v5` reads the Pages config. **One-time setup:**
   Pages must be enabled with *Settings → Pages → Build and deployment →
   Source → **GitHub Actions***. The default workflow `GITHUB_TOKEN` cannot
   *create* a Pages site (that is an admin action — attempting it fails with
   `Resource not accessible by integration`), so this first toggle is manual.
   After it, every push redeploys automatically with no further manual steps.
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

Before the first deploy, enable Pages once (*Settings → Pages → Source →
GitHub Actions*). Then re-run the workflow from the Actions tab (or push any
change to `viz/webdemo/index.html`). Subsequent deploys need no manual step.
