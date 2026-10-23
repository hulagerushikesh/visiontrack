"""New exploratory DEV-only trace wrapper; not the old study or validation.

All original evidence is read-only. No held-out input, selector override, scorer,
resume or automatic retry entry exists. Tests use explicit execution doubles.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import subprocess
import sys
from pathlib import Path

from experiments.box_gate_audit import audit as development_audit
from experiments.box_gate_combined_audit import Evidence, canonical, check, grid, same, sha
from experiments.box_gate_protocol import load_registration
from experiments.box_gate_runner import _construct, _snapshot
from experiments.box_gate_scene import generate_inputs
from experiments.box_gate_trace import ParityMismatch, observe_sequence, selected_frames
from experiments.traffic_protocol import ROOT, load_frozen_protocol
from experiments.traffic_runner import _check_import_origins, _environment, _verify_tree
from visiontrack.detection.base import Detection

POLICY = "new exploratory development replay; full grid; stop first error; no resume or retry"
VARIANTS = ("baseline", "gate_off")
MAX_TRACE_BYTES = 64 * 1024 * 1024


def _state():
    state = dict(source=_snapshot(), environment=_environment())
    check(state["source"]["worktree_dirty"] is False, "commit all changes before tracing")
    _check_import_origins()
    return state


def _prepare(bundle, root):
    """Authenticate all saved DEV evidence and regenerate inputs, without tracking."""
    check(root.resolve() == ROOT.resolve(), "use this wrapper's repository")
    state = _state()
    evidence = Evidence()
    index = evidence.index(root, "development")
    spec, hashes = load_registration(root)
    parent, _ = load_frozen_protocol(root)
    same(hashes, index["protocol_hashes"], "original protocols required")
    manifest, plan = evidence.bundle(bundle, index, spec, parent, "development")
    helper = index["audit"]
    same(sha(evidence.bytes(root / helper["script"])), helper["script_sha256"], "audit helper")
    saved_audit = evidence.load(bundle.parent / "audit.json")
    same(sha(evidence.bytes(bundle.parent / "audit.json")), helper["output_sha256"], "saved audit")
    check(development_audit(bundle, root) == saved_audit, "original development audit differs")
    same(state["environment"], index["environment"], "original runtime required for exact parity")
    baseline = _verify_tree(root, spec["baseline_revision"])
    same(baseline, plan["baseline_source"], "baseline source differs")
    names = set(state["source"]["experiment_sha256"]) | set(baseline["files"])
    names.update(str(p.relative_to(root)) for pattern in ("test_box_gate*.py", "test_traffic*.py")
                 for p in (root / "tests").glob(pattern))
    names.update(("pyproject.toml", "experiments/box_gate_protocol_v1.sha256",
                  "experiments/traffic_protocol_v1.sha256"))
    code = {name: sha(evidence.bytes(root / name)) for name in sorted(names)}
    cases = []
    for position, (scenario, seed, condition) in enumerate(grid(spec, parent, "development")):
        scene = generate_inputs(split="development", scenario=scenario, seed=seed,
                                condition=condition)
        same(scene.manifest(), plan["inputs"][position], "regenerated development input differs")
        variants = []
        for definition in spec["variants"]:
            name = definition["id"]
            record = evidence.load(bundle / f"pairs/{scenario}/{seed}/{condition}/{name}.json")
            settings = {**parent["tracker_config"], **definition["config_patch"]}
            same(record["id"], name, "variant order")
            same(record["config"], settings, "saved settings differ")
            same(record["scoring"]["input"], scene.manifest(), "variant input differs")
            same(sha(canonical(record["output"])), record["output_sha256"], "saved output seal")
            variants.append(record)
        times = [event["frame_time"] for v in variants
                 for event in v["scoring"]["crossing"]["bottom_centre"]["predicted_events"]]
        cases.append(dict(selector=dict(scenario=scenario, seed=seed, condition=condition),
                          scene=scene, variants=variants, frames=selected_frames(times)))
    same(len(cases), 120, "the full 120-pair development grid is required")
    context = dict(evidence=evidence, root=root, state=state, code=code, cases=cases,
                   manifest=manifest, index=index)
    _guard(context, full=True)
    return context


def _guard(context, *, full=False):
    same(_state(), context["state"], "source or runtime changed during diagnostic")
    for name, digest in context["code"].items():
        same(sha(context["evidence"].bytes(context["root"] / name)), digest, "code changed")
    if full:
        context["evidence"].unchanged()


def _payload(scene):
    """Only detections enter the tracker, never reference IDs/calibration/truth."""
    detections = [[Detection(box.copy(), scene.detection_score, scene.detection_class_id,
                             feature=None) for box in boxes] for boxes in scene.observed_boxes]
    expected = b"".join(canonical(dict(frame=f, detections=[dict(
        xyxy=box.tolist(), score=scene.detection_score, class_id=scene.detection_class_id,
        feature=None,
    ) for box in boxes])) + b"\n" for f, boxes in enumerate(scene.observed_boxes))
    return detections, sha(expected)


def _trace_variant(case, record):
    scene = case["scene"]
    before = scene.manifest()
    detections, expected_payload = _payload(scene)
    result = observe_sequence(_construct(record["config"]), detections,
                              frames=case["frames"], expected_output=record["output"])
    same(scene.manifest(), before, "input mutated during tracing")
    same(result["format"], "visiontrack.box-gate-internal-trace/v1", "trace format")
    same(result["frame_count"], before["frame_count"], "complete update count")
    same(result["settings"], record["config"], "traced settings")
    same(result["selected_frames"], case["frames"], "fixed trace selection")
    same(result["public_output"], record["output"], "exact complete output parity")
    for key in ("expected_output_sha256", "actual_output_sha256"):
        same(result[key], record["output_sha256"], "public output hash")
    same(result["detection_payload_sha256"], expected_payload, "actual input payload differs")
    same(result["exact_public_output_parity"], True, "observer parity check failed")
    for key in ("provenance_verified", "interpretation_allowed", "validation_evidence"):
        same(result[key], False, "observer cannot authorize itself")
    return dict(selector=case["selector"], variant=record["id"],
                saved_input_sha256=before["input_sha256"],
                saved_output_sha256=record["output_sha256"],
                interpretation_allowed=False, diagnostic=result)


def _output_path(output, root, bundle):
    check(not output.is_symlink() and not output.exists(), "use a new output directory")
    resolved = output.resolve()
    for protected in (root.resolve(), bundle.parent.resolve()):
        check(not resolved.is_relative_to(protected) and not protected.is_relative_to(resolved),
              "output must be disjoint from repository and original development evidence")
    check(resolved.parent.is_dir(), "output parent must exist")
    return resolved


def _verify_written(output, files):
    """Check exact coverage and bytes before authorizing the completed bundle."""
    paths = list(output.rglob("*"))
    check(not any(p.is_symlink() for p in paths), "trace output contains a symlink")
    same(sorted(str(p.relative_to(output)) for p in paths if p.is_file()), sorted(files),
         "trace output coverage differs")
    for name, expected in files.items():
        digest, size = hashlib.sha256(), 0
        with (output / name).open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                size += len(chunk)
                check(size <= MAX_TRACE_BYTES, "trace output size limit")
                digest.update(chunk)
        same(digest.hexdigest(), expected, "trace output changed")


def run_development_trace(bundle, output, *, root=ROOT):
    """One NEW complete-grid exploratory replay; no changes to prior evidence.

    Partial receipts never authorize interpretation. Only a complete, unchanged
    manifest permits exploratory inspection, not intervention acceptance.
    """
    # Reject symlinks before resolving. Bundle coverage rejects child symlinks.
    check(not bundle.is_symlink(), "original bundle must not be a symlink")
    output = _output_path(output, root, bundle)
    context = _prepare(bundle, root)  # NO tracker before every preflight passes.
    output.mkdir(exist_ok=False)
    files = {}

    def write(name, value):
        raw = canonical(value) + b"\n"
        check(len(raw) <= MAX_TRACE_BYTES, "trace output size limit")
        path = output / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        files[name] = sha(raw)

    completed, attempted, error = 0, 0, None
    current = None
    plan = dict(
        format="visiontrack.box-gate-development-trace-plan/v1", policy=POLICY,
        original_development_manifest_sha256=context["manifest"]["manifest_sha256"],
        original_source_revision=context["index"]["source_revision"],
        diagnostic_state=context["state"], code_sha256=context["code"],
        cases=[dict(selector=c["selector"], frames=c["frames"],
                    input_sha256=c["scene"].manifest()["input_sha256"],
                    expected_outputs={r["id"]: r["output_sha256"] for r in c["variants"]})
               for c in context["cases"]],
        heldout_files_read=False, production_change_authorized=False,
        validation_evidence=False,
    )
    try:
        write("plan.json", plan)
        for case in context["cases"]:
            for record in case["variants"]:
                current = dict(**case["selector"], variant=record["id"])
                _guard(context)
                attempted += 1
                write(f"attempts/{attempted:03d}.json", dict(status="started", **current))
                result = _trace_variant(case, record)
                write(f"traces/{attempted:03d}.json", result)
                _guard(context)
                completed += 1
        _guard(context, full=True)
        same((attempted, completed), (240, 240), "complete diagnostic grid required")
        _verify_written(output, files)
    except BaseException as exc:
        error = dict(type=type(exc).__name__, message=str(exc), current=current)
        if isinstance(exc, ParityMismatch):
            write("failed_trace.json", exc.diagnostic)
        if not isinstance(exc, Exception):
            # Best effort interrupted receipt; the original study is untouched.
            write("interrupted.json", dict(error=error, interpretation_allowed=False))
            raise
    manifest = dict(
        format="visiontrack.box-gate-development-trace-manifest/v1", policy=POLICY,
        status="complete" if error is None else "failed", error=error,
        attempted_variants=attempted, completed_variants=completed,
        unattempted_variants=240 - attempted, files_sha256=files.copy(),
        original_development_manifest_sha256=plan["original_development_manifest_sha256"],
        diagnostic_state=context["state"],
        exploratory_interpretation_allowed=error is None,
        heldout_files_read=False, is_original_registered_execution=False,
        validation_evidence=False, production_change_authorized=False,
        limitations=["New development-only diagnostic, not fresh validation or a fix.",
                     "Partial traces remain unapproved; stop on first error, no resume/retry.",
                     "Hashes and local guards are not a malicious-runtime sandbox or witness.",
                     "No new scoring, real-world accuracy or C++ adoption claim."],
    )
    manifest["manifest_sha256"] = sha(canonical(manifest))
    write("manifest.json", manifest)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--development", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        manifest = run_development_trace(args.development, args.output)
        print(canonical(dict(status=manifest["status"], manifest_sha256=manifest["manifest_sha256"],
                             output=str(args.output.resolve()))).decode())
        return 0 if manifest["status"] == "complete" else 2
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        print(f"Development trace refused: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
