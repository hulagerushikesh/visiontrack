"""Render a BenchmarkReport to an HTML page that matches the hand-authored site.

The report pages are part of the deployed site (served at /benchmark…), so they
share the one site stylesheet (``/assets/site.css``) and behaviour
(``/assets/site.js``) instead of inlining their own CSS — that is the whole point
of the shared-stylesheet refactor. For a portable, dependency-free artefact use
``--out-md`` (markdown) instead.
"""
from __future__ import annotations

import html

# Shared shell: the telemetry-bar nav used verbatim across every page.
_NAV = """<nav class="site-nav">
  <div class="nav-in">
    <a class="brand" href="/"><span class="dot"></span>VisionTrack</a>
    <span class="nav-tag">honest MOT benchmark</span>
    <span class="spacer"></span>
    <div class="nav-links">
      <a href="/demo">demo</a>
      <a href="/writeup">write-up</a>
      <a href="/video" data-secondary>video</a>
      <a href="/benchmark">benchmark</a>
      <a href="/docs/" data-secondary>docs</a>
    </div>
    <button class="theme-btn" type="button">◑ dark</button>
  </div>
</nav>"""

_DATASET_TABS = """<div class="dataset-tabs">
    <a href="/benchmark">synthetic</a>
    <a href="/benchmark/dancetrack">DanceTrack</a>
    <a href="/benchmark/dancetrack-yolox">DanceTrack · YOLOX</a>
    <a href="/benchmark/sportsmot">SportsMOT</a>
  </div>"""

_FOOTER = """<footer>
  <div class="foot-in">
    <span>VisionTrack · MIT</span>
    <span class="spacer"></span>
    <a href="/">home</a>
    <a href="/writeup">write-up</a>
    <a href="/demo">demo</a>
    <a href="/docs/">docs</a>
  </div>
</footer>"""


def _route(dataset: str) -> str:
    """Map a displayed dataset name to its served route."""
    d = dataset.lower()
    # SportsMOT first: a "sportsmot (real YOLOX)" label also matches "yolox",
    # which would otherwise route it to the DanceTrack page.
    if "sportsmot" in d:
        return "/benchmark/sportsmot"
    if "yolox" in d:
        return "/benchmark/dancetrack-yolox"
    if "dancetrack" in d:
        return "/benchmark/dancetrack"
    return "/benchmark"


def _fmt_cell(mean, std, delta, p, is_base, is_best):
    star = "<span class='sig'>*</span>" if p < 0.05 else ""
    cls = " class='best'" if is_best else ""
    if is_base:
        return f"<td{cls}>{mean:.3f}±{std:.3f}</td>"
    sign = "sig" if delta > 0 else "neg"
    return f"<td{cls}>{mean:.3f} <span class='{sign}'>({delta:+.3f}{star})</span></td>"


def render_html(rep) -> str:
    m = rep.meta
    best = {mt: rep.best(mt) for mt in rep.metrics}

    head = "".join(f"<th>{html.escape(mt)}</th>" for mt in rep.metrics)
    rows = []
    for r in rep.leaderboard:
        is_base = r["name"] == rep.baseline
        cells = "".join(
            _fmt_cell(*r["summary"][mt], *r["compare"][mt], is_base, best[mt] == r["name"])
            for mt in rep.metrics
        )
        cls = " class='base'" if is_base else ""
        rows.append(f"<tr{cls}><td>{html.escape(r['name'])}</td>{cells}</tr>")

    max_lift = max((t["lift"] for t in rep.taxonomy if t["lift"] == t["lift"]), default=1.0)
    tax = []
    for t in rep.taxonomy:
        lift = t["lift"]
        pct = 0 if lift != lift else min(100, 100 * lift / max(max_lift, 1e-9))
        hot = " hot" if lift == lift and lift >= 1.5 else ""
        tax.append(
            f"<tr><td>{html.escape(t['condition'])}</td>"
            f"<td>{t['pct_switch']:.0%}</td><td>{t['pct_base']:.0%}</td>"
            f"<td class='lift'>{lift:.2f}×</td>"
            f"<td><div class='bar{hot}'><i style='width:{pct:.0f}%'></i></div></td></tr>"
        )

    meta_chips = "".join(
        f"<span>{html.escape(k)}: <b>{html.escape(str(v))}</b></span>"
        for k, v in [("dataset", m["dataset"]), ("baseline", m["baseline"]),
                     ("runs/tracker", m["runs_per_tracker"]),
                     ("sequences", len(m["sequences"])), ("seeds", len(m["seeds"])),
                     ("config", m["config_hash"])]
    )

    ds = html.escape(rep.dataset)
    route = _route(rep.dataset)
    canonical = f"https://visiontrack.hulage.in{route}"
    og_title = f"Honest MOT benchmark ({ds}) · VisionTrack"
    og_desc = (f"A reproducible tracker leaderboard with paired significance and an "
               f"ID-switch error taxonomy, in one report — {ds}.")
    og_img = "https://visiontrack.hulage.in/assets/og-image.png"
    social = (
        f'<link rel="canonical" href="{canonical}">'
        f'<meta name="description" content="{og_desc}">'
        f'<meta name="theme-color" content="#0b0e14">'
        f'<meta property="og:type" content="website">'
        f'<meta property="og:site_name" content="VisionTrack">'
        f'<meta property="og:url" content="{canonical}">'
        f'<meta property="og:title" content="{og_title}">'
        f'<meta property="og:description" content="{og_desc}">'
        f'<meta property="og:image" content="{og_img}">'
        f'<meta property="og:image:width" content="1200">'
        f'<meta property="og:image:height" content="630">'
        f'<meta name="twitter:card" content="summary_large_image">'
        f'<meta name="twitter:title" content="{og_title}">'
        f'<meta name="twitter:description" content="{og_desc}">'
        f'<meta name="twitter:image" content="{og_img}">'
    )
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>MOT benchmark — {ds} · VisionTrack</title>{social}
<link rel="stylesheet" href="/assets/site.css">
<script defer src="/assets/site.js"></script></head><body>
{_NAV}
<main class="wrap benchmark-page">
<p class="eyebrow">VisionTrack · honest MOT benchmark</p>
<h1>Tracker comparison — {html.escape(rep.dataset)}</h1>
{_DATASET_TABS}
<div class="meta">{meta_chips}</div>
<p class="note">Every tracker sees identical detections and seeds, so Δ vs the
baseline is a paired comparison (Wilcoxon <span class="sig">*</span> = p&lt;0.05).
🏆-highlighted cell = best tracker for that metric.</p>
<h2>Leaderboard</h2>
<div class="scroll"><table><thead><tr><th>tracker</th>{head}</tr></thead><tbody>{''.join(rows)}</tbody></table></div>
<h2>Why <code>{html.escape(rep.baseline)}</code> swaps identities</h2>
<p class="note">{m['idsw_classified']} ID switches classified by local scene
condition. <b>Lift</b> = P(condition | switch) / P(condition | any GT); &gt;1 means
switches are over-represented there — the failure mode to attack.</p>
<div class="scroll"><table><thead><tr><th>condition</th><th>% of switches</th>
<th>base rate</th><th>lift</th><th>over-representation</th></tr></thead>
<tbody>{''.join(tax)}</tbody></table></div>
<p class="note" style="margin-top:22px">Reproduce: <code>python -m experiments.benchmark</code></p>
</main>
{_FOOTER}
</body></html>"""
