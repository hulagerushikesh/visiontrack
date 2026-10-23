"""One ordered held-out opening from an exact committed freeze, never a retry.

Private shared scoring/replay mechanics are not an authorization boundary. This
module's only public execution entry verifies the complete freeze, then claims
opening.json exclusively BEFORE invoking any tracker. No selector/configuration
override, resume, automatic retry or production adoption is exposed.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import subprocess
import sys
from pathlib import Path

from experiments import box_gate_holdout as holdout
from experiments.box_gate_decision import cases
from experiments.box_gate_protocol import load_registration
from experiments.box_gate_report import _summarize_grid, _validate_pair_core
from experiments.box_gate_runner import _run_pair
from experiments.box_gate_scene import generate_inputs
from experiments.box_gate_scoring import _score, _validated_scene
from experiments.traffic_protocol import load_frozen_protocol
from experiments.traffic_report import _sha
from experiments.traffic_runner import _json_bytes


def _score_heldout(scene, rows):
    """Private reference arithmetic; hand-fed rows do not prove tracker execution."""
    spec, hashes, parent = _validated_scene(scene, split="heldout")
    return _score(scene, rows, spec, hashes, parent)


def _markdown(summary):
    split = summary["numerical_rules"]["splits"][1]
    return "\n".join([
        "# Box-gate ablation — held-out split only", "",
        "120 pairs / 240 variants / 720 fresh/reset/fresh passes.", "",
        f"Held-out per-case safety violations: {len(split['regressions'])}.",
        "This split alone is not a complete-study verdict or acceptance.",
        "All 37 endpoints, null counts, seeds, contrasts and regressions are in summary.json.",
        "Development violations remain binding; a held-out result cannot erase them.",
        "Combined independent saved-record audit and interpretation are still required.",
        "Toy inputs only; no real-traffic accuracy or production/C++ adoption claim.", "",
    ])


def run_heldout(freeze_path: Path, output: Path, *, progress=None) -> dict:
    """Consume one freeze; retain each finished variant and stop on first error.

    An interrupted/failed opening stays consumed, including failures while
    creating its plan. Local file guards are not a global opening registry,
    malicious-runtime sandbox or a guarantee against power/storage failure.
    """
    freeze_path = holdout._external(freeze_path)
    output = holdout._external(output)
    if output.exists():
        raise FileExistsError("output already exists; never overwrite/resume a held-out run")
    freeze = holdout.verify_freeze(freeze_path)
    freeze_bytes = holdout._read(freeze_path)
    if freeze_bytes != _json_bytes(freeze) + b"\n":
        raise ValueError("freeze bytes changed after verification")
    for evidence in (freeze_path.parent, Path(freeze["development_bundle"])):
        if output.is_relative_to(evidence) or evidence.is_relative_to(output):
            raise ValueError("held-out output must be separate from freeze/development evidence")
    spec, hashes = load_registration()
    parent, _ = load_frozen_protocol()
    selected = cases(spec, parent, "heldout")
    planned = freeze["inputs"]
    if len(selected) != 120 or len(planned) != 120:
        raise ValueError("the entire registered held-out grid is required")
    state = {key: freeze[key] for key in holdout._state()}
    if _json_bytes(holdout._state()) != _json_bytes(state):
        raise ValueError("frozen state changed before opening")
    opening_path = freeze_path.parent / "opening.json"
    opening = {
        "format": "visiontrack.box-gate-heldout-opening/v1",
        "freeze_sha256": freeze["freeze_sha256"],
        "freeze_raw_sha256": hashlib.sha256(freeze_bytes).hexdigest(),
        "source_revision": state["source"]["replay_source"]["actual_revision"],
        "inputs_sha256": freeze["inputs_sha256"],
        "output": str(output), "execution_policy": holdout.POLICY,
    }
    opening["opening_sha256"] = _sha(opening)
    opening_bytes = _json_bytes(opening) + b"\n"
    # Output may be left empty if another process wins the exclusive claim.
    # Crucially no tracker, plan or case is executed before this claim succeeds.
    output.mkdir(exist_ok=False)
    with opening_path.open("xb") as stream:
        stream.write(opening_bytes)
        stream.flush()
        os.fsync(stream.fileno())

    def guard():
        if (
            holdout._read(freeze_path) != freeze_bytes
            or holdout._read(opening_path) != opening_bytes
            or _json_bytes(holdout._state()) != _json_bytes(state)
        ):
            raise ValueError("freeze, exclusive claim, code or runtime changed; stop, do not retry")

    files = {}

    def write(name, data):
        path = output / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        files[name] = hashlib.sha256(data).hexdigest()

    # Any failure here leaves the already-created claim consumed, not resumable.
    guard()
    write("plan.json", _json_bytes({
        "format": "visiontrack.box-gate-heldout-plan/v1",
        "protocol_id": spec["protocol_id"], "protocol_hashes": hashes,
        "registration": spec, "source": state["source"],
        "baseline_source": state["baseline_source"], "environment": state["environment"],
        "freeze_sha256": freeze["freeze_sha256"], "opening": opening,
        "development_evidence": freeze["development_evidence"],
        "inputs": planned, "heldout_tracking_authorized": True,
    }) + b"\n")
    records, error, attempted, replay_attempted, retained_variants = [], None, 0, False, 0
    with (output / "attempts.jsonl").open("xb") as ledger:

        def log(event):
            ledger.write(_json_bytes(event) + b"\n")
            ledger.flush()
            os.fsync(ledger.fileno())

        for index, ((scenario, seed, condition), inputs) in enumerate(
            zip(selected, planned, strict=True)
        ):
            selector = {"scenario": scenario, "seed": seed, "condition": condition}
            prefix = f"pairs/{scenario}/{seed}/{condition}"
            attempted += 1
            log({"event": "start", **selector})
            retained = []

            def save_variant(name, data, *, retained=retained, prefix=prefix, selector=selector):
                nonlocal retained_variants
                if len(retained) >= 2 or name != spec["grid"]["variant_order"][len(retained)]:
                    raise ValueError("variants must be retained in registered order")
                path = f"{prefix}/{name}.json"
                write(path, data + b"\n")
                retained.append(name)
                retained_variants += 1
                log({
                    "event": "variant_retained", **selector, "variant": name,
                    "path": path, "sha256": files[path], "validated_pair": False,
                })

            try:
                guard()
                scene = generate_inputs(split="heldout", **selector)
                registration, recipe_hashes, recipe = _validated_scene(scene, split="heldout")
                if _json_bytes(scene.manifest()) != _json_bytes(inputs):
                    raise ValueError("case inputs differ from the pre-opening freeze")
                # The only call to replay is after the exclusive claim and exact
                # state/input checks; there is no public single-held-out-case API.
                replay_attempted = True
                record = _run_pair(
                    scene, registration, recipe_hashes, recipe, _score_heldout, save_variant,
                )
                path = f"{prefix}/pair.json"
                write(path, _json_bytes(record) + b"\n")
                _validate_pair_core(
                    record, scene, state["source"], state["baseline_source"],
                    state["environment"], _score_heldout,
                )
                if retained != spec["grid"]["variant_order"] or any(
                    holdout._read(output / f"{prefix}/{v['id']}.json")
                    != _json_bytes(v) + b"\n" for v in record["variants"]
                ):
                    raise ValueError("retained variants differ from completed pair")
                guard()
                if progress is not None:
                    progress(index + 1, len(selected))
                records.append(record)
                log({"event": "success", **selector, "path": path, "sha256": files[path]})
            except Exception as exc:
                error = {**selector, "error_type": type(exc).__name__, "message": str(exc)[:1000]}
                log({"event": "failed", **error})
                break
    files["attempts.jsonl"] = hashlib.sha256(holdout._read(output / "attempts.jsonl")).hexdigest()
    if error is None:
        try:
            guard()
            if _json_bytes(holdout._development_evidence(Path(freeze["development_bundle"]))) != (
                _json_bytes(freeze["development_evidence"])
            ):
                raise ValueError("reviewed development evidence changed during opening")
            summary = _summarize_grid(records, planned, spec, parent, split="heldout")
            write("summary.json", _json_bytes(summary) + b"\n")
            write("summary.md", _markdown(summary).encode())
            expected = set(files)
            if holdout._bundle_hashes(output, expected) != files:
                raise ValueError("saved held-out evidence changed before sealing")
            guard()
        except Exception as exc:
            error = {"error_type": type(exc).__name__, "message": str(exc)[:1000]}
    manifest = {
        "format": "visiontrack.box-gate-heldout-bundle/v1",
        "protocol_id": spec["protocol_id"], "protocol_hashes": hashes,
        "source": state["source"], "environment": state["environment"],
        "baseline_source": state["baseline_source"],
        "freeze_sha256": freeze["freeze_sha256"], "opening": opening,
        "development_evidence": freeze["development_evidence"],
        "status": "failed" if error else "complete", "planned_pairs": len(selected),
        "attempted_pairs": attempted, "successful_pairs": len(records),
        "unattempted_pairs": len(selected) - attempted, "error": error,
        "files_sha256": files, "opening_consumed": True,
        "heldout_replay_attempted": replay_attempted,
        # A failed call may have constructed/updated a tracker without returning
        # a variant. Do not turn that uncertainty into a false 'unopened' claim.
        "heldout_tracking_executed": True if retained_variants else (
            None if replay_attempted else False
        ),
        "complete_study_report": False, "candidate_accepted": False,
        "production_change_authorized": False, "cpp_port_authorized": False,
    }
    manifest["manifest_sha256"] = _sha(manifest)
    with (output / "manifest.json").open("xb") as stream:
        stream.write(_json_bytes(manifest) + b"\n")
        stream.flush()
        os.fsync(stream.fileno())
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        manifest = run_heldout(
            args.freeze, args.output,
            progress=lambda n, total: print(f"Pair {n}/{total}", flush=True),
        )
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        print(f"Held-out opening refused/interrupted: {exc}. Retain evidence; do not retry.",
              file=sys.stderr)
        return 2
    print(f"{manifest['status']}: {manifest['successful_pairs']}/120 pairs; opening consumed")
    return 0 if manifest["status"] == "complete" else 2


if __name__ == "__main__":
    raise SystemExit(main())
