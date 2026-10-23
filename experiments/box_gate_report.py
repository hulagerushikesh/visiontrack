"""Verified, exclusive development export. No held-out tracker entry point.

Requires a clean committed harness, preserves partial variants and stops at the
first error. Pure numerical-rule fixtures are not research outcome evidence.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

from experiments.box_gate_decision import cases, evaluate_rules, validate_endpoints
from experiments.box_gate_protocol import ARTIFACTS, LOCK, load_registration
from experiments.box_gate_runner import _run_development
from experiments.box_gate_runner import _snapshot as replay_snapshot
from experiments.box_gate_scene import generate_inputs
from experiments.box_gate_scoring import score_development
from experiments.traffic_protocol import ROOT, load_frozen_protocol
from experiments.traffic_report import _contrast, _descriptive, _sha
from experiments.traffic_runner import (
    _check_import_origins,
    _environment,
    _git,
    _json_bytes,
    _verify_tree,
)


def _snapshot() -> dict:
    """Bind all current experiment/test sources, settings and locked recipes."""
    replay = replay_snapshot()
    if replay["worktree_dirty"]:
        raise ValueError("commit all local changes before exporting the development grid")
    names = set(replay["experiment_sha256"])
    names.update(
        str(p.relative_to(ROOT))
        for pattern in ("test_traffic_*.py", "test_box_gate_*.py")
        for p in (ROOT / "tests").glob(pattern)
    )
    names.update(
        (
            *ARTIFACTS,
            LOCK,
            "pyproject.toml",
            "experiments/__init__.py",
            "experiments/traffic_protocol_v1.json",
            "experiments/traffic_protocol_v1.sha256",
            "docs/TRAFFIC_RELIABILITY_PROTOCOL.md",
        )
    )
    digests = {}
    for name in sorted(names):
        path = ROOT / name
        if path.is_symlink() or path.stat().st_size > 1024 * 1024:
            raise ValueError("unexpected harness file")
        data = path.read_bytes()
        if data != _git(ROOT, "show", f"{replay['actual_revision']}:{name}"):
            raise ValueError("complete harness must match committed HEAD")
        digests[name] = hashlib.sha256(data).hexdigest()
    return {"replay_source": replay, "harness_sha256": digests}


def _sealed(value: dict, field: str) -> None:
    if not isinstance(value, dict):
        raise ValueError("expected a sealed record")
    payload = dict(value)
    digest = payload.pop(field, None)
    if digest != _sha(payload):
        raise ValueError(f"invalid {field}")


def _validate_pair(record: dict, scene, source: dict, baseline: dict, environment: dict) -> None:
    """Re-score saved public rows, not merely their advertised endpoint digest."""
    if scene.split != "development":
        raise ValueError("development validation requires development inputs")
    _validate_pair_core(record, scene, source, baseline, environment, score_development)


def _validate_pair_core(record, scene, source, baseline, environment, scorer) -> None:
    """Shared record checks; the caller supplies a split-guarded reference scorer."""
    spec, hashes = load_registration()
    parent, _ = load_frozen_protocol()
    _sealed(record, "record_sha256")
    if (
        record["format"] != f"visiontrack.box-gate-{scene.split}-pair/v1"
        or record["protocol_id"] != spec["protocol_id"]
        or record["protocol_hashes"] != hashes
        or _json_bytes(record["input"]) != _json_bytes(scene.manifest())
        or _json_bytes(record["source"]) != _json_bytes(source["replay_source"])
        or record["source"]["worktree_dirty"] is not False
        or _json_bytes(record["baseline_source"]) != _json_bytes(baseline)
        or _json_bytes(record["environment"]) != _json_bytes(environment)
        or record["heldout_tracking_executed"] is not (scene.split == "heldout")
        or record["complete_study_report"] is not False
        or [v["id"] for v in record["variants"]] != spec["grid"]["variant_order"]
    ):
        raise ValueError("pair input/source/environment/variant lineage mismatch")
    for variant, recipe in zip(record["variants"], spec["variants"], strict=True):
        settings = {**parent["tracker_config"], **recipe["config_patch"]}
        expected_replay = {
            "passes": 3,
            "pass_order": spec["grid"]["pass_order"],
            "updates_per_pass": parent["frame_grid"]["frames"],
            "reset_equal": True,
            "fresh_equal": True,
            "detection_receipts": [scene.detection_manifest()] * 3,
        }
        if (
            _json_bytes(variant["config"]) != _json_bytes(settings)
            or variant["config_sha256"] != _sha(settings)
            or variant["output_sha256"] != _sha(variant["output"])
            or _json_bytes(variant["replay"]) != _json_bytes(expected_replay)
        ):
            raise ValueError("variant configuration, actual input receipt or replay mismatch")
        _sealed(variant["scoring"], "scoring_sha256")
        rescored = scorer(scene, variant["output"])
        if _json_bytes(variant["scoring"]) != _json_bytes(rescored):
            raise ValueError("scoring differs from independently re-scored public rows")
        validate_endpoints(variant["scoring"]["endpoints"])
    difference = _contrast(
        [
            (1, record["variants"][1]["scoring"]["endpoints"]),
            (-1, record["variants"][0]["scoring"]["endpoints"]),
        ]
    )
    if _json_bytes(record["candidate_minus_baseline"]) != _json_bytes(difference):
        raise ValueError("paired endpoint contrast mismatch")


def _summarize(records: list[dict], planned: list[dict], spec: dict, parent: dict) -> dict:
    """Complete ordered grid only; exporter validates provenance before this."""
    return _summarize_grid(records, planned, spec, parent, split="development")


def _summarize_grid(records, planned, spec, parent, *, split: str) -> dict:
    """Shared complete-grid arithmetic, not an execution or provenance gate."""
    expected = cases(spec, parent, split)
    actual = [
        (r["input"]["scenario"], r["input"]["seed"], r["input"]["condition"]) for r in records
    ]
    if actual != expected or [r["input"] for r in records] != planned:
        raise ValueError(f"complete ordered {split} grid and planned inputs required")
    indexed = dict(zip(expected, records, strict=True))
    evidence = []
    for record in records:
        evidence.append(
            {
                "split": split,
                "scenario": record["input"]["scenario"],
                "seed": record["input"]["seed"],
                "condition": record["input"]["condition"],
                "endpoints": {v["id"]: v["scoring"]["endpoints"] for v in record["variants"]},
            }
        )
    scenarios = []
    for scenario in spec["splits"][split]["scenarios"]:
        seeds = []
        for seed in spec["splits"][split]["seeds"]:
            paired = {c["id"]: indexed[(scenario, seed, c["id"])] for c in parent["conditions"]}
            controls = paired["control"]["input"]["sha256"]
            if any(
                r["input"]["sha256"][n] != controls[n]
                for r in paired.values()
                for n in ("world_truth", "random_draws")
            ):
                raise ValueError("conditions do not share truth and random draws")
            for first, second in (("control", "box_error_only"), ("perspective_only", "combined")):
                if (
                    paired[first]["input"]["sha256"]["ideal_truth"]
                    != paired[second]["input"]["sha256"]["ideal_truth"]
                ):
                    raise ValueError("same-projection conditions differ in ideal truth")
            seeds.append(
                {
                    "seed": seed,
                    "conditions": {
                        condition: {
                            "absolute": {v["id"]: v["scoring"]["endpoints"] for v in r["variants"]},
                            "candidate_minus_baseline": r["candidate_minus_baseline"],
                        }
                        for condition, r in paired.items()
                    },
                }
            )
        scenarios.append(
            {
                "scenario": scenario,
                "seeds": seeds,
                "conditions": {
                    c["id"]: {
                        "absolute": {
                            variant: _descriptive(
                                [s["conditions"][c["id"]]["absolute"][variant] for s in seeds]
                            )
                            for variant in spec["grid"]["variant_order"]
                        },
                        "candidate_minus_baseline": _descriptive(
                            [s["conditions"][c["id"]]["candidate_minus_baseline"] for s in seeds]
                        ),
                    }
                    for c in parent["conditions"]
                },
            }
        )
    return {
        "format": f"visiontrack.box-gate-{split}-summary/v1",
        "protocol_id": spec["protocol_id"],
        "protocol_hashes": load_registration()[1],
        "paired_cases": len(records),
        "variant_runs": 2 * len(records),
        "replay_passes": 6 * len(records),
        "scenarios": scenarios,
        "numerical_rules": evaluate_rules(evidence),
        f"complete_{split}_grid": True,
        "complete_study_report": False,
        "heldout_tracking_executed": split == "heldout",
        "limitations": [
            f"{split.capitalize()} only: numerical study verdict remains inconclusive "
            "until both splits exist.",
            "Do not tune candidate, margins or selectors from these development outcomes.",
            "37 endpoints, null counts, all per-case contrasts and regressions retained; "
            "no pooled sites.",
            "Re-scoring verifies replay/metric consistency, not scientific truth "
            "or an independent implementation.",
            "Toy boxes/projection only, not real detector, traffic, privacy "
            "or production validation.",
        ],
    }


def _markdown(summary: dict) -> str:
    rules = summary["numerical_rules"]
    dev = rules["splits"][0]
    lines = [
        "# Box-gate ablation — development only",
        "",
        "120 pairs / 240 variant runs / 720 replay passes. No held-out tracking.",
        "",
        f"Study numerical classification: **{rules['classification']}** (both splits required).",
        f"Development per-case safety regressions: **{len(dev['regressions'])}**.",
        "",
        "| Scenario | Baseline IDSW/object | Gate off | Absolute reduction "
        "| Relative reduction | Both margins |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for s in dev["scenarios"]:
        relative = (
            "undefined" if s["relative_reduction"] is None else f"{s['relative_reduction']:.6g}"
        )
        lines.append(
            f"| {s['scenario']} | {s['baseline_primary']:.6g} | {s['gate_off_primary']:.6g} "
            f"| {s['absolute_reduction']:.6g} | {relative} "
            f"| {s['meets_both_improvement_margins']} |"
        )
    lines += [
        "",
        "Every regression and all 37 per-case endpoints, differences and defined/null",
        "seed counts are retained in summary.json; full rows/diagnostics are in pairs/.",
        "A lower ID-switch mean cannot excuse an individual count/FP/miss regression.",
        "",
        "## Limits",
        "",
        *[f"- {s}" for s in summary["limitations"]],
        "",
    ]
    return "\n".join(lines)


def export_development(output: Path, *, progress=None) -> dict:
    """Create a new external bundle; preserve failed/partial evidence, never retry.

    No split selector, result filtering, overwrite or held-out opening API.
    Finished variant bytes are saved before the next variant is attempted.
    """
    spec, hashes = load_registration()
    parent, _ = load_frozen_protocol()
    source, environment = _snapshot(), _environment()
    baseline = _verify_tree(ROOT, spec["baseline_revision"])
    _check_import_origins()
    selected = cases(spec, parent, "development")
    planned = [
        generate_inputs(split="development", scenario=s, seed=n, condition=c).manifest()
        for s, n, c in selected
    ]
    output = Path(output).resolve()
    if output.is_relative_to(ROOT.resolve()):
        raise ValueError("export evidence outside the repository")
    if _snapshot() != source or _environment() != environment or load_registration()[1] != hashes:
        raise ValueError("preflight changed while planning")
    output.mkdir(exist_ok=False)
    files = {}

    def write(name, data):
        path = output / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream:
            stream.write(data)
        files[name] = hashlib.sha256(data).hexdigest()

    write(
        "plan.json",
        _json_bytes(
            {
                "format": "visiontrack.box-gate-development-plan/v1",
                "protocol_id": spec["protocol_id"],
                "protocol_hashes": hashes,
                "registration": spec,
                "source": source,
                "baseline_source": baseline,
                "environment": environment,
                "inputs": planned,
                "heldout_tracking_authorized": False,
            }
        )
        + b"\n",
    )
    records, error, attempted = [], None, 0
    with (output / "attempts.jsonl").open("xb") as ledger:

        def log(event):
            ledger.write(_json_bytes(event) + b"\n")
            ledger.flush()

        for index, ((scenario, seed, condition), inputs) in enumerate(
            zip(selected, planned, strict=True)
        ):
            selector = {"scenario": scenario, "seed": seed, "condition": condition}
            prefix = f"pairs/{scenario}/{seed}/{condition}"
            attempted += 1
            log({"event": "start", **selector})
            retained = []

            def save_variant(name, data, *, retained=retained, prefix=prefix, selector=selector):
                if len(retained) >= 2 or name != spec["grid"]["variant_order"][len(retained)]:
                    raise ValueError("partial variants must follow registered order")
                path = f"{prefix}/{name}.json"
                write(path, data + b"\n")
                retained.append(name)
                log(
                    {
                        "event": "variant_retained",
                        **selector,
                        "variant": name,
                        "path": path,
                        "sha256": files[path],
                        "validated_pair": False,
                    }
                )

            try:
                if _snapshot() != source or _environment() != environment:
                    raise ValueError("harness/environment changed before pair")
                record = _run_development(**selector, variant_sink=save_variant)
                path = f"{prefix}/pair.json"
                write(path, _json_bytes(record) + b"\n")
                scene = generate_inputs(split="development", **selector)
                if scene.manifest() != inputs:
                    raise ValueError("planned inputs changed")
                _validate_pair(record, scene, source, baseline, environment)
                if retained != spec["grid"]["variant_order"] or any(
                    (output / f"{prefix}/{v['id']}.json").read_bytes() != _json_bytes(v) + b"\n"
                    for v in record["variants"]
                ):
                    raise ValueError("partial variant artifacts differ from completed pair")
                if _snapshot() != source or _environment() != environment:
                    raise ValueError("harness/environment changed during pair")
                records.append(record)
                log({"event": "success", **selector, "path": path, "sha256": files[path]})
                if progress is not None:
                    progress(index + 1, len(selected))
            except Exception as exc:
                error = {**selector, "error_type": type(exc).__name__, "message": str(exc)[:1000]}
                log({"event": "failed", **error})
                break
    files["attempts.jsonl"] = hashlib.sha256((output / "attempts.jsonl").read_bytes()).hexdigest()
    if error is None:
        try:
            if (
                _snapshot() != source
                or _environment() != environment
                or _verify_tree(ROOT, spec["baseline_revision"]) != baseline
                or load_registration()[1] != hashes
            ):
                raise ValueError("harness/baseline/registration/environment changed during grid")
            _check_import_origins()
            summary = _summarize(records, planned, spec, parent)
            write("summary.json", _json_bytes(summary) + b"\n")
            write("summary.md", _markdown(summary).encode())
            for name, digest in files.items():
                path = output / name
                if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                    raise ValueError("saved evidence changed before sealing bundle")
        except Exception as exc:
            error = {"error_type": type(exc).__name__, "message": str(exc)[:1000]}
    manifest = {
        "format": "visiontrack.box-gate-development-bundle/v1",
        "protocol_id": spec["protocol_id"],
        "protocol_hashes": hashes,
        "source": source,
        "environment": environment,
        "baseline_source": baseline,
        "status": "failed" if error else "complete",
        "planned_pairs": len(selected),
        "attempted_pairs": attempted,
        "successful_pairs": len(records),
        "unattempted_pairs": len(selected) - attempted,
        "error": error,
        "files_sha256": files,
        "heldout_tracking_executed": False,
        "complete_study_report": False,
    }
    manifest["manifest_sha256"] = _sha(manifest)
    with (output / "manifest.json").open("xb") as stream:
        stream.write(_json_bytes(manifest) + b"\n")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="new external bundle directory (must not exist)")
    args = parser.parse_args()
    manifest = export_development(
        args.output, progress=lambda n, total: print(f"Pair {n}/{total}", flush=True)
    )
    print(f"{manifest['status']}: {manifest['successful_pairs']}/{manifest['planned_pairs']} pairs")
    print(f"Bundle: {args.output.resolve()}")
    return 0 if manifest["status"] == "complete" else 2


if __name__ == "__main__":
    raise SystemExit(main())
