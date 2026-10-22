"""Development export CLI and shared report mechanics for frozen traffic grids.

Requires a committed, clean harness. Writes a new external bundle only; never
overwrites a prior attempt. Failure preserves an audit trail and stops the grid.
"""

from __future__ import annotations

import argparse
import hashlib
import math
import subprocess
import sys
from numbers import Real
from pathlib import Path

from experiments.traffic_protocol import ROOT, load_frozen_protocol
from experiments.traffic_runner import _git, _json_bytes, run_development
from experiments.traffic_scene import generate_scene

CROSSING_METRICS = (
    "truth_count",
    "predicted_count",
    "matched_count",
    "missed_events",
    "extra_events",
    "event_error",
    "recall",
    "matched_time_abs_mean_frames",
    "matched_x_abs_mean_world",
    "matched_wrong_window_events",
    "window_count_abs_error",
)
TRACKING_METRICS = (
    "true_object_frames",
    "matched_object_frames",
    "missed_object_frames",
    "matched_object_frame_fraction",
    "id_switches",
    "fragmentations",
    "false_positive_rows",
)


def _sha(value: object) -> str:
    return hashlib.sha256(_json_bytes(value)).hexdigest()


def _snapshot() -> dict:
    revision = _git(ROOT, "rev-parse", "HEAD").decode().strip()
    if _git(ROOT, "status", "--porcelain", "-uno"):
        raise ValueError("commit tracked changes before exporting a traffic grid")
    sources = {}
    for path in sorted((ROOT / "experiments").glob("traffic_*.py")):
        name = str(path.relative_to(ROOT))
        current = hashlib.sha256(path.read_bytes()).hexdigest()
        if current != hashlib.sha256(_git(ROOT, "show", f"{revision}:{name}")).hexdigest():
            raise ValueError("experiment source is uncommitted or differs from HEAD")
        sources[name] = current
    return {"actual_revision": revision, "experiment_sha256": sources}


def _cases(spec: dict) -> list[tuple[str, int, str]]:
    return _split_cases(spec, "development")


def _split_cases(spec: dict, split: str) -> list[tuple[str, int, str]]:
    if split not in {"development", "heldout"}:
        raise ValueError("unknown traffic split")
    selected = spec["splits"][split]
    return [
        (scenario, seed, condition["id"])
        for scenario in selected["scenarios"]
        for seed in selected["seeds"]
        for condition in spec["conditions"]
    ]


def _key(record: dict, split: str = "development") -> tuple[str, int, str]:
    scene = record["input"]
    if scene["split"] != split:
        raise ValueError(f"non-{split} record")
    return scene["scenario"], scene["seed"], scene["condition"]


def _metrics(record: dict) -> dict:
    """Fixed report endpoints; all other diagnostics remain in each raw record."""
    values = {}
    for anchor in ("bottom_centre", "box_centre"):
        for name in CROSSING_METRICS:
            values[f"crossing.{anchor}.{name}"] = record["crossing"][anchor]["summary"][name]
    overall = record["diagnostics"]["overall"]
    for name in TRACKING_METRICS:
        values[f"tracking.{name}"] = overall[name]
    for name in ("observation_contact_error", "matched_track_contact_error"):
        for anchor in ("bottom_centre", "box_centre"):
            for metric in ("sample_count", "mean_distance_world"):
                values[f"tracking.{name}.{anchor}.{metric}"] = overall[name][anchor][metric]
    for value in values.values():
        if value is not None and (
            isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value)
        ):
            raise ValueError("report endpoints must be finite numbers or null")
    return values


def _contrast(parts: list[tuple[int, dict]]) -> dict:
    names = set(parts[0][1])
    if any(set(values) != names for _, values in parts):
        raise ValueError("inconsistent endpoint fields")
    return {
        name: None
        if any(values[name] is None for _, values in parts)
        else sum(sign * values[name] for sign, values in parts)
        for name in sorted(names)
    }


def _descriptive(vectors: list[dict]) -> dict:
    return {
        name: {
            "defined_seeds": len(defined),
            "undefined_seeds": len(vectors) - len(defined),
            "mean": math.fsum(defined) / len(defined) if defined else None,
            "min": min(defined) if defined else None,
            "max": max(defined) if defined else None,
        }
        for name in sorted(vectors[0])
        for defined in [[vector[name] for vector in vectors if vector[name] is not None]]
    }


