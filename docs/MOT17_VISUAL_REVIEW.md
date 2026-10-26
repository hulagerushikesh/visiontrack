# First real-pixel review: what the scored switch does and does not show

**2026-10-26 update:** the owner delegated the technical review to the assistant;
no separate reviewer is available. The [AI-assisted case note and no-change
recommendation](MOT17_AI_REVIEW_DECISION.md) now record the bounded reinspection.
Independent human/reference validation remains **deferred, not completed**. The
owner only confirmed page/image/frame controls, not trajectory interpretation.
Exploratory documentation can proceed without requiring their manual review;
the historical checkpoint and stronger validation limits below are retained.

Checkpoint: **2026-10-25**. We now have the actual **22 source images, frames
36–57**, for the already selected MOT17-04-FRCNN event. Bounded acquisition,
source correspondence, an **AI-assisted preliminary visual inspection** and a
private staged review page are complete. **Independent human review is not.**
No tracker, threshold, reference label, evaluator, old receipt or C++ code changes.

Subsequent [saved prior-context audit](MOT17_PRIOR_CONTEXT.md): in every public
frame 3–35, 19 has IoU >=0.5 with 85 alone, not 89. This supplies earlier
geometric history, but no earlier pixels or independent physical correspondence.
The preliminary visual observations below and the review gate remain unchanged.

## The finding in plain language

The images show two nearby pedestrians moving in opposing directions, with
substantial overlap in the early part of this short window. One light-topped
figure moves away/up-left; another light-topped figure moves toward/down-right.
In the later, more separated frames, published reference **85** encloses the
away-moving figure and **89** the approaching figure.

The saved **19** box increasingly aligns with the approaching figure/reference
89. Public box **31** first appears at 54 over the away-moving figure/reference
85. These are observations of boxes and anonymous scene motion, not recognition
of who the pedestrians are. At the start, one detector/output box overlaps both
reference extents; this window alone does not establish which physical figure
19 originally represented before frame 36.

This makes the earlier distinction tangible: **the scorer recording “85 changed
from 19 to 31” is not, by itself, proof that a person left, was forgotten, and
returned.** The prior actual-call trace already establishes that 19 stayed updated
and public throughout. The preliminary image inspection is consistent with
overlapping-object ambiguity and later separation, not an expired-ID recovery.
It does not independently establish the earlier physical correspondence, label
correctness or a causal explanation of the entire failure.

The inspecting assistant had already seen the numerical diagnosis. Its three-pass
view is **not a blinded study, a second independent implementation or a human
adjudication**. Keep uncertainty rather than turning this into an accepted fix.

## What we acquired, and under which boundary

