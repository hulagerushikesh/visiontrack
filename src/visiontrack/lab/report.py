"""Deterministic, read-only HTML reports for verified Reliability Lab bundles."""

# ruff: noqa: E501
from __future__ import annotations

import hashlib
from html import escape
from pathlib import Path
from typing import Any

from .comparison import create_comparison_summary
from .contracts import canonical_json, sha256_json
from .runner import load_experiment_bundle
from .storage import read_evidence_manifest, read_failure_jsonl, write_report_artifacts

MAX_REPORT_EVENTS = 500
_PRIVACY_CLASSES = ("source_pixels", "redacted", "synthetic")


def _missing_media() -> dict[str, Any]:
    return {
        "status": "not_declared",
        "evidence_id": None,
        "artifact_count": 0,
        "privacy": [],
        "views": [],
        "frame_indices": [],
    }


def _event_media(
    bundle: Path, variant: str, source: Any, events: list[Any]
) -> tuple[dict[str, dict[str, Any]], dict[str, int]]:
    """Verify optional media for every event and return metadata-only summaries."""
    result = {event.event_id: _missing_media() for event in events}
    privacy_counts = {privacy: 0 for privacy in _PRIVACY_CLASSES}
    evidence_root = bundle / "runs" / variant / "evidence"
    if evidence_root.is_symlink():
        raise ValueError(f"evidence root for {variant} must be a local directory")
    if not evidence_root.exists():
        return result, privacy_counts
    if not evidence_root.is_dir():
        raise ValueError(f"evidence root for {variant} must be a local directory")
    events_by_id = {event.event_id: event for event in events}
    for event_directory in sorted(evidence_root.iterdir(), key=lambda path: path.name):
        if event_directory.is_symlink() or not event_directory.is_dir():
            raise ValueError(f"invalid evidence entry for {variant}: {event_directory.name}")
        event = events_by_id.get(event_directory.name)
        if event is None:
            raise ValueError(f"orphaned evidence event for {variant}: {event_directory.name}")
        manifest = read_evidence_manifest(
            event_directory / "manifest.json",
            source=source,
            failure=event,
        )
        for artifact in manifest.artifacts:
            privacy_counts[artifact.privacy] += 1
        result[event.event_id] = {
            "status": "available" if manifest.artifacts else "declared_empty",
            "evidence_id": manifest.evidence_id,
            "artifact_count": len(manifest.artifacts),
            "privacy": sorted({artifact.privacy for artifact in manifest.artifacts}),
            "views": sorted({artifact.view for artifact in manifest.artifacts}),
            "frame_indices": sorted({artifact.frame_index for artifact in manifest.artifacts}),
        }
    return result, privacy_counts


