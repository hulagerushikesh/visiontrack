"""Experimental crossing scorer for clips with per-frame box annotations."""

from __future__ import annotations

import numpy as np

from visiontrack.core.assignment import linear_assignment
from visiontrack.core.geometry import iou_matrix

MIN_IOU = 0.30


def _event_key(event):
    return event["frame"], event["track_id"], event["direction"]


def _overlap(predicted, reference):
    if predicted is None or reference is None:
        return None
    return float(iou_matrix(np.asarray([predicted]), np.asarray([reference]))[0, 0])


def _assign(candidates, prediction_count, reference_count):
    # One dummy column per prediction lets any row remain unmatched. The
    # penalty exceeds the largest possible total change in IoU, so gaining
    # a match always takes priority over improving overlap.
    penalty = min(prediction_count, reference_count) + 1
    costs = np.full((prediction_count, reference_count + prediction_count), penalty + 1.0)
    costs[:, reference_count:] = penalty
    for pi, ri, detail in candidates:
        costs[pi, ri] = 1.0 - detail["iou"]
    rows, cols = linear_assignment(costs)
    selected = set(zip(rows, cols, strict=True))
    return [(pi, ri, detail) for pi, ri, detail in candidates if (pi, ri) in selected]


def score_spatial_crossings(
    predictions,
    references,
    track_boxes,
    episode_boxes,
    *,
    frames_before,
    frames_after,
    stride,
):
    """Score one gate. Reference track IDs are uninterrupted annotation episode IDs.

    Box mappings use (source frame, track or episode ID) keys and xyxy boxes
    in a shared pixel coordinate system. Event frames and window widths are in
    source-frame units, and stride is the interval between retained frames.
    """
    if frames_before < 0 or frames_after < 0 or stride < 1:
        raise ValueError("window extents must be nonnegative and stride must be positive")

    predictions = sorted(predictions, key=_event_key)
    references = sorted(references, key=_event_key)
    for group in (predictions, references):
        if len({_event_key(event) for event in group}) != len(group):
            raise ValueError("duplicate event in a single gate")

    audit, eligible, near = [], [], []
    for pi, prediction in enumerate(predictions):
        frame = prediction["frame"]
        predicted_box = track_boxes.get((frame, prediction["track_id"]))
        for ri, reference in enumerate(references):
            delta = frame - reference["frame"]
            if prediction["direction"] != reference["direction"]:
                continue
            if not -frames_before - stride <= delta <= frames_after + stride:
                continue
            on_time = -frames_before <= delta <= frames_after
            reference_box = episode_boxes.get((frame, reference["track_id"]))
            iou = _overlap(predicted_box, reference_box)
            detail = {
                "predicted": prediction,
                "reference": reference,
                "frame_delta": delta,
                "iou": iou,
                "within_window": on_time,
            }
            audit.append(detail)
            if iou is not None and iou >= MIN_IOU:
                (eligible if on_time else near).append((pi, ri, detail))

    matches = _assign(eligible, len(predictions), len(references))
    matched_predictions = {pi for pi, _, _ in matches}
    matched_references = {ri for _, ri, _ in matches}
    near = [
        (pi, ri, detail)
        for pi, ri, detail in near
        if pi not in matched_predictions and ri not in matched_references
    ]
    # An offset attribution is diagnostic. Require a unique candidate for
    # each endpoint among all remaining supported pairs, including on-time
    # alternatives. Leave competing explanations unresolved.
    diagnostics = [
        detail
        for pi, ri, detail in near
        if sum(pi == other_pi or ri == other_ri for other_pi, other_ri, _ in eligible + near) == 1
    ]
    return {
        "matches": [detail for _, _, detail in matches],
        "unmatched_predictions": [
            event for pi, event in enumerate(predictions) if pi not in matched_predictions
        ],
        "missed_references": [
            event for ri, event in enumerate(references) if ri not in matched_references
        ],
        "offset_diagnostics": diagnostics,
        "candidate_audit": audit,
    }
