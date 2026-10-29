# HVSD rain: owner event review and bounded crossing diagnosis

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

## Source-window adjudication

On 2026-10-29, the assistant inspected the locally decoded source frames around
each mark, using the 704×432 images produced by the source-only review page.
The source clip and all 194 extracted frames remain outside Git. Frame numbers
below are **zero-based**; image `000038.png` is frame 37. This focused visual
pass is a second look at the same evidence, **not** independent human ground
truth or a dense annotation. The owner has attested a complete 194-frame pass;
the assistant inspected only these windows.

| Owner mark | Source observation and timing | Frozen pipeline at the apparent crossing | Assessment |
| ---: | --- | --- | --- |
| 27 | A lower-road vehicle is visibly near the x=500 line in frames 27–28. | Confirmed public ID 3 crosses between 27–28. | The one rule-defined event aligns with this mark. |
| 37 | A dark lower-road vehicle moves through the line over roughly frames 36–39. The white vehicle and public ID 3 farther up/right are separate candidates. | Near-line proposal center x=478.9 at 35; none retained at 36–38; center x=504.6 at 39, where tentative ID 4 begins. | A proposal gap spans the apparent crossing and the new tentative ID begins after it. No matching public event can be emitted. Exact object linkage is still an inference from proximity and appearance. |
| 57 | A dark/red lower-road car moves across the line at approximately frames 57–58. | Proposal centers x=494.8 (score 0.577) at 57 and x=500.3 (0.597) at 58; both are below the default **0.6 new-track threshold**. Tentative ID 10 starts at x=507.1 at 59. Public ID 6 is already farther right. | The detector proposed a plausible crossing, but no public track existed on its two bracketing frames. This is a threshold/lifecycle lead, not proof that changing the threshold would improve outcomes. |
| 92 | A dark lower-road vehicle visibly passes the line around frames 91–94. | No retained near-line road-class proposal or track in frames 88–96. | The detector stage is the leading gap for this apparent crossing. The absence is under the pinned model/filter; it does not establish why the model failed. |
| 160 | A white boxy vehicle moves through the line around frames 161–162. Its `car` versus `van` visual category is ambiguous. | Proposal centers x=493.9 at 161 and x=501.4 at 162; the nearby internal IDs change from tentative 16 to tentative 17, with no public output. | Proposals exist, but association/confirmation did not preserve a public ID through the line. A targeted gate trace below identifies a rejected candidate pairing. |

The default tracker requires **three consecutive matched frames** to confirm a
tentative track; its high-score cutoff is 0.5 and new-track cutoff is 0.6.
These are explanatory configuration facts, not proposed new defaults. The
source view supports the five marks as plausible visible vehicle crossings,
with a class ambiguity at 160. It does **not** establish that the near-line
proposals are the same physical objects in every frame, or that all unmarked
crossings are true negatives. We therefore retain all five owner marks and do
not calculate recall or claim a causal tracker defect from this short clip.

No tracker setting is changed. The next controlled question would separate
detector failure from track initiation/association failure on a different,
independently labeled source with a frozen protocol. The rain clip remains
development-only evidence.

### Targeted tentative-association trace

`experiments/hvsd_rain_gate_trace.py` observes the tracker's stage-three
tentative/high-score pairing calls around the five marks without changing any
match results. It verifies the same source/model hashes and the same frozen
per-frame public-output receipt. The full metadata-only trace is stored at
`../visiontrack-walkthrough/traffic-hvsd-v1/rain-gate-trace.json`, outside Git.
For the white-vehicle window, two candidate pairs are especially informative:

| Frame | Tentative ID → proposal center x | IoU (minimum 0.3) | Kalman distance² (maximum 9.488) | Actual match |
| ---: | --- | ---: | ---: | --- |
| 158 | 13 → 471.9 | 0.5227 | 35.227 | Rejected |
| 162 | 16 → 501.4 | 0.5561 | 33.107 | Rejected |

Both pairs have the same COCO class and pass the IoU gate; the squared
Mahalanobis distance fails the active gate. This explains why **those candidate
associations** did not advance tentative tracks. It does not independently
prove the candidate boxes represent the same physical van in both frames, or
that disabling/relaxing the gate would be safe. In the prior controlled
[box-gate experiment](BOX_GATE_FINDINGS.md), a gate-off variant produced safety
violations, so this short rain clip does not justify a configuration change.

## Reproduce privately

```bash
python -m experiments.hvsd_rain_review ~/Downloads/hvsd-rain-review*.json \
  --owner-attested-full-frame-pass \
  --video ../visiontrack-walkthrough/traffic-hvsd-v1/video/rain.mp4 \
  --model models/yolox_nano.onnx \
  --output ../visiontrack-walkthrough/traffic-hvsd-v1/rain-review-audit.json

python -m experiments.hvsd_rain_gate_trace \
  --video ../visiontrack-walkthrough/traffic-hvsd-v1/video/rain.mp4 \
  --model models/yolox_nano.onnx \
  --output ../visiontrack-walkthrough/traffic-hvsd-v1/rain-gate-trace.json
```

The command fails closed on source/schema mismatches and on a changed
per-frame smoke receipt. Without `--video` and `--model` it only validates and
deduplicates the owner marks. If filenames or the set of downloads change,
record the exact file hashes before comparing again.

## Next decision

The owner has confirmed a full-frame pass, and the four unmatched windows now
have a focused source and pipeline diagnosis. The white vehicle at frame 160
remains visually ambiguous between `car` and `van`; the original mark is
preserved. A tentative pair's gate rejection has been reproduced, while exact
physical object correspondence and the effect of any alternative gate remain
open. A future outcome study needs a different permitted source with
independent truth and a prospectively frozen decision/split before any
candidate comparison.