def build_report_model(bundle: str | Path) -> dict[str, Any]:
    """Build a content-addressed view model from a fully verified Lab bundle."""
    bundle_path = Path(bundle)
    comparison_path = bundle_path / "comparison.json"
    if not comparison_path.is_file():
        raise ValueError("comparison.json is required before report generation")

    # This recomputes and immutably compares the summary, revalidating every
    # upstream run, metric, and failure artifact before presentation.
    summary = create_comparison_summary(bundle_path)
    experiment, source, _ = load_experiment_bundle(bundle_path)
    variant_names = [variant["name"] for variant in experiment.variants]
    if set(summary["metrics"]) != set(variant_names):
        raise ValueError("verified metric artifacts are required for every report variant")
    if set(summary["failure_sets"]) != set(variant_names):
        raise ValueError("verified failure artifacts are required for every report variant")

    variants: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    privacy_counts = {privacy: 0 for privacy in _PRIVACY_CLASSES}
    for variant in experiment.variants:
        name = variant["name"]
        variants.append(
            {
                "name": name,
                "baseline": name == experiment.baseline,
                "configuration": variant,
                "run_id": summary["run_ids"][name],
                "diagnostics": summary["diagnostics"][name],
                "diagnostic_deltas": summary["deltas_vs_baseline"][name],
                "metrics": summary["metrics"][name],
                "metric_deltas": summary["metric_deltas_vs_baseline"][name],
                "failure_counts": summary["failure_counts"][name],
                "failure_set": summary["failure_sets"][name],
            }
        )
        failure_path = bundle_path / "runs" / name / "failures.jsonl"
        events = read_failure_jsonl(
            failure_path,
            frame_count=source.frame_count,
        )
        actual_failure_sha256 = hashlib.sha256(failure_path.read_bytes()).hexdigest()
        if actual_failure_sha256 != summary["failure_sets"][name]["failure_sha256"]:
            raise ValueError("failure artifact changed after comparison verification")
        media, variant_privacy_counts = _event_media(bundle_path, name, source, events)
        for privacy, count in variant_privacy_counts.items():
            privacy_counts[privacy] += count
        failures.extend(
            {"variant": name, **event.to_dict(), "media_evidence": media[event.event_id]}
            for event in events
        )

    failures.sort(
        key=lambda event: (
            event["frame_index"],
            event["event_type"],
            event["variant"],
            event["event_id"],
        )
    )
    failure_total = len(failures)
    media_summary = {
        "event_manifests": sum(
            failure["media_evidence"]["status"] != "not_declared" for failure in failures
        ),
        "image_artifacts": sum(failure["media_evidence"]["artifact_count"] for failure in failures),
        "privacy_counts": privacy_counts,
        "images_embedded": False,
    }
    failures = failures[:MAX_REPORT_EVENTS]
    content: dict[str, Any] = {
        "schema_version": 1,
        "comparison_id": summary["comparison_id"],
        "experiment": {
            "experiment_id": experiment.experiment_id,
            "created_at": experiment.created_at,
            "baseline": experiment.baseline,
            "frame_range": experiment.frame_range,
            "visiontrack_version": experiment.visiontrack_version,
            "git_revision": experiment.git_revision,
        },
        "source": {
            "source_id": source.source_id,
            "name": source.name,
            "kind": source.kind,
            "frame_count": source.frame_count,
            "width": source.width,
            "height": source.height,
            "fps": source.fps,
            "detector": source.detector,
            "detection_sha256": source.detection_sha256,
            "ground_truth_sha256": source.ground_truth_sha256,
            "video_sha256": source.video_sha256,
            "video_status": "hash_only_not_bundled"
            if source.video_sha256 is not None
            else "not_declared",
        },
        "variants": variants,
        "failures": failures,
        "failure_event_total": failure_total,
        "failure_event_displayed": len(failures),
        "failure_events_truncated": failure_total > len(failures),
        "media_evidence": media_summary,
        "decision": summary["decision"],
        "limitations": [
            "Track IDs are run-local and are not persistent person identities.",
            "Raw video and rendered frames are not embedded in this report.",
            "Variant acceptance remains an explicit human decision.",
        ],
    }
    content["report_id"] = sha256_json(content)
    return content


def _number(value: Any, *, signed: bool = False) -> str:
    if value is None:
        return "—"
    if isinstance(value, int):
        return f"{value:+d}" if signed else str(value)
    number = float(value)
    rendered = f"{number:.4f}".rstrip("0").rstrip(".")
    if signed and number > 0:
        return f"+{rendered}"
    return rendered


def _short(value: str | None) -> str:
    return "Not available" if value is None else value[:12]


def _identity_list(values: list[int]) -> str:
    return ", ".join(str(value) for value in values) if values else "—"