def summarize_development(records: list[dict]) -> dict:
    """All registered cases or failure, no filtering/imputation/ranking/p-values."""
    return _summarize(records, split="development")


def _summarize(records: list[dict], *, split: str) -> dict:
    spec, hashes = load_frozen_protocol()
    expected = _cases(spec) if split == "development" else _split_cases(spec, split)
    indexed, inputs = {}, {}
    for record in records:
        key = _key(record, split)
        if key not in expected or key in indexed:
            raise ValueError(f"unexpected or duplicate {split} record")
        if record["protocol_id"] != spec["protocol_id"] or record["protocol_hashes"] != hashes:
            raise ValueError("inconsistent report protocol")
        indexed[key] = _metrics(record)
        inputs[key] = record["input"]
    if set(indexed) != set(expected):
        raise ValueError(f"complete registered {split} grid required")
    scenes = []
    for scenario in spec["splits"][split]["scenarios"]:
        pairs = []
        for seed in spec["splits"][split]["seeds"]:
            absolute = {c["id"]: indexed[(scenario, seed, c["id"])] for c in spec["conditions"]}
            paired_inputs = {c["id"]: inputs[(scenario, seed, c["id"])] for c in spec["conditions"]}
            control_inputs = paired_inputs["control"]["sha256"]
            if any(
                p["sha256"][name] != control_inputs[name]
                for p in paired_inputs.values()
                for name in ("world_truth", "random_draws")
            ):
                raise ValueError("paired conditions must share truth and random draws")
            for first, second in (("control", "box_error_only"), ("perspective_only", "combined")):
                if (
                    paired_inputs[first]["sha256"]["ideal_truth"]
                    != paired_inputs[second]["sha256"]["ideal_truth"]
                ):
                    raise ValueError("same-projection conditions must share ideal truth")
            control = absolute["control"]
            differences = {
                name: _contrast([(1, values), (-1, control)])
                for name, values in absolute.items()
                if name != "control"
            }
            interaction = _contrast(
                [
                    (1, absolute["combined"]),
                    (-1, absolute["perspective_only"]),
                    (-1, absolute["box_error_only"]),
                    (1, control),
                ]
            )
            pairs.append(
                {
                    "seed": seed,
                    "absolute": absolute,
                    "difference_from_control": differences,
                    "interaction": interaction,
                }
            )
        scenes.append(
            {
                "scenario": scenario,
                "seeds": pairs,
                "absolute": {
                    c["id"]: _descriptive([p["absolute"][c["id"]] for p in pairs])
                    for c in spec["conditions"]
                },
                "difference_from_control": {
                    c["id"]: _descriptive([p["difference_from_control"][c["id"]] for p in pairs])
                    for c in spec["conditions"]
                    if c["id"] != "control"
                },
                "interaction": _descriptive([p["interaction"] for p in pairs]),
            }
        )
    return {
        "format": f"visiontrack.traffic-{split}-summary/v1",
        "protocol_id": spec["protocol_id"],
        "protocol_hashes": hashes,
        "run_count": len(records),
        "scenario_count": len(scenes),
        "scenarios": scenes,
        "complete_development_grid": split == "development",
        "complete_heldout_grid": split == "heldout",
        "complete_study_report": False,
        "heldout_tracking_executed": split == "heldout",
        "limitations": [
            f"Synthetic {split} characterization, not improvement or traffic validation.",
            "Each scenario is the unit; seeds repeat measurement noise, not independent scenes.",
            "No frame/seed p-values, confidence intervals, pooled site claims or automatic winner.",
            "Null components make contrasts undefined; means state their defined counts.",
            "Interaction is combined - perspective_only - box_error_only + control.",
            "Conditional localization must be read with its sample counts and completeness.",
            "All region/pulse strata, signed errors and failures remain in the full run records.",
        ],
    }


