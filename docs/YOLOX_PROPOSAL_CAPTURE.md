# YOLOX proposal capture: preserve information before suppression

Implemented **2026-11-04 in the checkout**, after the
[localization research decision](LOCALIZATION_RESEARCH_DECISION.md). This API is
not in published `visiontrack-mot` 0.5.1. No tracker, Kalman, browser or C++ behavior
is changed, and no new release is implied.

## What we built and why

A detector can propose several overlapping rectangles, then discard all but one.
Ordinary `detect(frame)` returns the surviving detections. The new, explicit
`detect_with_proposals(frame)` returns those same detections plus a bounded
record of the proposals and the decoder's decisions for that frame.

This lets us investigate whether the discarded information helps predict how
wrong a location is. It does **not** identify a real person, estimate uncertainty,
improve accuracy, or establish a new method. Suppression groups can mix objects
or classes; correlated rectangles are not independent measurements.

## API

With a locally available compatible model and an already permitted RGB frame:

```python
from visiontrack.detection.yolox_onnx import YoloxDetector

model = YoloxDetector("local-model.onnx", class_filter={0})
detections, capture = model.detect_with_proposals(frame_rgb, max_proposals=4096)
observations = tracker.update(detections)  # unchanged ordinary Detection objects

print(capture.total_proposals, capture.truncated, capture.omitted_count)
for proposal in capture.records:
    print(proposal.proposal_index, proposal.status, proposal.group_complete)
```

One inference call produces both results. There is no callback, background
capture, file write, CLI flag or automatic retention on the detector. Callers
choose whether to retain each result. A normal video pipeline still calls
`detect` and allocates no proposal recorder.

`max_proposals` is a non-negative Python integer; booleans are rejected before
inference. Zero retains counts only. The default is 4096; the bound applies to
**retained diagnostic rows**, not raw model tensors, NMS work, total process
memory, or caller accumulation across frames. Capture uses temporary eligible
row indices for this frame; those are not retained in the returned object.

## Exact interpretation

- Original index means row order after removing the batch dimension and applying
  the existing supported layout normalization, before threshold filtering. Both
  row/column layouts, decoded and raw-grid exports retain that convention.
- Coordinates are unclipped `xyxy` in original-image pixels: decoded network
  coordinates divided by the recorded letterbox scale. Padding is bottom/right,
  with origin top-left. Raw tensor shape, actual transposition, whether grid decode
  was applied, input size and strides are recorded. The existing heuristic that
  chooses grid decoding is unchanged; its flag is not proof of model provenance.
- Score remains objectness times the largest class score. The record includes
  both factors, winning class and configured confidence/IoU thresholds.
- The existing greedy NMS is **class-agnostic**. Score order is NumPy's existing
  `argsort()[::-1]`, including ties; overlap equal to the IoU threshold survives.
  Class filtering still happens **after** NMS. A box of a filtered-out class can
  therefore suppress another class before being removed itself.
- Status is `confidence_filtered`, `nms_suppressed`, `class_filtered`, or
  `returned`. Each NMS group consists of a winner and only the rows it directly
  suppressed. It is not a transitive overlap cluster or a verified object group.
  A returned row's `output_index` links to the ordinary detections list.
- Counts cover **all** model proposals, even if no records fit the limit:
  total = confidence-filtered + NMS-suppressed + class-filtered + returned;
  NMS-kept = class-filtered + returned.

## Truncation and missing information

The capture retains the first `max_proposals` original rows. This deterministic
prefix is spatial/order biased and must not be treated as a representative
sample. It can omit good detections or an entire group. `truncated` and
`omitted_count` make frame-level omission explicit.

Every retained eligible row records its original group winner index, total group
size, captured group size and `group_complete`. A suppressed row may point to a
winner outside the prefix. Even a retained winner has an incomplete group if
some of its victims are omitted. Below-confidence-threshold rows have no NMS
group: completeness is `None`, not `True` or a zero-variance measurement.

Records and coordinates are immutable scalar/tuple copies, detached from model
arrays. `capture.to_dict()` returns detached plain values with explicit
truncation and per-record completeness. To serialize locally, use
`json.dumps(capture.to_dict(), allow_nan=False)`; non-finite values from a model
are not silently sanitized. The schema is `visiontrack.yolox-proposals/v1`.
There are no image bytes, embeddings, reference labels or cross-frame identity
records in it. This diagnostic is not a sealed Lab evidence bundle: model-byte,
source, frame and environment provenance must be recorded separately for a study.

## Validation and next gate

Authored tensors and fake sessions check thresholds, ties, cross-class and direct
suppression, class filtering, empty results, both layouts, grid decoding,
letterboxing, immutable/no-history behavior, truncation (including absent group
winners), and multi-frame tracking/reset parity. Wheel/source installation also
exercises the API without ONNX Runtime. The local non-slow suite passes 1,446
tests, including 35 capture cases. A separate generated-tensor replay compares
800 detection calls and 800 tracker updates against the pre-change decoder
(`b4f3668`): exact agreement, including capture off/on. These are engineering
checks, not localization-quality or real-time results.

Next, measure the added storage/compute on fixed permitted inputs and prepare the
[offline signal audit](LOCALIZATION_RESEARCH_DECISION.md#research-gate-after-capture):
compare proposal information against score/class/size baselines with checked
reference labels and explicit coverage. Incomplete or singleton groups must not
become automatic certainty. If no reliable incremental signal is found, stop
before changing association. RoundaboutHD intake remains a separate pending route.
