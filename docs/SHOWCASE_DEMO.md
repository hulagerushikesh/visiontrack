# A five-minute VisionTrack demonstration

Updated **2026-10-30** using the deterministic `lab-demo --with-initiation` workflow.
This is a **synthetic workflow demonstration**, not a real-camera benchmark,
accepted tracker change or completed usability study. No footage is needed.

## Before starting

From the current source checkout, use a new output folder:

```bash
python -m pip install -e '.[lab]'
visiontrack lab-demo ./lab-showcase --with-initiation --write
```

Omit `--write` to preview the output paths. The new option is not in the
published 0.3.0 wheel yet. Open `lab-showcase/try-in-browser` in your computer's
file manager. Its three files are `report.json`, `initiation-trace.json` and
`START_HERE.txt`. The full Lab bundle is in the adjacent fingerprint-named
directory; the public website does not host it. Files are read into browser
tab memory, without upload, camera access or a human acceptance decision.

At [the Lab](https://visiontrack.hulage.in/lab), select **Import report.json**
and choose that folder's report. Follow **Inspect track initiation** near the
report heading, then **Import initiation trace** and select that folder's trace.
If the trace controls are unavailable, use the current local app or wait for
the matching website deployment; deployment is not verified by preparing files.

## 1. Explain the problem — 30 seconds

“An ID can stay stable while its box or count is wrong. VisionTrack helps us
inspect failures and compare settings before calling a change better.”

Say explicitly: this example contains generated objects, not recorded people.
The intended first audience is engineers/researchers evaluating tracking
configurations. Whether this saves them useful work is still to be tested.

## 2. Follow a detection into public output — 60 seconds

Use **Next** to compare frames 0, 1 and 2 in the initiation timeline:

| Frame | Internal state of ID 1 | Public output |
| --- | --- | --- |
| 0 | Born tentative, one hit | None |
| 1 | Tentative, two hits | None |
| 2 | Confirmed, three hits | ID 1 |

The three columns separate proposals, internal tracks and public output.
“A proposal can create an internal track without producing a public box yet.
Confirmation does not add boxes to earlier frames.” This explains lifecycle
state, not object truth or which association gate rejected a pair.

Optionally find **Explore tracking mistakes** and inspect **bytetrack / Misses
at frame 0**. A report miss does not by itself explain its cause:

The selected event concerns reference object **4** at frame **0**. It has no
matched public track at the report's IoU-0.5 matching threshold. That is what
“miss” means here. It is not evidence that the person was renamed, or proof of
why the miss happened. No images/video are attached, so skip evidence-file
selection. Do not infer the visual cause from this metadata alone.

## 3. Read the comparison — 60 seconds

Find **Same evidence. Controlled change.** in the Lab, or the offline HTML's
comparison table. Both configurations consumed the same saved detections and
reference labels, frames **0–47**. The scene has four reference objects and
114 reference object-frame observations; it is not 114 people.

| Recorded measure | bytetrack (baseline) | single-stage |
| --- | --- | --- |
| Missed object-frames (FN) | 23 | 23 |
| Unmatched output rows (FP) | 0 | 0 |
| Tracking-ID changes (IDSW) | 0 | 0 |
| Fragmentation events (Frag) | 9 | 9 |
| IDF1 | 0.8878 | 0.8878 |

**This example is a tie.** It does not demonstrate that one configuration is
better, or that they are equivalent on other inputs. FN and fragmentation are
different kinds of errors; zero ID switches does not mean zero mistakes.
Do not change the seed or select another example just to manufacture a winner.

## 4. Explain a separate, completed research trade-off — 60 seconds

Open the [initiation-threshold findings](INITIATION_THRESHOLD_FINDINGS.md).
This is a **different synthetic experiment**, not extra results contained in
the onboarding report or a second configuration replay in this timeline.

“Lowering the birth threshold recovered some true crossings, but also let
persistent false proposals confirm and create false counts. The change failed
our no-harm requirement.” All 54 paired cells and 324 repeatability passes are
retained, including 36 unchanged controls. Defaults and C++ remain unchanged.
The useful result is a rejected unsafe trade-off on these toy inputs, not
evidence of an improvement or degradation in real traffic.

## 5. Close with a supported decision — 30 seconds

“The onboarding scene does not choose a winner. The separate study tells us not
to adopt that proposed fix. A traffic improvement still needs representative,
permitted data and independently checked labels.”

Leave **Human review** untouched for this beginner demo. No acceptance/rejection
record is necessary. Report preparation does not complete the owner's review.
Ask: **“Why can an internal track have no public box? What does this example
not prove? Which step was unclear?”** Record the answer, including confusion.
Do not complete another person's review on their behalf or treat these checks
as independent physical-label validation.

## Reproduction and checks

The current generator uses a
fixed fixture timestamp and `git_revision: null`, not a recording date or a
runtime provenance receipt. The freshly generated report has ID
`d37d847100489f7cee7f3f083e9085f7bd2a4c0dbbf140d46f51409c62b2f3fc`
and byte SHA-256
`197efc039a63276934f4a2e5d059a26754743f621d0a7c2bea972eb21fadd01e`.
Rebuilding independently with and without `--with-initiation` preserves every
bundle byte produced by the current generator. Historical exports are not
rewritten or assumed byte-identical to today's report. Both easy-to-find import files pass the actual Lab readers,
including report/trace fingerprints and exact configuration/run binding.
The trace records the executing Python/NumPy/package source provenance, so its
fingerprint can change when that implementation/environment changes.
Preview, existing-path refusal, trace-generation failure and publication rollback
are exercised without external data, network activity or footage.
There are 64 displayed failure records, no image artifacts and no chosen variant.

Follow the [daily/weekly delivery plan](WEEKLY_DELIVERY_PLAN.md) next. This
demonstration is reproducibly prepared; participant comprehension, external
usefulness and browser interaction/visual QA remain open checks. Browser QA
was not performed because of the earlier access denial. No new outreach or
deployment is implied.
