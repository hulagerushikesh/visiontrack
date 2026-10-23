"""One development pair for the registered ablation, not a full-grid exporter.

No split, variant, configuration override, CLI, file writes or held-out entry.
Tests use explicit doubles; comparative experiment runs follow the committed
complete reporting/decision harness, not this adapter's implementation tests.
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, fields
from numbers import Integral

import numpy as np

from experiments.box_gate_protocol import load_registration
from experiments.box_gate_scene import generate_inputs
from experiments.box_gate_scoring import _public_rows, _validated_input, score_development
from experiments.traffic_protocol import ROOT
from experiments.traffic_report import _contrast, _sha
from experiments.traffic_runner import (
    _check_import_origins,
    _environment,
    _git,
    _json_bytes,
    _verify_tree,
)
from experiments.traffic_scene import _digest_arrays


def _snapshot() -> dict:
    """Record local harness bytes, revision and dirty state; not a grid freeze."""
    digests = {}
    paths = sorted({
        path for pattern in ("traffic_*.py", "box_gate_*.py")
        for path in (ROOT / "experiments").glob(pattern)
    })
    for path in paths:
        if path.is_symlink() or path.stat().st_size > 1024 * 1024:
            raise ValueError("unexpected experiment source file")
        digests[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return {
        "actual_revision": _git(ROOT, "rev-parse", "HEAD").decode().strip(),
        "worktree_dirty": bool(_git(ROOT, "status", "--porcelain")),
        "experiment_sha256": digests,
    }


def _construct(settings: dict):
    from visiontrack.tracking.config import TrackerConfig
    from visiontrack.tracking.tracker import ByteTracker

    if {field.name for field in fields(TrackerConfig)} != set(settings):
        raise ValueError("TrackerConfig fields differ from registration")
    config = TrackerConfig(**settings)
    if _json_bytes(asdict(config)) != _json_bytes(settings):
        raise ValueError("constructed configuration differs from registration")
    return ByteTracker(config)


def _config_matches(tracker, settings: dict) -> None:
    if _json_bytes(asdict(tracker.cfg)) != _json_bytes(settings):
        raise ValueError("tracker configuration changed during replay")


def _replay(tracker, scene, parent: dict, settings: dict) -> tuple[list[dict], dict]:
    """Fingerprint the actual Detection payload before each update.

    Writable box copies isolate the immutable source from tracker mutations.
    Only boxes, constant score/class and feature=None enter the tracker; no
    reference IDs, contacts, projection or evaluator state is handed to it.
    """
    from visiontrack.detection.base import Detection

    if type(tracker.frame_index) is not int or tracker.frame_index != -1:
        raise ValueError("tracker must start at frame -1")
    _config_matches(tracker, settings)
    rows, handed_boxes = [], []
    for frame, boxes in enumerate(scene.observed_boxes):
        detections = [
            Detection(box.copy(), scene.detection_score, scene.detection_class_id, feature=None)
            for box in boxes
        ]
        if any(
            d.feature is not None or type(d.score) is not float
            or d.score != scene.detection_score or type(d.class_id) is not int
            or d.class_id != scene.detection_class_id for d in detections
        ):
            raise ValueError("Detection handoff differs from registered metadata")
        handed_boxes.append(np.stack([d.xyxy.copy() for d in detections]))
        observations = tracker.update(detections)
        if type(tracker.frame_index) is not int or tracker.frame_index != frame:
            raise ValueError("tracker did not advance exactly one frame")
        batch = []
        for observation in observations:
            if (
                isinstance(observation.frame, bool) or not isinstance(observation.frame, Integral)
                or observation.frame != frame
            ):
                raise ValueError("public observation frame mismatch")
            batch.append({
                "frame": observation.frame, "track_id": observation.track_id,
                "xyxy": np.asarray(observation.xyxy).tolist(),
                "score": observation.score, "class_id": observation.class_id,
            })
            if len(rows) + len(batch) > 100_000:
                raise ValueError("public output row limit exceeded")
        normalized, _ = _public_rows(batch, parent)
        rows.extend(normalized)
    _config_matches(tracker, settings)
    receipt = {
        "format": "visiontrack.box-gate-detection-inputs/v1",
        "frame_count": len(handed_boxes),
        "detections_per_frame": len(handed_boxes[0]),
        "score": scene.detection_score, "class_id": scene.detection_class_id, "feature": None,
        "arrays_sha256": _digest_arrays({
            "frames": np.arange(len(handed_boxes), dtype="<f8"),
            "observed_boxes": np.asarray(handed_boxes, dtype="<f8"),
        }),
    }
    receipt["detection_stream_sha256"] = _sha(receipt)
    if receipt != scene.detection_manifest():
        raise ValueError("actual Detection stream differs from paired input")
    return rows, receipt


def run_development(*, scenario: str, seed: int, condition: str) -> dict:
    """Replay one fixed pair with isolated fresh/reset/independent-fresh passes.

    No acceptance verdict: a single case cannot satisfy the registered study.
    The later grid exporter must enforce a committed clean complete harness.
    """
    return _run_development(scenario=scenario, seed=seed, condition=condition)


def _run_development(*, scenario: str, seed: int, condition: str, variant_sink=None) -> dict:
    """Exporter hook preserves each finished variant before attempting the next.

    Sink receives immutable canonical bytes, never mutable tracker/scorer state.
    Still development-only; this is not a generic split or held-out bypass.
    """
    scene = generate_inputs(
        split="development", scenario=scenario, seed=seed, condition=condition,
    )
    registration, hashes, parent = _validated_input(scene)
    baseline = _verify_tree(ROOT, registration["baseline_revision"])
    _check_import_origins()
    source, input_manifest = _snapshot(), scene.manifest()
    variants, instances = [], []
    for variant in registration["variants"]:
        settings = {**parent["tracker_config"], **variant["config_patch"]}
        tracker = _construct(settings)
        if any(tracker is previous or tracker.cfg is previous.cfg for previous in instances):
            raise ValueError("variants and fresh passes require isolated tracker/config instances")
        instances.append(tracker)
        outputs, receipts = [], []
        for name in registration["grid"]["pass_order"]:
            if name == "reset":
                tracker.reset()
            elif name == "independent_fresh":
                tracker = _construct(settings)
                if any(
                    tracker is previous or tracker.cfg is previous.cfg for previous in instances
                ):
                    raise ValueError("fresh pass must use an independent tracker/config instance")
                instances.append(tracker)
            rows, receipt = _replay(tracker, scene, parent, settings)
            outputs.append(rows)
            receipts.append(receipt)
        if any(_json_bytes(rows) != _json_bytes(outputs[0]) for rows in outputs[1:]):
            raise ValueError("variant reset/fresh output mismatch")
        scored = score_development(scene, outputs[0])
        if (
            scored["public_rows_sha256"] != _sha(outputs[0])
            or scored["input"] != input_manifest or scored["source"] != baseline
        ):
            raise ValueError("scorer lineage differs from replay")
        variants.append({
            "id": variant["id"], "config": settings, "config_sha256": _sha(settings),
            "output": outputs[0], "output_sha256": _sha(outputs[0]),
            "replay": {
                "passes": 3, "pass_order": registration["grid"]["pass_order"],
                "updates_per_pass": len(scene.frames), "reset_equal": True, "fresh_equal": True,
                "detection_receipts": receipts,
            },
            "scoring": scored,
        })
        if variant_sink is not None:
            variant_sink(variant["id"], _json_bytes(variants[-1]))
    _check_import_origins()
    if (
        _verify_tree(ROOT, registration["baseline_revision"]) != baseline
        or _snapshot() != source or scene.manifest() != input_manifest
        or load_registration()[1] != hashes
    ):
        raise ValueError("source, inputs or registration changed during paired replay")
    result = {
        "format": "visiontrack.box-gate-development-pair/v1",
        "protocol_id": registration["protocol_id"], "protocol_hashes": hashes,
        "input": input_manifest, "baseline_source": baseline, "source": source,
        "environment": _environment(), "variants": variants,
        "candidate_minus_baseline": _contrast([
            (1, variants[1]["scoring"]["endpoints"]),
            (-1, variants[0]["scoring"]["endpoints"]),
        ]),
        "heldout_tracking_executed": False, "complete_study_report": False,
        "limitations": [
            "One development pair, not a full grid, decision or real-traffic claim.",
            "Actual source/runtime recorded, not a cross-environment bit-parity guarantee.",
            "Input receipts fingerprint pre-update payloads, not truth-assisted associations.",
            "Workflow provenance is not a sandbox against monkeypatched or malicious runtimes.",
        ],
    }
    result["record_sha256"] = _sha(result)
    return result
