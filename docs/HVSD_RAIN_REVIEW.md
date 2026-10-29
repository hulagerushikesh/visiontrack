# HVSD rain: owner event review and first pipeline comparison

Checkpoint: **2026-10-29**. This is an **exploratory development** check of
one 194-frame, 6.4-second publisher-hosted clip, not a held-out evaluation.
It follows the [source/intake check](PUBLIC_TRAFFIC_VIDEO_FEASIBILITY.md).
No video frames, weights, or raw review downloads are committed.

## Source-only review intake

The owner used the local source-only page and downloaded six JSON files. The
review task was to mark vehicles on the **lower road** whose center crossed the
vertical x=500 line **left to right**, with `clear` or `uncertain` judgment.
The page showed no model outputs. `experiments/hvsd_rain_review.py` validated
each file against the pinned source SHA-256, 194-frame count, line/rubric,
review role, and event schema. It rejected no submitted file. The owner-local
audit receipt and original downloads remain outside Git in
`../visiontrack-walkthrough/traffic-hvsd-v1/` and `~/Downloads/`.

Six submitted records reduce to **five distinct clear marks** at zero-based
frames **27, 37, 57, 92, 160**. Frame **57** was downloaded twice with identical
content; it is one mark, not two independent reviewers or two vehicles. There
were no `uncertain` marks. The owner confirmed in chat that they reviewed
**all 194 frames** and marked every crossing they noticed. The JSON files do
not independently certify that negative-frame coverage or provide dense boxes,
object IDs, vehicle identity, or the reason for any possible omission. The browser page's
`owner_independent_scene_pass` label documents its source-only presentation;
it is not a second independent reviewer. The local audit records the owner's
full-frame attestation separately from machine-verifiable file checks.

## Frozen pipeline observation

The same YOLOX nano model, road-class filter and `ByteTracker()` defaults were
run again without tuning. The canonical per-frame count/ID receipt exactly
matched the earlier smoke run:
`0125e1e9644e0df9fb36d3c1353c8e328dd7fc1e03d8117299af0e0afe4f49c6`.
The comparison uses **only confirmed public track outputs**. It emits a
left-to-right event when the center of the same public ID moves from x<500 to
x>=500 in **consecutive frames**, with line-interpolated center y in 205..432.
No gap filling, ID joining, detector-only box, or retrospective correction is
allowed. This rule was specified before inspecting the geometric result.

The rule emitted **one** model event: public track ID 3, between frames 27–28,
at interpolated frame 27.66 and y=278.51. It falls next to the owner's frame
27 mark. There was **no public-output line-crossing event** near the other four
marked frames (37, 57, 92, 160). That is a useful failure lead, not a claim
that four physical vehicles were missed: marks need timing/coverage review, a
true vehicle can be detected without becoming a confirmed public track, and
the event rule excludes fragmented tracks and nonconsecutive observations.
The five owner marks are event references, not dense identity truth; no IDF1,
HOTA, MOT, detection recall, or real-world counting accuracy is calculated.

The same frozen rerun logged detector proposals and internal track state within
125 pixels of the line over each mark's ±4-frame window. These are candidate
diagnostics, not object-to-object matches:

| Owner mark | Near-line evidence | Bounded interpretation |
| ---: | --- | --- |
| 27 | Detector proposals and confirmed public ID 3 span the line | One public crossing agrees within one frame. |
| 37 | Detector proposals are intermittent for a second vehicle; tentative ID 4 appears after the line | Possible detector/lifecycle gap; continuing public ID 3 is the earlier vehicle and must not be counted again. |
| 57 | Detector centers move through x=500; tentative IDs 9 and 10 appear while public ID 6 is farther right | A proposal exists, but no confirmed public ID crosses the line. |
| 92 | No retained road-class detection, public track or internal track near the line in frames 88–96 | Detector-stage gap is the leading explanation, conditional on the mark's timing. |
| 160 | Repeated detector proposals move through the line; tentative IDs 13–18 start and expire | Lifecycle/association instability is visible; no public crossing is emitted. |

No tracker settings are changed from these observations. Exact object
correspondence and crossing frame should be checked on source imagery before
making a stronger causal claim. A candidate detection is not automatically
the owner-marked vehicle.

## Reproduce privately

```bash
python -m experiments.hvsd_rain_review ~/Downloads/hvsd-rain-review*.json \
  --owner-attested-full-frame-pass \
  --video ../visiontrack-walkthrough/traffic-hvsd-v1/video/rain.mp4 \
  --model models/yolox_nano.onnx \
  --output ../visiontrack-walkthrough/traffic-hvsd-v1/rain-review-audit.json
```

The command fails closed on source/schema mismatches and on a changed
per-frame smoke receipt. Without `--video` and `--model` it only validates and
deduplicates the owner marks. If filenames or the set of downloads change,
record the exact file hashes before comparing again.

## Next decision

The owner has confirmed a full-frame pass. A second, focused source review
should adjudicate the **crossing timing and vehicle class** at frames 37, 57,
92 and 160; record ambiguity as `uncertain`, not silently remove a mark. The
four bounded windows have now been inspected for candidate detector and track
state evidence, but exact object correspondence and causal attribution remain
open. This clip remains development data.
A future outcome study needs a different permitted source with independent
truth and a prospectively frozen decision/split before candidate comparison.