The [official MOT17 archive page](https://motchallenge.net/data/MOT17/) provides
the training ZIP and lists CC BY-NC-SA 3.0, with possible additional source
conditions. The [licence notice](https://creativecommons.org/licenses/by-nc-sa/3.0/)
does not guarantee every privacy/publicity permission. This is a bounded
**local, non-commercial research admission**, not legal clearance for commercial
deployment, biometric recognition or public image redistribution. No additional
sequence-source link is listed for this sequence on the archive page.

Attribution: MOTChallenge; Milan et al.,
[MOT16: A Benchmark for Multi-Object Tracking (2016)](https://arxiv.org/abs/1603.00831).
Dataset material does not inherit our software's MIT licence. Do not upload these
images to the public website, Git, email or an external reviewer service.

The fixed range was selected by the corrected first-event rule **before** image
inspection, not selected for an attractive visual outcome. All 22 frames were
acquired; there was no search for a better sequence or alternate event.

| Acquisition fact | Actual result |
| --- | --- |
| Official source | `https://motchallenge.net/data/MOT17.zip` |
| Full ZIP size | 5,860,214,001 bytes; not downloaded in full |
| Successful bounded transfer | **9,783,379 bytes / 79 range requests**, including ZIP metadata and annotation checks |
| Saved source JPEGs | **22 / 5,115,254 bytes**, each 1,920 × 1,080 |
| Annotation correspondence | Full-ZIP `seqinfo.ini`, detections and GT exactly equal the previously admitted official label members |
| Integrity | HTTPS, fixed strong ETag, exact partial-response ranges, ZIP CRCs and local per-image SHA-256 receipts |
| Remaining authenticity limit | No full-archive SHA-256 or independently published per-image hashes were obtained |
| Human reviewer / changed tracker | None / none |

The acquisition tool uses an offline default preview, requires `--write`, caps
transfer at 32 MiB / 128 requests and refuses full-response fallback, redirects,
changed ETags, oversized/duplicate selected members or annotation mismatches.
It reads only selected archive entries; it does not call `extractall` or run
models. It rejects an output inside the VisionTrack repository.

An initial intake stopped before any images were saved: the full ZIP has a
`MOT17/` root prefix, unlike the labels-only ZIP. Its method/failure receipt is
retained in `.../mot17-visual-review-iL6MiU/frames/`. After inspecting the actual
archive inventory, the corrected acquisition used a new `verified-frames/`
directory. This was an acquisition-path correction, not a tracker trial or
selective retry of a research outcome.

## Local reviewer handoff: no installation or recording

The completed packet is outside Git:
`../visiontrack-walkthrough/mot17-visual-review-iL6MiU/`.
The final page is **`review-final/index.html`**, next to `verified-frames/`.

1. Open `review-final/index.html` directly in a normal browser from Finder.
   Keep the sibling image folder in place. No login, terminal, webcam or upload.
2. In **Scene only**, step through 36–57 and write what you can/cannot distinguish.
   Do this before reading another reviewer's conclusions, including the findings
   above. An uninformed second reviewer should receive the private page, not this
   interpretation first; sharing the pixels with anyone else needs its own review.
3. Select **Reference boxes**, then optionally **Detail view**. Do the two
   labels consistently cover distinct figures? Note exact uncertain frames.
4. Select **Saved tracker boxes**. Follow 19/31; optionally reveal supplied
   detections. These are original saved outputs, not a fresh tracker run.
5. Write observations or **“uncertain”** for each pass, use a non-identifying alias,
   then explicitly download notes. Keep disagreement; do not edit source labels.

Notes remain in browser memory until downloaded. There are no external assets,
requests, telemetry, uploads or automatic winner selection. The page is a
lightweight staged aid, not secure blinding: all overlays exist in its local
source. It records the scene/reference notes present before their first overlay
transition, while retaining later edits separately. A blank early snapshot remains
blank; the tool does not manufacture a completed blind pass or verified reviewer.

Images were rechecked against the receipt at page construction. The browser
checks dimensions but does **not** re-hash relative image files at display time;
keep the sealed folder unchanged. The fixed detail crop changes only the view,
not any label, source image, timing or metric. Missing images produce an error.

The automated browser-control surface rejects local-file navigation. We did not
bypass that restriction. Offline DOM/canvas doubles check initial concealment,
pass switching, original box drawing, stale image handling, dimension errors and
explicit note download. **This is not an actual-browser visual QA pass**; owner
opening/interaction feedback is still needed. Static diagnostic crops of all 22
frames were inspected directly for the preliminary analysis above.

## Research decision and next gates

- [x] Obtain the fixed local source window with an explicit limited admission.
- [x] Verify annotation/source correspondence and preserve all image receipts.
- [x] Inspect every frame's local diagnostic crop, separating imagery, references
      and unchanged public outputs; record the preliminary/anchored nature.
- [x] Prepare and test a private staged review handoff without publishing pixels.
- [ ] A second person independently checks the scene/reference interpretation;
      record agreement, disagreement and unresolved earlier correspondence.
- [ ] Decide whether earlier context is actually needed; if so, record the
      specific question and a new fixed range **before** acquiring more images.
- [ ] Justify/freeze one comparison and fresh validation, or retain a reasoned
      stop if no defensible intervention follows. No improvement is promised.
      The subsequent AI-assisted note records a limited no-change recommendation,
      not closure of this independent-validation gate.
- [ ] Create the final understandable case study and test practitioner usefulness.

**Current intervention decision: do not tune lifetime, add identity memory,
disable gates or reduce confirmation on the strength of this episode.** The
evidence does not justify those actions. This is a reasoned non-intervention
pending review, not a measured “no effect” result from an unrun experiment.

No need to wait for volunteer footage to review this packet. Consented private
recording remains a separate route. C++ stays in maintenance until an accepted,
useful tracking-behaviour change earns its own parity handoff.

## Reproduce the tools without touching old results

Preview acquisition offline:

```bash
PYTHONPATH=src:. python -m experiments.mot17_review_frames
```

For an explicitly permitted local non-commercial acquisition, provide the pinned
labels and a **new external** output directory, then add `--write`:

```bash
PYTHONPATH=src:. python -m experiments.mot17_review_frames \
  --labels ../visiontrack-walkthrough/mot17-label-audit-NQQO7d/MOT17Labels.zip \
  --output /absolute/private/new-frames-directory --write
```

The offline review builder is `python -m experiments.mot17_visual_review`.
It requires the baseline/rescore paths, image directory, its explicit manifest
SHA-256 and a new external output. It revalidates inputs before and after building,
preserves original frame/box coordinates and never invokes a tracker or scorer.

Successful image manifest SHA-256:
`02bd442793b58b6090a661da66f0e779b5f571aadf431f4783e15c18ff924a89`.
Final private review manifest SHA-256:
`b3d59eac3678087d9196ae40e5ebcd2fbd9c3e4457aabd797e8f03fb5c496404`.
Original baseline and v2 metric-rescore manifest fingerprints remain
`4ff57df09d5b4cf06491e984cf7b61f37b79ee22c0a087677f6587d5081984a8`
and `87403372f0a9158da83b4b8dddacb2c6b244db0a08ea7cc92bfb9ac5084a8e4a`.
Only tooling, tests, documentation and the offline CI check enter Git; no images,
private review notes or generated review bundle are committed.

Local verification at this checkpoint: **1,008 tests pass, one slow test
deselected**, including the isolated bootstrap that runs all **1,099 historical
tests** at their original revision. The 23 new Python tests are synthetic
transport/model/admission checks, not real-world accuracy tests. All eight
existing web contract/workflow scripts, the new offline staged-review check,
TypeScript, the production app build, Ruff and strict documentation pass.
Remote CI/deployment must be checked separately after pushing; none of these
checks completes independent human review or actual-browser visual QA.
