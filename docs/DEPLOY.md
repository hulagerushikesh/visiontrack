# Deploying the site (Vercel + custom subdomain)

The public site is a **static bundle** — a landing hub plus three self-contained
HTML pages (interactive demo, study guide, CV roadmap). There is no build step,
server, or dataset at serve time. It is hosted on **Vercel** at a custom
subdomain of `hulage.in`.

**Live URL:** https://visiontrack.hulage.in

## What gets deployed

| Route | Serves | Source file |
|-------|--------|-------------|
| `/` | Landing hub | `web/index.html` |
| `/demo` | Interactive tracker demo | `viz/webdemo/index.html` |
| `/study` | VisionTrack study guide | `docs/LEARNING_PATH.html` |
| `/roadmap` | CV junior→research roadmap | `docs/CV_ROADMAP.html` |

Both the build and routing are defined in [`vercel.json`](../vercel.json). It uses
an explicit `builds` list (`@vercel/static` for exactly the five static entries
above) plus `routes` for the clean URLs. Declaring `builds` **disables Vercel's
zero-config auto-detection** — without it, Vercel sees `pyproject.toml` and wrongly
tries the Python builder (`No python entrypoint found`). With it, only the static
files are deployed; the Python project is ignored.

## One-time setup (in the Vercel dashboard)

1. Sign in to **vercel.com** with GitHub.
2. **Add New → Project** → import `hulagerushikesh/visiontrack`.
3. On the import screen:
   - **Framework Preset:** `Other`
   - **Build Command:** leave empty
   - **Output Directory:** leave empty (serves the repo root)
   - **Root Directory:** `.`
4. **Deploy.** The project goes live on a `*.vercel.app` URL first.

## Attaching the subdomain

1. Project → **Settings → Domains** → add `visiontrack.hulage.in`.
2. Vercel shows a DNS record to create. For a subdomain it is a **CNAME**:

   | Type | Name | Value |
   |------|------|-------|
   | CNAME | `visiontrack` | `cname.vercel-dns.com` |

3. Add that CNAME in the DNS provider that manages `hulage.in`. This only
   touches the `visiontrack` subdomain — the apex (`hulage.in`) is untouched.
4. Wait for Vercel to verify (minutes, up to ~an hour). Vercel auto-provisions
   the TLS certificate. Done.

## Ongoing

Every push to `main` triggers an automatic Vercel redeploy. To refresh the demo
content, run `make demo` (regenerates `viz/webdemo/index.html`) and push.
