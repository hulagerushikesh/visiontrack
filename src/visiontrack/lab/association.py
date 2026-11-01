"""One selected pair's actual gates and assignment in an exact saved-run replay.

No alternative matching, counterfactual intervention or physical identity claim.
The matrices come directly from the production tracker, before its one solver call.
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from .contracts import sha256_json
from .initiation import _STAGES, _InitiationObserver, _replay_initiation


class _AssociationObserver(_InitiationObserver):
    def __init__(self, config, *, track_id, detection_index, **kwargs):
        super().__init__(config, **kwargs)
        self.target_track = track_id
        self.target_detection = detection_index
        self.stages: list[dict[str, Any]] = []

    def _key(self, detection):
        return self._detection_keys[self._indices[id(detection)]]

    def _match(self, tracks, dets, iou_thresh, gate):
        if self._capture:
            if self._stage >= len(_STAGES):
                raise ValueError("diagnostic association-stage contract changed")
            self._active_stage = {
                "stage": _STAGES[self._stage],
                "track_count": len(tracks), "detection_count": len(dets),
                "track_offered": any(t.track_id == self.target_track for t in tracks),
                "detection_offered": any(self._key(d) == self.target_detection for d in dets),
                "pair": None,
            }
            self.stages.append(self._active_stage)
        return super()._match(tracks, dets, iou_thresh, gate)

    def _association_observer(
        self, cost, max_cost, tracks, dets, ious, iou_thresh,
        class_mismatch, gating_d2, gate_thresh, result,
    ):
        # Observe only the selected pair after the real solver has returned;
        # never retain a quadratic matrix or solve a diagnostic substitute.
        if not self._capture:
            return
        stage = self._active_stage
        if not (stage["track_offered"] and stage["detection_offered"]):
            return
        ti = next(i for i, t in enumerate(tracks) if t.track_id == self.target_track)
        di = next(i for i, d in enumerate(dets) if self._key(d) == self.target_detection)
        numbers = [float(ious[ti, di]), float(iou_thresh), float(cost[ti, di]), float(max_cost)]
        distance = None if gating_d2 is None else float(gating_d2[ti, di])
        if not all(math.isfinite(n) for n in numbers + ([] if distance is None else [distance])):
            raise ValueError("non-finite association diagnostic; no explanation emitted")
        failures = []
        if ious[ti, di] < iou_thresh:
            failures.append("iou")
        if class_mismatch is not None and class_mismatch[ti, di]:
            failures.append("class")
        if gate_thresh is not None and distance is not None and distance > gate_thresh:
            failures.append("mahalanobis")
        accepted = {(int(t), int(d)) for t, d in result[0]}
        track_match = next((d for t, d in accepted if t == ti), None)
        detection_match = next((t for t, d in accepted if d == di), None)
        selected = (ti, di) in accepted
        eligible = bool(cost[ti, di] <= max_cost)
        outcome = (
            "selected" if selected else "blocked_by_gate" if failures else
            "above_cost_limit" if not eligible else "eligible_not_selected"
        )
        stage["pair"] = {
            "predicted_xyxy": [float(v) for v in tracks[ti].to_xyxy()],
            "track_class_id": int(tracks[ti].class_id),
            "iou": numbers[0], "minimum_iou": numbers[1],
            "class_gate_enabled": self.cfg.class_aware,
            "class_mismatch": bool(class_mismatch is not None and class_mismatch[ti, di]),
            "mahalanobis_squared": distance,
            "mahalanobis_limit": None if gate_thresh is None else float(gate_thresh),
            "failed_gates": failures,
            "solver_cost": numbers[2], "maximum_cost": numbers[3],
            "cost_eligible": eligible, "outcome": outcome,
            "track_matched_detection_index": (
                None if track_match is None else self._key(dets[track_match])
            ),
            "detection_matched_track_id": (
                None if detection_match is None else int(tracks[detection_match].track_id)
            ),
        }


def build_association_explanation(
    bundle: str | Path, *, variant: str, frame: int, track_id: int, detection_index: int,
) -> dict[str, Any]:
    """Explain one original detection key and pre-existing track in one frame.

    Full experiment warm-up/replay and exact saved-output SHA checks are shared
    with the initiation diagnostic. Only three stage summaries and at most one
    offered pair are exported. Nothing is written; no footage/model is opened.
    """
    if (type(frame) is not int or frame < 0 or type(track_id) is not int or track_id < 1
            or type(detection_index) is not int or detection_index < 0):
        raise ValueError("require integer frame >= 0, track ID >= 1 and detection index >= 0")
    trace, observer = _replay_initiation(
        bundle, variant=variant, start=frame, end=frame + 1,
        observer_type=_AssociationObserver,
        observer_options={"track_id": track_id, "detection_index": detection_index},
    )
    observed = trace["frames"][0]
    detection = next((d for d in observed["detections"]
                      if d["detection_index"] == detection_index), None)
    if detection is None:
        raise ValueError("detection index does not exist in the selected source frame")
    if not any(stage["track_offered"] for stage in observer.stages):
        raise ValueError("track was not active before association in the selected frame")
    if any(s["track_offered"] and s["detection_offered"] and s["pair"] is None
           for s in observer.stages):
        raise ValueError("production association observation missing; no explanation emitted")
    result = {key: trace[key] for key in (
        "experiment_id", "source_id", "variant", "run_id", "detection_sha256", "track_sha256",
        "replay_frame_range", "config", "producer", "public_output_parity",
        "accuracy_claim", "physical_identity_verified",
    )}
    result.update({
        "schema": "visiontrack.association-explanation/v1",
        "frame_index": frame, "track_id": track_id, "detection_index": detection_index,
        "detection": detection, "stages": observer.stages,
        "limits": [
            "Offered pairs use actual production matrices and the single production solver result.",
            "Not offered is different from failing a gate; scores and earlier stages limit inputs.",
            "Eligible but not selected does not prove a local or global counterfactual cause.",
            "A pair passing gates does not establish physical identity or a correct match.",
            "Only one frame/pair is exported; the whole saved experiment is replayed read-only.",
        ],
    })
    result["explanation_id"] = sha256_json(result)
    return result
