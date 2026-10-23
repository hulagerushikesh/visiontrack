"""Development reference scorer plus private shared reference arithmetic.

Consumes supplied public rows; never constructs a tracker or opens a holdout.
Hand-fed rows are scorer fixtures, not evidence that either variant produced them.
The public API remains development-only. The separate exclusive opening gate
uses private split-specific regeneration/arithmetic without weakening that API.
The original traffic-v1 files and their selector guards remain unchanged.
"""

from __future__ import annotations

from dataclasses import asdict, fields
from numbers import Integral, Real

import numpy as np

from experiments.box_gate_protocol import load_registration
from experiments.box_gate_scene import BoxGateInputs, generate_inputs
from experiments.traffic_crossing import AnchorSample, extract_crossings, score_crossings
from experiments.traffic_diagnostics import (
    ANCHORS,
    MAX_ROWS,
    PHASES,
    _error,
    _phase,
    _region,
    _summary,
    _validated_rows,
    _world_anchors,
)
from experiments.traffic_protocol import ROOT, load_frozen_protocol
from experiments.traffic_report import _metrics, _sha
from experiments.traffic_runner import (
    _anchor_samples,
    _check_import_origins,
    _json_bytes,
    _verify_tree,
)
from experiments.traffic_scene import GroundProjection


def _validated_input(scene: BoxGateInputs) -> tuple[dict, dict, dict]:
    """Regenerate registered development inputs, comparing every field/array.

    A self-consistent manifest alone cannot establish input provenance. Reject
    held-out selectors before generation; no generic split bypass is exposed.
    This is a workflow guard, not a sandbox for malicious concurrent callers.
    """
    if type(scene) is not BoxGateInputs or scene.split != "development":
        raise ValueError("scoring requires registered development BoxGateInputs")
    return _validated_scene(scene, split="development")


def _validated_scene(scene: BoxGateInputs, *, split: str) -> tuple[dict, dict, dict]:
    """Private split-specific regeneration; held-out callers require the opening gate.

    This helper grants no execution permission. The public development wrapper
    rejects held-out inputs before reaching it; it is not a security boundary.
    """
    if split not in {"development", "heldout"} or type(scene) is not BoxGateInputs:
        raise ValueError("expected registered BoxGateInputs and an explicit split")
    if scene.split != split:
        raise ValueError("input split differs from the required evaluation split")
    registration, hashes = load_registration()
    parent, parent_hashes = load_frozen_protocol()
    if parent_hashes != registration["parent_artifacts"]:
        raise ValueError("parent protocol changed during scoring preflight")
    expected = generate_inputs(
        split=split, scenario=scene.scenario, seed=scene.seed, condition=scene.condition,
    )
    for field in fields(BoxGateInputs):
        actual, canonical = getattr(scene, field.name), getattr(expected, field.name)
        if isinstance(canonical, np.ndarray):
            equal = (
                type(actual) is np.ndarray and actual.dtype == canonical.dtype
                and actual.shape == canonical.shape
                and actual.tobytes() == canonical.tobytes()
            )
        else:
            equal = (
                type(actual) is type(canonical) and _json_bytes(actual) == _json_bytes(canonical)
            )
        if not equal:
            raise ValueError(f"input differs from registered generator: {field.name}")
    if dict(scene.protocol_hashes) != hashes:
        raise ValueError("input registration provenance differs")
    return registration, hashes, parent


def _public_rows(rows: list[dict], parent: dict) -> tuple[list[dict], dict]:
    """Bounded JSON-shaped public outputs, with no truth-based filtering."""
    if not isinstance(rows, list) or len(rows) > MAX_ROWS:
        raise ValueError("expected a bounded list of public output rows")
    normalized = []
    for row in rows:
        if not isinstance(row, dict) or set(row) != {
            "frame", "track_id", "xyxy", "score", "class_id",
        }:
            raise ValueError("public row fields differ from replay output schema")
        box, score, category = row["xyxy"], row["score"], row["class_id"]
        if (
            not isinstance(box, list) or len(box) != 4
            or any(isinstance(v, bool) or not isinstance(v, Real) for v in box)
            or isinstance(score, bool) or not isinstance(score, Real)
            or not np.isfinite(score) or not 0 <= score <= 1
            or isinstance(category, bool) or not isinstance(category, Integral)
            or category != parent["ideal_box"]["class_id"]
        ):
            raise ValueError("invalid public output metadata or box")
        normalized.append({
            "frame": row["frame"], "track_id": row["track_id"],
            "xyxy": [float(v) for v in box], "score": float(score), "class_id": int(category),
        })
    by_frame = _validated_rows(normalized, parent)
    # Preserve caller order for canonical matching/tie semantics, not GT order.
    for row in normalized:
        row["frame"], row["track_id"] = int(row["frame"]), int(row["track_id"])
    return normalized, by_frame