def _validate_record(
    record: dict, planned: dict, source: dict, spec: dict, hashes: dict, *, split="development"
) -> None:
    copy = dict(record)
    digest = copy.pop("record_sha256")
    if _sha(copy) != digest or record["input"] != planned:
        raise ValueError("run record or planned input digest mismatch")
    actual = record["source"]
    if (
        actual["tracked_worktree_dirty"]
        or actual["actual_revision"] != source["actual_revision"]
        or actual["experiment_sha256"] != source["experiment_sha256"]
        or actual["baseline"]["revision"] != spec["baseline_revision"]
    ):
        raise ValueError("run source provenance changed")
    if (
        record["config"] != spec["tracker_config"]
        or record["protocol_hashes"] != hashes
        or record["protocol_id"] != spec["protocol_id"]
        or record["heldout_tracking_executed"] is not (split == "heldout")
        or record["config_sha256"] != _sha(spec["tracker_config"])
        or record["output_sha256"] != _sha(record["output"])
        or record["diagnostics"]["input_sha256"] != planned["input_sha256"]
        or record["replay"]
        != {
            "passes": 3,
            "reset_equal": True,
            "fresh_equal": True,
            "updates_per_pass": spec["frame_grid"]["frames"],
        }
    ):
        raise ValueError("inconsistent run evidence")


def _markdown(summary: dict) -> str:
    heldout = summary.get("heldout_tracking_executed", False)
    split = "heldout" if heldout else "development"
    lines = [
        f"# Traffic mechanism — complete {split} grid",
        "",
        "Synthetic failure characterization only. "
        + ("Held-out tracking is now opened." if heldout else "Held-out tracking is unopened."),
        "",
        "Values below are seed means [min, max], not independent-scene confidence bounds.",
        "",
        "All endpoints, paired differences, interactions and undefined counts are in summary.json.",
        "Full region/pulse strata, rows and failure evidence are in runs/. No winner is selected.",
        "",
    ]
    columns = [
        ("Crossing misses + extras", "crossing.bottom_centre.event_error"),
        ("Window count error", "crossing.bottom_centre.window_count_abs_error"),
        ("ID switches", "tracking.id_switches"),
        ("Missed object-frames", "tracking.missed_object_frames"),
        ("False-positive rows", "tracking.false_positive_rows"),
        ("Completeness", "tracking.matched_object_frame_fraction"),
    ]
    for scene in summary["scenarios"]:
        lines += [f"## {scene['scenario']}", ""]
        for title, rows in (
            ("Absolute conditions", scene["absolute"]),
            (
                "Differences from control (condition minus control)",
                scene["difference_from_control"],
            ),
            (
                "Interaction (combined - perspective - box error + control)",
                {"interaction": scene["interaction"]},
            ),
        ):
            lines += [
                f"### {title}",
                "",
                "| Condition | " + " | ".join(title for title, _ in columns) + " |",
                "| --- | " + " | ".join("---" for _ in columns) + " |",
            ]
            for name, values in rows.items():
                cells = [
                    (
                        f"{values[key]['mean']:.6g} [{values[key]['min']:.6g}, "
                        f"{values[key]['max']:.6g}]"
                    )
                    if values[key]["mean"] is not None
                    else "undefined"
                    for _, key in columns
                ]
                lines.append(f"| {name} | " + " | ".join(cells) + " |")
            lines.append("")
    lines += ["## Limits", "", *[f"- {line}" for line in summary["limitations"]], ""]
    return "\n".join(lines)


def export_development(output: Path, *, progress=None) -> dict:
    """Write a fresh external attempt; stop and retain the ledger on any error."""
    return _export_grid(
        output,
        split="development",
        runner=run_development,
        summarize=summarize_development,
        progress=progress,
    )


