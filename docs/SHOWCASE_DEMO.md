# A five-minute VisionTrack demonstration

Prepared **2026-10-23** using the existing deterministic `lab-demo` workflow.
This is a **synthetic workflow demonstration**, not a real-camera benchmark,
accepted tracker change or completed usability study. No footage is needed.

## Before starting

The prepared local bundle is outside both repositories, under
`visiontrack-walkthrough/showcase-2026-10-23/`, in experiment directory
`b71944878b44b25d2f84f263c52a6670c1d93febde9177252bf50655c8270e72`.
Its `report/index.html` opens without installation; `report/report.json` can be
selected using **Import report.json** at
[the Lab](https://visiontrack.hulage.in/lab). Local file links are supplied in
the chat; the public site does not host this bundle. Importing it reads a local
file in the browser, not an upload of footage. No camera or email action is needed.

## 1. Explain the problem — 30 seconds

“An ID can stay stable while its box or count is wrong. VisionTrack helps us
inspect failures and compare settings before calling a change better.”

Say explicitly: this example contains generated objects, not recorded people.
The intended first audience is engineers/researchers evaluating tracking
configurations. Whether this saves them useful work is still to be tested.

## 2. Inspect one mistake — 60 seconds

In the Lab, find **Explore tracking mistakes**. Select **Inspect** on
**bytetrack / Misses at frame 0**. In the offline HTML, find that event in the
failure table instead; it does not have the React screen's interactive controls.

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

Open the [box-gate findings](BOX_GATE_FINDINGS.md). This is a **different
synthetic experiment**, not extra results contained in the onboarding report.

One concrete held-out solo example is enough to explain the issue:

- The reference crossing is at frame **149.5**, inside `[120, 150)`.
- Gate-off reports the crossing near **165.5654**, inside `[150, 180)`.
- Event error improves **1 → 0**, but time-window count error worsens **1 → 2**.

“It found the crossing, but put it in the wrong counting window. Improving one
number was not enough.” The completed study rejected the gate-off intervention
under its fixed joint requirements; defaults and C++ remain unchanged. These
are toy scenes, not evidence of improvement or degradation in real traffic.

## 5. Close with a supported decision — 30 seconds

“The onboarding scene does not choose a winner. The separate study tells us not
to adopt that proposed fix. Our next evidence milestone is one permitted real
clip with checked labels, not a claim that we have the world's best tracker.”

Leave **Human review** untouched for this beginner demo. No acceptance/rejection
record is necessary. Report preparation does not complete the owner's review.
Ask only: **“Can you explain one mistake and why a better number might still
be a bad change? Which part was unclear?”** Record the answer, including confusion.

## Reproduction and checks

From a configured checkout, use a new output folder:

```bash
visiontrack lab-demo /absolute/path/to/new-demo --write
```

This preparation used code checkpoint `bf7f059`; the existing generator uses a
fixed fixture timestamp and `git_revision: null`, not a recording date or a
runtime provenance receipt. The prepared report has ID
`b8b8760c1c6616856577082bcb2e3e96cf3d3ee961ab3dc3c00f3b4dfb109f96`
and byte SHA-256
`184445099c301764a2f87fcd7793973beb975898e3e88d632105836be6c35837`.
Rebuilding in an independent temporary directory reproduced these report bytes.
The Python bundle verifier and actual browser report parser both accepted it.
There are 64 displayed failure records, no image artifacts and no chosen variant.

Follow the [daily/weekly delivery plan](WEEKLY_DELIVERY_PLAN.md) next. This
demonstration is ready locally; participant comprehension and external usefulness
remain open checks. No new outreach or deployment is implied.
