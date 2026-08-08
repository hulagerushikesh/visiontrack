"""Render a BenchmarkReport to a self-contained, theme-aware HTML page."""
from __future__ import annotations

import html

_CSS = """
:root{--bg:#f4f7fb;--surface:#fff;--surface2:#f0f3f8;--border:#dbe2ec;--ink:#0e141b;
--ink2:#33404f;--muted:#5c6773;--accent:#2f7ae5;--good:#1f9d63;--warn:#d5722a;
--mono:ui-monospace,"SF Mono",Menlo,Consolas,monospace;--sans:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
@media(prefers-color-scheme:dark){:root{--bg:#0b0e14;--surface:#141922;--surface2:#1a2029;
--border:#26303c;--ink:#e7ebf1;--ink2:#b7c0cd;--muted:#8792a1;--accent:#5aa2ff;--good:#37c07e;--warn:#e8833a}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--sans);
line-height:1.6;font-size:15px;-webkit-font-smoothing:antialiased}
.wrap{max-width:900px;margin:0 auto;padding:40px 22px 90px}
.eyebrow{font-family:var(--mono);font-size:11px;letter-spacing:.16em;text-transform:uppercase;color:var(--accent);margin:0 0 8px}
h1{font-size:27px;letter-spacing:-.02em;margin:0 0 14px}
h2{font-size:18px;letter-spacing:-.01em;margin:38px 0 6px}
.meta{font-family:var(--mono);font-size:12.5px;color:var(--muted);display:flex;gap:8px;flex-wrap:wrap;margin:0 0 6px}
.meta span{background:var(--surface2);border:1px solid var(--border);border-radius:6px;padding:3px 9px}
.note{color:var(--muted);font-size:13.5px;margin:8px 0 0}
.scroll{overflow-x:auto;border:1px solid var(--border);border-radius:12px;margin-top:12px;background:var(--surface)}
table{border-collapse:collapse;width:100%;font-size:13.5px}
th,td{padding:9px 13px;text-align:right;white-space:nowrap;border-bottom:1px solid var(--border)}
th:first-child,td:first-child{text-align:left;font-family:var(--mono);font-size:12.5px}
thead th{font-family:var(--mono);font-size:10.5px;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);background:var(--surface2)}
tbody tr:last-child td{border-bottom:none}
tr.base td:first-child{color:var(--accent);font-weight:700}
.best{background:color-mix(in srgb,var(--good) 14%,transparent);font-weight:700}
.sig{color:var(--good);font-weight:700}.neg{color:var(--warn)}
.bar{position:relative;background:var(--surface2);border:1px solid var(--border);border-radius:6px;height:22px;min-width:120px}
.bar>i{position:absolute;left:0;top:0;bottom:0;border-radius:5px;background:var(--accent);opacity:.85}
.bar.hot>i{background:var(--warn)}
.lift{font-family:var(--mono);font-weight:700}
footer{margin-top:44px;border-top:1px solid var(--border);padding-top:16px;font-family:var(--mono);font-size:12px;color:var(--muted)}
footer a{color:var(--accent);text-decoration:none}
"""


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
        f"<span>{html.escape(k)}: {html.escape(str(v))}</span>"
        for k, v in [("dataset", m["dataset"]), ("baseline", m["baseline"]),
                     ("runs/tracker", m["runs_per_tracker"]),
                     ("sequences", len(m["sequences"])), ("seeds", len(m["seeds"])),
                     ("config", m["config_hash"])]
    )

    ds = html.escape(rep.dataset)
    og_title = f"Honest MOT benchmark ({ds}) · VisionTrack"
    og_desc = (f"A reproducible tracker leaderboard with paired significance and an "
               f"ID-switch error taxonomy, in one report — {ds}.")
    og_img = "https://visiontrack.hulage.in/assets/og-image.png"
    social = (
        f'<meta name="description" content="{og_desc}">'
        f'<meta name="theme-color" content="#0b0e14">'
        f'<meta property="og:type" content="website">'
        f'<meta property="og:site_name" content="VisionTrack">'
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
<title>MOT benchmark — {ds}</title>{social}<style>{_CSS}</style></head><body>
<div class="wrap">
<p class="eyebrow">VisionTrack · honest MOT benchmark</p>
<h1>Tracker comparison — {html.escape(rep.dataset)}</h1>
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
<footer>Reproduce: <code>python -m experiments.benchmark</code> ·
<a href="https://github.com/hulagerushikesh/visiontrack">github.com/hulagerushikesh/visiontrack</a></footer>
</div></body></html>"""
