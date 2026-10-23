"""Input/code/evidence freeze; execution lives in box_gate_execution separately.

Preparation generates geometry and audits saved development records only. Build
and commit the complete held-out replay/export gate before issuing a real freeze.
Any later commit invalidates this exact-revision freeze, even a docs-only commit.
This local workflow is not a security sandbox or a global opening registry.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from experiments.box_gate_audit import audit, compare
from experiments.box_gate_decision import cases
from experiments.box_gate_protocol import load_registration
from experiments.box_gate_report import _snapshot
from experiments.box_gate_scene import generate_inputs
from experiments.traffic_protocol import (
    ROOT,
    _reject_constant,
    _unique_pairs,
    load_frozen_protocol,
)
from experiments.traffic_report import _sha
from experiments.traffic_runner import (
    _check_import_origins,
    _environment,
    _git,
    _json_bytes,
    _verify_tree,
)

INDEX = "experiments/box_gate_development_v1_evidence.json"
MAX_BYTES = 4 * 1024 * 1024
POLICY = "one complete ordered grid; claim before tracker; stop on first error; no retry"


def _read(path: Path) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise ValueError("expected a regular evidence file, not a symlink")
    with path.open("rb") as stream:
        data = stream.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError("evidence file exceeds size limit")
    return data


def _load(path: Path) -> dict:
    value = json.loads(
        _read(path), object_pairs_hook=_unique_pairs, parse_constant=_reject_constant,
    )
    if not isinstance(value, dict):
        raise ValueError("expected a JSON evidence object")
    return value


def _external(path: Path) -> Path:
    path = Path(path)
    if path.is_symlink():
        raise ValueError("external evidence path must not be a symlink")
    resolved = path.resolve()
    if resolved.is_relative_to(ROOT.resolve()):
        raise ValueError("keep freeze and evidence outside the repository")
    return resolved


def _state() -> dict:
    """Exact committed code/settings/recipe/runtime; no tracker construction."""
    spec, hashes = load_registration()
    parent, _ = load_frozen_protocol()
    source = _snapshot()  # Refuses tracked AND untracked dirty worktrees.
    data = _read(ROOT / INDEX)
    revision = source["replay_source"]["actual_revision"]
    if data != _git(ROOT, "show", f"{revision}:{INDEX}"):
        raise ValueError("commit the reviewed development index before freezing")
    source["harness_sha256"][INDEX] = hashlib.sha256(data).hexdigest()
    _check_import_origins()
    return {
        "protocol_id": spec["protocol_id"], "protocol_hashes": hashes,
        "registration": spec, "source": source,
        "baseline_source": _verify_tree(ROOT, spec["baseline_revision"]),
        "environment": _environment(),
        "configurations": [
            {"id": v["id"], "settings": {**parent["tracker_config"], **v["config_patch"]}}
            for v in spec["variants"]
        ],
    }


def _bundle_hashes(bundle: Path, expected: set[str]) -> dict:
    """Fixed registered paths, bounded reads, no undeclared files or links."""
    paths = list(bundle.rglob("*"))
    if any(p.is_symlink() for p in paths):
        raise ValueError("development bundle must not contain symlinks")
    if {str(p.relative_to(bundle)) for p in paths if p.is_file()} != expected:
        raise ValueError("complete exact development bundle coverage required")
    result = {}
    for name in sorted(expected):
        path = bundle / name
        if not path.resolve().is_relative_to(bundle):
            raise ValueError("development file escapes its bundle")
        result[name] = hashlib.sha256(_read(path)).hexdigest()
    return result


def _development_evidence(bundle: Path) -> dict:
    """Re-audit all saved negative results, not just a self-consistent manifest."""
    bundle = _external(bundle)
    spec, hashes = load_registration()
    parent, _ = load_frozen_protocol()
    index_bytes = _read(ROOT / INDEX)
    index = _load(ROOT / INDEX)
    expected = {"manifest.json", "plan.json", "attempts.jsonl", "summary.json", "summary.md"}
    for scenario, seed, condition in cases(spec, parent, "development"):
        prefix = f"pairs/{scenario}/{seed}/{condition}"
        expected.update(f"{prefix}/{name}.json" for name in ("baseline", "gate_off", "pair"))
    file_hashes = _bundle_hashes(bundle, expected)
    manifest = _load(bundle / "manifest.json")
    if (
        index["protocol_hashes"] != hashes
        or index["complete_development_grid"] is not True
        or index["heldout_tracking_executed"] is not False
        or index["candidate_tuned"] is not False
        or file_hashes["manifest.json"] != index["manifest_raw_sha256"]
        or manifest["manifest_sha256"] != index["bundle_manifest_sha256"]
        or manifest["source"]["replay_source"]["actual_revision"] != index["source_revision"]
        or manifest["environment"] != index["environment"]
        or file_hashes != {
            **manifest["files_sha256"], "manifest.json": file_hashes["manifest.json"],
        }
        or any(file_hashes[name] != digest for name, digest in index["artifact_sha256"].items())
        or index["audit"]["script"] != "experiments/box_gate_audit.py"
        or hashlib.sha256(_read(ROOT / "experiments/box_gate_audit.py")).hexdigest()
        != index["audit"]["script_sha256"]
    ):
        raise ValueError("development bundle differs from the reviewed committed index")
    result = audit(bundle, ROOT)  # stdlib-only arithmetic, no generator/scorer/tracker call.
    # Pin the existing companion file, never follow an absolute path supplied
    # by JSON. Historic integral metrics may serialize as 4 rather than 4.0:
    # retain those bytes and require both typed structure and exact value
    # equality, rather than rewriting the old record or weakening a margin.
    audit_path = bundle.parent / "audit.json"
    audit_bytes = _read(audit_path)
    if hashlib.sha256(audit_bytes).hexdigest() != index["audit"]["output_sha256"]:
        raise ValueError("saved-record audit file differs from reviewed negative results")
    reviewed = _load(audit_path)
    compare(reviewed, result, "reviewed development audit")
    if reviewed != result:
        raise ValueError("recalculated audit differs from reviewed negative results")
    if (
        _bundle_hashes(bundle, expected) != file_hashes
        or _read(ROOT / INDEX) != index_bytes or _read(audit_path) != audit_bytes
    ):
        raise ValueError("development evidence changed during audit")
    return {
        "index_sha256": hashlib.sha256(index_bytes).hexdigest(),
        "source_revision": index["source_revision"],
        "bundle_manifest_sha256": index["bundle_manifest_sha256"],
        "files_sha256": file_hashes,
        "audit_output_sha256": index["audit"]["output_sha256"],
        "environment": manifest["environment"],
        "paired_cases": result["paired_cases"],
        "safety_endpoint_violations": len(result["safety_regressions"]),
        "candidate_accepted": False,
    }


def _inputs() -> list[dict]:
    spec, _ = load_registration()
    parent, _ = load_frozen_protocol()
    return [
        generate_inputs(split="heldout", scenario=s, seed=n, condition=c).manifest()
        for s, n, c in cases(spec, parent, "heldout")
    ]


def prepare_freeze(output: Path, *, development_bundle: Path) -> dict:
    """Persist only an input/code/evidence freeze, never open tracking.

    Do not issue the real freeze until the complete execution gate is committed.
    An existing directory is never overwritten; this API cannot resume a run.
    """
    output = _external(output)
    if output.exists():
        raise FileExistsError("freeze directory already exists; do not overwrite/refreeze")
    bundle = _external(development_bundle)
    state = _state()
    evidence, inputs = _development_evidence(bundle), _inputs()
    if _json_bytes(evidence["environment"]) != _json_bytes(state["environment"]):
        raise ValueError("held-out runtime must match the reviewed development environment")
    if _json_bytes(_state()) != _json_bytes(state):
        raise ValueError("code, environment or registration changed during preparation")
    freeze = {
        "format": "visiontrack.box-gate-heldout-freeze/v1", **state,
        "development_bundle": str(bundle), "development_evidence": evidence,
        "inputs": inputs, "inputs_sha256": _sha(inputs),
        "planned_pairs": 120, "variant_runs": 240, "replay_passes": 720,
        "execution_policy": POLICY,
        "heldout_tracking_executed": False, "complete_study_report": False,
        "production_change_authorized": False, "cpp_port_authorized": False,
    }
    freeze["freeze_sha256"] = _sha(freeze)
    output.mkdir(exist_ok=False)
    with (output / "freeze.json").open("xb") as stream:
        stream.write(_json_bytes(freeze) + b"\n")
    return freeze


def verify_freeze(path: Path) -> dict:
    """Read-only pre-opening check, including full development evidence re-audit.

    Exact revision required: no automatic descendant/refreeze exception. A
    separate executor claims opening.json exclusively before any construction.
    Verification itself never creates that claim or authorizes an execution.
    """
    path = _external(path)
    if path.name != "freeze.json":
        raise ValueError("use the original external freeze.json")
    opening = path.parent / "opening.json"
    if opening.exists() or opening.is_symlink():
        raise FileExistsError("opening already claimed; retain evidence, do not retry")
    freeze = _load(path)
    body = dict(freeze)
    digest = body.pop("freeze_sha256", None)
    if digest != _sha(body):
        raise ValueError("invalid freeze seal")
    state = _state()
    evidence = _development_evidence(Path(freeze["development_bundle"]))
    if _json_bytes(evidence["environment"]) != _json_bytes(state["environment"]):
        raise ValueError("held-out runtime differs from reviewed development environment")
    inputs = _inputs()
    expected = {
        "format": "visiontrack.box-gate-heldout-freeze/v1", **state,
        "development_bundle": str(_external(Path(freeze["development_bundle"]))),
        "development_evidence": evidence,
        "inputs": inputs, "inputs_sha256": _sha(inputs),
        "planned_pairs": 120, "variant_runs": 240, "replay_passes": 720,
        "execution_policy": POLICY,
        "heldout_tracking_executed": False, "complete_study_report": False,
        "production_change_authorized": False, "cpp_port_authorized": False,
    }
    if _json_bytes(body) != _json_bytes(expected) or _json_bytes(_state()) != _json_bytes(state):
        raise ValueError("frozen code, inputs, environment or evidence changed; do not refreeze")
    if _read(path) != _json_bytes(freeze) + b"\n":
        raise ValueError("freeze must retain its exact canonical saved bytes")
    return freeze


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)
    prepare = actions.add_parser("prepare", help="code/input freeze only; no tracker")
    prepare.add_argument("--output", required=True, type=Path)
    prepare.add_argument("--development-bundle", required=True, type=Path)
    verify = actions.add_parser("verify", help="read-only check; no opening or tracker")
    verify.add_argument("--freeze", required=True, type=Path)
    args = parser.parse_args()
    try:
        freeze = (
            prepare_freeze(args.output, development_bundle=args.development_bundle)
            if args.action == "prepare" else verify_freeze(args.freeze)
        )
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        print(f"Box-gate freeze refused: {exc}", file=sys.stderr)
        return 2
    print(f"{args.action}: {freeze['freeze_sha256']}; no held-out tracking or opening.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