def render_report_html(model: dict[str, Any]) -> str:
    """Render a standalone accessible HTML document from a report model."""
    source = model["source"]
    experiment = model["experiment"]
    variants = model["variants"]
    metric_names = sorted({key for variant in variants for key in variant["metrics"]})
    failure_types = ("id_switch", "fragmentation", "miss", "false_positive")

    metric_headers = "".join(
        f'<th scope="col">{escape(variant["name"])}<br><span>value / Δ</span></th>'
        for variant in variants
    )
    metric_rows = "".join(
        "<tr>"
        f'<th scope="row">{escape(metric)}</th>'
        + "".join(
            "<td>"
            f"<strong>{escape(_number(variant['metrics'].get(metric)))}</strong>"
            f"<span>{escape(_number(variant['metric_deltas'].get(metric), signed=True))}</span>"
            "</td>"
            for variant in variants
        )
        + "</tr>"
        for metric in metric_names
    )
    failure_headers = "".join(
        f'<th scope="col">{escape(variant["name"])}</th>' for variant in variants
    )
    failure_count_rows = "".join(
        "<tr>"
        f'<th scope="row">{escape(event_type.replace("_", " ").title())}</th>'
        + "".join(
            f"<td>{variant['failure_counts'].get(event_type, 0)}</td>" for variant in variants
        )
        + "</tr>"
        for event_type in failure_types
    )

    if model["failures"]:
        event_rows = "".join(
            "<tr>"
            f'<td><span class="event-tag">{escape(event["event_type"].replace("_", " "))}</span></td>'
            f"<td>{escape(event['variant'])}</td>"
            f"<td>{event['frame_index']}</td>"
            f"<td>{escape(_identity_list(event['track_ids']))}</td>"
            f"<td>{escape(_identity_list(event['ground_truth_ids']))}</td>"
            f'<td><a href="#evidence-{event["event_id"]}">Frames '
            f"{event['evidence_frames']['start']}–{event['evidence_frames']['end'] - 1}</a></td>"
            f"<td>{escape(event['media_evidence']['status'].replace('_', ' ').title())}</td>"
            "</tr>"
            for event in model["failures"]
        )
        evidence_cards = "".join(
            f'<details id="evidence-{event["event_id"]}" class="evidence-card">'
            f"<summary>Frame {event['frame_index']} · "
            f"{escape(event['event_type'].replace('_', ' ').title())} · "
            f"{escape(event['variant'])}</summary>"
            '<div class="evidence-grid">'
            f"<p><span>Evidence range</span>{event['evidence_frames']['start']}–"
            f"{event['evidence_frames']['end'] - 1}</p>"
            f"<p><span>Track IDs</span>{escape(_identity_list(event['track_ids']))}</p>"
            f"<p><span>Ground-truth IDs</span>{escape(_identity_list(event['ground_truth_ids']))}</p>"
            f"<p><span>Event fingerprint</span><code>{event['event_id']}</code></p>"
            f"<p><span>Image evidence</span>{escape(event['media_evidence']['status'].replace('_', ' ').title())}</p>"
            f"<p><span>Local images</span>{event['media_evidence']['artifact_count']}</p>"
            f"<p><span>Privacy classes</span>{escape(', '.join(event['media_evidence']['privacy']) or '—')}</p>"
            '</div><p class="muted">Frame media is not embedded. Use this bounded range '
            "to inspect the original local source.</p></details>"
            for event in model["failures"]
        )
    else:
        event_rows = '<tr><td colspan="7">No measured failure events in this experiment.</td></tr>'
        evidence_cards = '<p class="empty">No failure evidence ranges to inspect.</p>'

    truncation = ""
    if model["failure_events_truncated"]:
        truncation = (
            '<p class="notice" role="status">Showing the first '
            f"{model['failure_event_displayed']} of {model['failure_event_total']} "
            "deterministically ordered events. The immutable JSONL files remain complete.</p>"
        )

    variant_cards = "".join(
        '<article class="variant-card">'
        f'<p class="eyebrow">{"Baseline" if variant["baseline"] else "Variant"}</p>'
        f"<h3>{escape(variant['name'])}</h3>"
        f"<p>{variant['diagnostics']['observation_count']} observations · "
        f"{variant['diagnostics']['unique_track_count']} run-local tracks</p>"
        f'<code title="Full run ID: {variant["run_id"]}">{variant["run_id"]}</code>'
        "</article>"
        for variant in variants
    )

    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; img-src data:">
  <title>VisionTrack Reliability Lab · {escape(source["name"])}</title>
  <style>
    :root{{--ink:#111827;--muted:#64748b;--line:#dbe3ef;--paper:#fff;--wash:#f5f7ff;--violet:#5546e8;--mint:#15b981}}*{{box-sizing:border-box}}html{{scroll-behavior:smooth}}body{{margin:0;background:linear-gradient(145deg,#f0f2ff 0,#fbfdff 45%,#effcf8 100%);color:var(--ink);font:16px/1.55 Inter,ui-sans-serif,system-ui,sans-serif}}a{{color:#4338ca}}a:focus-visible,summary:focus-visible{{outline:3px solid #22c55e;outline-offset:3px}}.skip{{position:absolute;left:-9999px;top:1rem}}.skip:focus{{left:1rem;z-index:2;background:#fff;padding:.7rem 1rem;border-radius:.6rem}}main{{width:min(1180px,calc(100% - 2rem));margin:0 auto;padding:3rem 0 5rem}}header{{padding:2.2rem;border:1px solid rgba(255,255,255,.9);border-radius:2rem;background:rgba(255,255,255,.8);box-shadow:0 24px 70px rgba(51,65,85,.12);backdrop-filter:blur(18px)}}.brand{{display:flex;align-items:center;gap:.75rem;font-weight:750}}.mark{{display:grid;place-items:center;width:2.5rem;height:2.5rem;border-radius:.8rem;background:#07110f;color:#70f3c2}}.eyebrow{{margin:0 0 .5rem;color:var(--violet);font:700 .75rem/1.2 ui-monospace,monospace;letter-spacing:.14em;text-transform:uppercase}}h1{{max-width:850px;margin:2.5rem 0 .8rem;font-size:clamp(2.5rem,7vw,5.5rem);line-height:.95;letter-spacing:-.06em}}header>p{{max-width:720px;color:var(--muted);font-size:1.08rem}}.status{{display:inline-flex;margin-top:1rem;padding:.55rem .8rem;border-radius:999px;background:#eef2ff;color:#4338ca;font-weight:700}}section{{margin-top:4rem}}h2{{font-size:clamp(1.6rem,3vw,2.5rem);letter-spacing:-.035em}}h3{{margin:.2rem 0;font-size:1.3rem}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:1rem}}.card,.variant-card,.evidence-card{{border:1px solid var(--line);border-radius:1.25rem;background:var(--paper);padding:1.25rem;box-shadow:0 10px 35px rgba(51,65,85,.06)}}.card span,.evidence-grid span{{display:block;color:var(--muted);font-size:.78rem;text-transform:uppercase;letter-spacing:.08em}}.card strong{{display:block;margin-top:.35rem;font-size:1.15rem}}code{{display:block;max-width:100%;overflow-wrap:anywhere;color:#475569;font:500 .72rem/1.5 ui-monospace,monospace}}.variant-card code{{margin-top:1rem}}.table-wrap{{overflow-x:auto;border:1px solid var(--line);border-radius:1.25rem;background:#fff}}table{{width:100%;border-collapse:collapse}}caption{{padding:1rem 1.2rem;text-align:left;color:var(--muted)}}th,td{{padding:.9rem 1.1rem;border-top:1px solid var(--line);text-align:left;vertical-align:top}}thead th{{border-top:0;background:#f8fafc;color:#475569;font-size:.8rem;text-transform:uppercase;letter-spacing:.06em}}th span,td span{{display:block;color:var(--muted);font-size:.78rem;font-weight:500}}td strong{{display:block}}.event-tag{{display:inline-block;padding:.25rem .55rem;border-radius:999px;background:#eef2ff;color:#4338ca;font-weight:700;text-transform:capitalize}}.notice,.empty{{padding:1rem;border-radius:1rem;background:#fff7ed;color:#9a3412}}.evidence-list{{display:grid;gap:.75rem}}details summary{{cursor:pointer;font-weight:750}}.evidence-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:1rem;margin-top:1rem}}.evidence-grid p{{margin:0}}.muted{{color:var(--muted)}}.provenance{{display:grid;grid-template-columns:minmax(130px,.3fr) 1fr;gap:.65rem 1rem}}.provenance dt{{color:var(--muted)}}.provenance dd{{margin:0;overflow-wrap:anywhere;font-family:ui-monospace,monospace;font-size:.82rem}}footer{{margin-top:4rem;padding-top:1.5rem;border-top:1px solid var(--line);color:var(--muted);font-size:.85rem}}@media(max-width:640px){{main{{width:min(100% - 1rem,1180px);padding-top:.5rem}}header{{padding:1.3rem;border-radius:1.3rem}}th,td{{padding:.75rem}}.provenance{{grid-template-columns:1fr}}}}
  </style>
</head>
<body>
  <a class="skip" href="#content">Skip to report content</a>
  <main id="content">
    <header>
      <div class="brand"><span class="mark" aria-hidden="true">◎</span>VisionTrack · Reliability Lab</div>
      <h1>Evidence before confidence.</h1>
      <p>A read-only report for <strong>{escape(source["name"])}</strong>. Every displayed result traces back to immutable detections, ground truth, run output, and metric artifacts.</p>
      <span class="status">Decision: not selected</span>
    </header>
    <section aria-labelledby="overview-heading">
      <p class="eyebrow">Experiment overview</p><h2 id="overview-heading">What was compared</h2>
      <div class="grid">
        <div class="card"><span>Source</span><strong>{escape(source["name"])}</strong><small>{escape(source["kind"])}</small></div>
        <div class="card"><span>Evaluated frames</span><strong>{experiment["frame_range"]["start"]}–{experiment["frame_range"]["end"] - 1}</strong><small>{experiment["frame_range"]["end"] - experiment["frame_range"]["start"]} frames</small></div>
        <div class="card"><span>Resolution</span><strong>{source["width"]} × {source["height"]}</strong><small>{escape(_number(source["fps"]))} fps</small></div>
        <div class="card"><span>Video evidence</span><strong>{"Hash only" if source["video_status"] == "hash_only_not_bundled" else "Not bundled"}</strong><small>Local-first privacy boundary</small></div>
      </div>
    </section>
    <section aria-labelledby="variants-heading"><p class="eyebrow">Runs</p><h2 id="variants-heading">Verified variants</h2><div class="grid">{variant_cards}</div></section>
    <section aria-labelledby="metrics-heading"><p class="eyebrow">Paired measurement</p><h2 id="metrics-heading">Tracking metrics</h2><div class="table-wrap"><table><caption>Value and delta relative to {escape(experiment["baseline"])}</caption><thead><tr><th scope="col">Metric</th>{metric_headers}</tr></thead><tbody>{metric_rows}</tbody></table></div></section>
    <section aria-labelledby="counts-heading"><p class="eyebrow">Failure taxonomy</p><h2 id="counts-heading">Measured failure counts</h2><div class="table-wrap"><table><caption>Events emitted by the same correspondence used for metrics</caption><thead><tr><th scope="col">Failure</th>{failure_headers}</tr></thead><tbody>{failure_count_rows}</tbody></table></div></section>
    <section aria-labelledby="events-heading"><p class="eyebrow">Frame-level evidence</p><h2 id="events-heading">Failure events</h2>{truncation}<div class="table-wrap"><table><caption>{model["failure_event_displayed"]} displayed events · {model["media_evidence"]["image_artifacts"]} verified local images (not embedded)</caption><thead><tr><th scope="col">Type</th><th scope="col">Variant</th><th scope="col">Frame</th><th scope="col">Tracks</th><th scope="col">Ground truth</th><th scope="col">Evidence</th><th scope="col">Media</th></tr></thead><tbody>{event_rows}</tbody></table></div></section>
    <section aria-labelledby="evidence-heading"><p class="eyebrow">Inspection ranges</p><h2 id="evidence-heading">Bounded local evidence</h2><div class="evidence-list">{evidence_cards}</div></section>
    <section aria-labelledby="provenance-heading"><p class="eyebrow">Provenance</p><h2 id="provenance-heading">Content fingerprints</h2><div class="card"><dl class="provenance"><dt>Report</dt><dd>{model["report_id"]}</dd><dt>Comparison</dt><dd>{model["comparison_id"]}</dd><dt>Experiment</dt><dd>{experiment["experiment_id"]}</dd><dt>Source</dt><dd>{source["source_id"]}</dd><dt>Detections</dt><dd>{source["detection_sha256"]}</dd><dt>Ground truth</dt><dd>{source["ground_truth_sha256"]}</dd><dt>Video</dt><dd>{escape(_short(source["video_sha256"]))}</dd></dl></div></section>
    <section aria-labelledby="limits-heading"><p class="eyebrow">Boundaries</p><h2 id="limits-heading">What this report does not claim</h2><ul>{"".join(f"<li>{escape(item)}</li>" for item in model["limitations"])}</ul></section>
    <footer>Generated deterministically by VisionTrack {escape(experiment["visiontrack_version"])} · read-only local artifact</footer>
  </main>
</body>
</html>
"""
    return html


def generate_local_report(bundle: str | Path) -> Path:
    """Generate immutable report JSON and standalone HTML; return the HTML path."""
    model = build_report_model(bundle)
    report_json = (canonical_json(model) + "\n").encode("utf-8")
    report_html = render_report_html(model).encode("utf-8")
    return write_report_artifacts(bundle, report_json=report_json, index_html=report_html)