def _diagnostics(scene: BoxGateInputs, by_frame: dict, parent: dict) -> dict:
    """One canonical CLEAR-MOT correspondence, retained across all strata."""
    from visiontrack.eval.mot import MotAccumulator

    projection = _projection(scene, parent)
    accumulator = MotAccumulator(iou_threshold=parent["diagnostics"]["gt_match_iou"])
    gt_ids = np.array(scene.object_ids, dtype=np.int64)
    samples, failures = [], []
    phase_fp = dict.fromkeys(PHASES, 0)
    regions = parent["diagnostics"]["regions_y"]
    for frame in range(parent["frame_grid"]["frames"]):
        public = by_frame[frame]
        events = accumulator.update(
            gt_ids, scene.ideal_boxes[frame],
            np.array([row["track_id"] for row in public], dtype=np.int64),
            np.array([row["xyxy"] for row in public], dtype=np.float64).reshape(-1, 4),
        )
        failures.extend(asdict(event) for event in events)
        phase = _phase(frame, parent)
        phase_fp[phase] += sum(e.event_type == "false_positive" for e in events)
        event_ids = {
            name: {e.gt_id for e in events if e.event_type == name}
            for name in ("miss", "id_switch", "fragmentation")
        }
        anchors = {
            row["track_id"]: _world_anchors(np.array(row["xyxy"]), projection) for row in public
        }
        used = set()
        for index, identity in enumerate(scene.object_ids):
            truth = scene.world_contacts[frame, index]
            observed = _world_anchors(scene.observed_boxes[frame, index], projection)
            match, tracked = None, None
            if identity not in event_ids["miss"]:
                # Same pinned evaluator correspondence as traffic-v1, no second
                # matcher and no truth ID injected into the supplied public rows.
                match = int(accumulator._last_hyp[identity])
                if match not in anchors or match in used:
                    raise ValueError("invalid canonical evaluator correspondence")
                used.add(match)
                tracked = {name: _error(anchors[match][name], truth) for name in ANCHORS}
            samples.append({
                "frame": frame, "object_id": identity,
                "region": _region(float(truth[1]), regions), "phase": phase,
                "matched_track_id": match, "id_switch": identity in event_ids["id_switch"],
                "fragmentation": identity in event_ids["fragmentation"],
                "observation_error": {name: _error(observed[name], truth) for name in ANCHORS},
                "matched_track_error": tracked,
            })
    metrics = accumulator.result()
    overall = _summary(samples, metrics.false_positives)
    if (
        overall["matched_object_frames"] != metrics.true_positives
        or overall["missed_object_frames"] != metrics.false_negatives
        or overall["id_switches"] != metrics.id_switches
        or overall["fragmentations"] != metrics.fragmentations
        or sum(phase_fp.values()) != metrics.false_positives
    ):
        raise ValueError("diagnostics disagree with canonical evaluator")
    return {
        "overall": overall, "frame_count": metrics.num_frames,
        "iou_threshold": parent["diagnostics"]["gt_match_iou"],
        "mean_matched_box_iou": metrics.motp if metrics.true_positives else None,
        "by_phase": {
            phase: _summary([s for s in samples if s["phase"] == phase], phase_fp[phase])
            for phase in PHASES
        },
        "by_true_region": [
            {
                "region": index, "y_bounds": bounds,
                "upper_inclusive": index == len(regions) - 1,
                "summary": _summary([s for s in samples if s["region"] == index], None),
                "by_phase": {
                    phase: _summary(
                        [s for s in samples if s["region"] == index and s["phase"] == phase], None,
                    ) for phase in PHASES
                },
            } for index, bounds in enumerate(regions)
        ],
        "samples": samples, "failures": failures,
    }


def _projection(scene: BoxGateInputs, parent: dict) -> GroundProjection:
    name = next(c["projection"] for c in parent["conditions"] if c["id"] == scene.condition)
    return GroundProjection(np.array(parent["projection"][name]))


def score_development(scene: BoxGateInputs, rows: list[dict]) -> dict:
    """Score supplied rows, retaining all 37 inherited endpoints and nulls.

    No variant selector, tracker execution, acceptance verdict or file writes.
    Source verification binds the canonical evaluator to the registered baseline.
    A later replay adapter must establish the actual producer/configuration.
    """
    registration, hashes, parent = _validated_input(scene)
    return _score(scene, rows, registration, hashes, parent)


def _score(scene, rows, registration, hashes, parent) -> dict:
    """Shared arithmetic after split-specific regeneration; never runs a tracker."""
    normalized, by_frame = _public_rows(rows, parent)
    baseline = _verify_tree(ROOT, registration["baseline_revision"])
    _check_import_origins()
    projection = _projection(scene, parent)
    truth = extract_crossings([
        AnchorSample(frame, identity, *scene.world_contacts[frame, index])
        for frame in range(len(scene.frames))
        for index, identity in enumerate(scene.object_ids)
    ])
    record = {
        "format": f"visiontrack.box-gate-{scene.split}-scoring/v1",
        "protocol_id": registration["protocol_id"], "protocol_hashes": hashes,
        "input": scene.manifest(), "public_rows_sha256": _sha(normalized),
        "source": baseline,
        "row_origin": "caller supplied; producer and variant not established by scorer",
        "tracker_executed_by_scorer": False, "heldout_opened_by_scorer": False,
        "crossing": {
            name: score_crossings(truth, extract_crossings(_anchor_samples(
                normalized, projection, name,
            ))) for name in parent["anchors"]
        },
        "diagnostics": _diagnostics(scene, by_frame, parent),
        "limitations": [
            "Numeric toy geometry, not measured traffic or real detector performance.",
            "Crossing subrecords retain the inherited parent recipe ID/hashes, not a new run ID.",
            "Matched localization is conditional; unmatched positions/timing remain undefined.",
            "Supplied output rows are not proof of tracker execution or an ablation benefit.",
        ],
    }
    record["endpoints"] = _metrics(record)
    if len(record["endpoints"]) != 37:
        raise ValueError("inherited endpoint set changed")
    _check_import_origins()
    if _verify_tree(ROOT, registration["baseline_revision"]) != baseline:
        raise ValueError("baseline source changed during scoring")
    record["scoring_sha256"] = _sha(record)
    return record