def _export_grid(
    output: Path,
    *,
    split: str,
    runner,
    summarize,
    progress=None,
    preflight=None,
    before_runs=None,
    freeze_sha256=None,
    freeze_revision=None,
) -> dict:
    """Shared mechanics; held-out callers must provide the separate freeze gate."""
    if split not in {"development", "heldout"} or (
        split == "heldout"
        and any(x is None for x in (preflight, before_runs, freeze_sha256, freeze_revision))
    ):
        raise ValueError("held-out export requires a freeze and one-pass gate")
    spec, hashes = load_frozen_protocol()
    source = _snapshot()
    cases = _cases(spec) if split == "development" else _split_cases(spec, split)
    planned = [
        generate_scene(split=split, scenario=s, seed=n, condition=c).manifest() for s, n, c in cases
    ]
    if preflight is not None:
        preflight(source, planned)
    output = Path(output).resolve()
    if output.is_relative_to(ROOT.resolve()):
        raise ValueError("export results outside the repository")
    output.mkdir(exist_ok=False)
    files = {}

    def write(name: str, data: bytes) -> None:
        path = output / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream:
            stream.write(data)
        files[name] = hashlib.sha256(data).hexdigest()

    write(
        "plan.json",
        _json_bytes(
            {
                "format": f"visiontrack.traffic-{split}-plan/v1",
                "protocol_id": spec["protocol_id"],
                "protocol_hashes": hashes,
                "recipe": spec,
                "source": source,
                "inputs": planned,
                "heldout_tracking_authorized": split == "heldout",
                "freeze_sha256": freeze_sha256,
                "frozen_harness_revision": freeze_revision,
            }
        )
        + b"\n",
    )
    if before_runs is not None:
        before_runs(output)
    records, baseline, environment, error = [], None, None, None
    attempted = 0
    with (output / "attempts.jsonl").open("xb") as ledger:
        for index, ((scenario, seed, condition), inputs) in enumerate(
            zip(cases, planned, strict=True)
        ):
            selector = {"scenario": scenario, "seed": seed, "condition": condition}
            attempted += 1
            ledger.write(_json_bytes({"event": "start", **selector}) + b"\n")
            ledger.flush()
            try:
                record = runner(**selector)
                _validate_record(record, inputs, source, spec, hashes, split=split)
                if records and (
                    record["environment"] != environment or record["source"]["baseline"] != baseline
                ):
                    raise ValueError("environment/baseline changed across grid")
                baseline, environment = record["source"]["baseline"], record["environment"]
                name = f"runs/{scenario}/{seed}/{condition}.json"
                write(name, _json_bytes(record) + b"\n")
                records.append(record)
                ledger.write(
                    _json_bytes(
                        {"event": "success", **selector, "path": name, "sha256": files[name]}
                    )
                    + b"\n"
                )
                ledger.flush()
                if progress is not None:
                    progress(index + 1, len(cases))
            except Exception as exc:
                # Preserve failure, do not skip seeds, repair boxes or select a rerun.
                error = {**selector, "error_type": type(exc).__name__, "message": str(exc)[:1000]}
                ledger.write(_json_bytes({"event": "failed", **error}) + b"\n")
                ledger.flush()
                break
    files["attempts.jsonl"] = hashlib.sha256((output / "attempts.jsonl").read_bytes()).hexdigest()
    if error is None:
        try:
            if _snapshot() != source:
                raise ValueError("harness changed during grid export")
            if preflight is not None:
                preflight(source, planned)
            summary = summarize(records)
            write("summary.json", _json_bytes(summary) + b"\n")
            write("summary.md", _markdown(summary).encode())
        except Exception as exc:
            error = {"error_type": type(exc).__name__, "message": str(exc)[:1000]}
    manifest = {
        "format": f"visiontrack.traffic-{split}-bundle/v1",
        "source": source,
        "protocol_id": spec["protocol_id"],
        "protocol_hashes": hashes,
        "status": "complete" if error is None else "failed",
        "planned_runs": len(cases),
        "attempted_runs": attempted,
        "successful_runs": len(records),
        "unattempted_runs": len(cases) - attempted,
        "error": error,
        "files_sha256": files,
        "complete_study_report": False,
        "heldout_tracking_executed": split == "heldout" and attempted > 0,
        "freeze_sha256": freeze_sha256,
        "frozen_harness_revision": freeze_revision,
    }
    manifest["manifest_sha256"] = _sha(manifest)
    # Manifest authenticates its own fields separately, never lists/hash-includes itself.
    with (output / "manifest.json").open("xb") as stream:
        stream.write(_json_bytes(manifest) + b"\n")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        manifest = export_development(
            args.output,
            progress=lambda done, total: print(f"Development {done}/{total}", flush=True)
            if done % 10 == 0
            else None,
        )
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"Export refused: {exc}", file=sys.stderr)
        return 2
    print(f"{manifest['status']}: {manifest['successful_runs']}/{manifest['planned_runs']} runs")
    print(f"Bundle: {args.output.resolve()}")
    return 0 if manifest["status"] == "complete" else 2


if __name__ == "__main__":
    raise SystemExit(main())
