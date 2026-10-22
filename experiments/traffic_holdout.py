"""Prepare a committed harness/input freeze, then explicitly open held-out once.

Preparing generates geometry only. Opening is a separate command, retaining
every attempt and refusing automatic reruns, selection, tuning or overrides.
Workflow/integrity guards are not an adversarial sandbox or scientific validity.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from experiments.traffic_protocol import (
    ROOT,
    _reject_constant,
    _unique_pairs,
    load_frozen_protocol,
)
from experiments.traffic_report import (
    _cases,
    _export_grid,
    _sha,
    _snapshot,
    _split_cases,
    _summarize,
)
from experiments.traffic_runner import _environment, _git, _json_bytes, _run_case, _verify_tree
from experiments.traffic_scene import generate_scene

INDEX = "experiments/traffic_development_v1_evidence.json"
MAX_FILE_BYTES = 2 * 1024 * 1024


def _read(path: Path) -> bytes:
    if path.is_symlink():
        raise ValueError("evidence files must not be symlinks")
    with path.open("rb") as stream:
        data = stream.read(MAX_FILE_BYTES + 1)
    if len(data) > MAX_FILE_BYTES:
        raise ValueError("evidence file exceeds size limit")
    return data


def _load(path: Path) -> dict:
    value = json.loads(
        _read(path), object_pairs_hook=_unique_pairs, parse_constant=_reject_constant
    )
    if not isinstance(value, dict):
        raise ValueError("expected a JSON evidence object")
    return value


def _harness() -> dict:
    """Commit-bind implementation, its tests, package settings and protocol locks."""
    revision = _git(ROOT, "rev-parse", "HEAD").decode().strip()
    names = {
        str(p.relative_to(ROOT))
        for pattern in ("experiments/traffic_*.py", "tests/test_traffic*.py")
        for p in ROOT.glob(pattern)
    }
    names.update(
        {
            "pyproject.toml",
            INDEX,
            "experiments/traffic_protocol_v1.json",
            "experiments/traffic_protocol_v1.sha256",
            "docs/TRAFFIC_RELIABILITY_PROTOCOL.md",
        }
    )
    files = {}
    for name in sorted(names):
        data = _read(ROOT / name)
        if data != _git(ROOT, "show", f"{revision}:{name}"):
            raise ValueError("commit the complete harness and tests before freezing")
        files[name] = hashlib.sha256(data).hexdigest()
    return files


def _development_evidence(bundle: Path) -> dict:
    """Independently check the retained, already-indexed 120-run development bundle."""
    spec, hashes = load_frozen_protocol()
    index = _load(ROOT / INDEX)
    bundle = Path(bundle).resolve()
    if bundle.is_relative_to(ROOT.resolve()):
        raise ValueError("development evidence must remain outside the repository")
    manifest = _load(bundle / "manifest.json")
    content = dict(manifest)
    digest = content.pop("manifest_sha256")
    expected_files = {
        "plan.json",
        "attempts.jsonl",
        "summary.json",
        "summary.md",
        *[f"runs/{s}/{n}/{c}.json" for s, n, c in _cases(spec)],
    }
    if (
        manifest["format"] != "visiontrack.traffic-development-bundle/v1"
        or manifest["status"] != "complete"
        or [manifest[k] for k in ("planned_runs", "attempted_runs", "successful_runs")] != [120] * 3
        or manifest["unattempted_runs"] != 0
        or manifest["error"] is not None
        or manifest["heldout_tracking_executed"] is not False
        or manifest["protocol_id"] != spec["protocol_id"]
        or manifest["protocol_hashes"] != hashes
        or manifest["source"]["actual_revision"] != index["harness_revision"]
        or set(manifest["files_sha256"]) != expected_files
        or digest != _sha(content)
        or digest != index["bundle"]["manifest_content_sha256"]
    ):
        raise ValueError("complete indexed development evidence required")
    # Only registered relative names are traversed; no paths supplied by JSON.
    for name in sorted(expected_files | {"manifest.json"}):
        path = bundle / name
        if not path.resolve().is_relative_to(bundle):
            raise ValueError("development evidence escapes its bundle")
        actual = hashlib.sha256(_read(path)).hexdigest()
        expected = (
            index["bundle"]["file_sha256"][name]
            if name == "manifest.json"
            else manifest["files_sha256"][name]
        )
        if actual != expected or (
            name in index["bundle"]["file_sha256"]
            and actual != index["bundle"]["file_sha256"][name]
        ):
            raise ValueError("development evidence file digest mismatch")
    return {
        "index_sha256": hashlib.sha256(_read(ROOT / INDEX)).hexdigest(),
        "harness_revision": index["harness_revision"],
        "manifest_content_sha256": digest,
        "verified_non_manifest_files": len(expected_files),
        "successful_runs": 120,
        "file_sha256": index["bundle"]["file_sha256"],
    }


def _inputs(spec: dict) -> list[dict]:
    return [
        generate_scene(split="heldout", scenario=s, seed=n, condition=c).manifest()
        for s, n, c in _split_cases(spec, "heldout")
    ]


def prepare_freeze(output: Path, *, development_bundle: Path) -> dict:
    """Save all held-out input digests and verified code WITHOUT running a tracker."""
    spec, hashes = load_frozen_protocol()
    source = _snapshot()
    harness = _harness()
    baseline = _verify_tree(ROOT, spec["baseline_revision"])
    environment = _environment()
    evidence = _development_evidence(development_bundle)
    inputs = _inputs(spec)
    if (
        _snapshot() != source
        or _harness() != harness
        or _verify_tree(ROOT, spec["baseline_revision"]) != baseline
        or _environment() != environment
    ):
        raise ValueError("harness/environment changed while preparing freeze")
    freeze = {
        "format": "visiontrack.traffic-heldout-freeze/v1",
        "protocol_id": spec["protocol_id"],
        "protocol_hashes": hashes,
        "recipe": spec,
        "source": source,
        "harness_files_sha256": harness,
        "baseline": baseline,
        "environment": environment,
        "development_evidence": evidence,
        "inputs": inputs,
        "planned_runs": len(inputs),
        "heldout_tracking_executed": False,
        "complete_study_report": False,
        "real_data_validated": False,
        "execution_policy": "one complete grid; stop on first error; no automatic rerun",
    }
    freeze["freeze_sha256"] = _sha(freeze)
    output = Path(output).resolve()
    if output.is_relative_to(ROOT.resolve()):
        raise ValueError("freeze outside the repository")
    output.mkdir(exist_ok=False)
    with (output / "freeze.json").open("xb") as stream:
        stream.write(_json_bytes(freeze) + b"\n")
    return freeze


def verify_freeze(path: Path) -> dict:
    """Read-only gate; docs-only descendant commits may follow the frozen harness."""
    freeze = _load(path)
    content = dict(freeze)
    digest = content.pop("freeze_sha256")
    spec, hashes = load_frozen_protocol()
    if (
        freeze["format"] != "visiontrack.traffic-heldout-freeze/v1"
        or digest != _sha(content)
        or freeze["protocol_id"] != spec["protocol_id"]
        or freeze["protocol_hashes"] != hashes
        or freeze["recipe"] != spec
        or freeze["planned_runs"] != 120
        or freeze["heldout_tracking_executed"] is not False
        or freeze["complete_study_report"] is not False
        or freeze["real_data_validated"] is not False
        or freeze["execution_policy"]
        != "one complete grid; stop on first error; no automatic rerun"
    ):
        raise ValueError("invalid held-out freeze")
    source = _snapshot()
    # Later docs/index commits are allowed, but source/tests/config cannot drift.
    _git(ROOT, "merge-base", "--is-ancestor", freeze["source"]["actual_revision"], "HEAD")
    if (
        source["experiment_sha256"] != freeze["source"]["experiment_sha256"]
        or _harness() != freeze["harness_files_sha256"]
        or _verify_tree(ROOT, spec["baseline_revision"]) != freeze["baseline"]
        or _environment() != freeze["environment"]
        or _inputs(spec) != freeze["inputs"]
    ):
        raise ValueError("frozen harness, environment or inputs changed; do not silently refreeze")
    index = _load(ROOT / INDEX)
    evidence = freeze["development_evidence"]
    if (
        evidence["index_sha256"] != hashlib.sha256(_read(ROOT / INDEX)).hexdigest()
        or evidence["harness_revision"] != index["harness_revision"]
        or evidence["manifest_content_sha256"] != index["bundle"]["manifest_content_sha256"]
        or evidence["file_sha256"] != index["bundle"]["file_sha256"]
        or evidence["successful_runs"] != 120
        or evidence["verified_non_manifest_files"] != 124
    ):
        raise ValueError("frozen development evidence differs from reviewed index")
    return freeze


def export_heldout(output: Path, *, freeze_path: Path, progress=None) -> dict:
    """Explicitly consume the freeze's single local opening; no resume/retry mode."""
    freeze_path = Path(freeze_path).resolve()
    if freeze_path.is_relative_to(ROOT.resolve()):
        raise ValueError("use the original external freeze directory")
    freeze = verify_freeze(freeze_path)
    if (freeze_path.parent / "opening.json").exists():
        raise FileExistsError("held-out opening already claimed; retain it, do not retry/refreeze")

    def preflight(source, inputs):
        if verify_freeze(freeze_path) != freeze or inputs != freeze["inputs"]:
            raise ValueError("freeze changed during held-out export")

    def claim(output):
        # Claim before any tracker construction; a crash/failure consumes this
        # local opening too. Do not delete/copy/refreeze to disguise an opening.
        with (freeze_path.parent / "opening.json").open("xb") as stream:
            stream.write(
                _json_bytes(
                    {
                        "freeze_sha256": freeze["freeze_sha256"],
                        "output": str(output),
                        "policy": freeze["execution_policy"],
                    }
                )
                + b"\n"
            )

    def run_case(**selector):
        record = _run_case(split="heldout", **selector)
        if (
            record["environment"] != freeze["environment"]
            or record["source"]["baseline"] != freeze["baseline"]
        ):
            raise ValueError("run environment/baseline differs from freeze")
        record.pop("record_sha256")
        record["heldout_freeze"] = {
            "sha256": freeze["freeze_sha256"],
            "harness_revision": freeze["source"]["actual_revision"],
        }
        record["record_sha256"] = _sha(record)
        return record

    return _export_grid(
        output,
        split="heldout",
        runner=run_case,
        summarize=lambda records: _summarize(records, split="heldout"),
        progress=progress,
        preflight=preflight,
        before_runs=claim,
        freeze_sha256=freeze["freeze_sha256"],
        freeze_revision=freeze["source"]["actual_revision"],
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)
    prepare = actions.add_parser("prepare", help="geometry/provenance only, no tracker")
    prepare.add_argument("--output", required=True, type=Path)
    prepare.add_argument("--development-bundle", required=True, type=Path)
    verify = actions.add_parser("verify", help="read-only freeze check, no tracker")
    verify.add_argument("--freeze", required=True, type=Path)
    run = actions.add_parser("run", help="explicitly OPEN held-out tracking once")
    run.add_argument("--freeze", required=True, type=Path)
    run.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        if args.action == "prepare":
            freeze = prepare_freeze(args.output, development_bundle=args.development_bundle)
            print(f"Frozen {freeze['planned_runs']} input cases; held-out tracking NOT executed.")
            print(f"Freeze SHA-256: {freeze['freeze_sha256']}")
        elif args.action == "verify":
            freeze = verify_freeze(args.freeze)
            print(f"Verified freeze {freeze['freeze_sha256']}; no tracker executed.")
        else:
            manifest = export_heldout(
                args.output,
                freeze_path=args.freeze,
                progress=lambda n, total: print(f"Held-out {n}/{total}", flush=True)
                if n % 10 == 0
                else None,
            )
            print(f"{manifest['status']}: {manifest['successful_runs']}/{manifest['planned_runs']}")
            return 0 if manifest["status"] == "complete" else 2
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        print(f"Held-out action refused: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
