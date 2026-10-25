# Before the overlap: what track 19's saved history supports

Checkpoint: **2026-10-25**. This is a completed, **read-only exploratory
geometry audit**, not a new tracker experiment or independent visual review.
It addresses one unresolved question from the
[36–57 preliminary pixel inspection](MOT17_VISUAL_REVIEW.md): what saved
evidence exists before that short image window?

## Result in plain language

Track 19 was not first introduced in the overlap window. It becomes public at
source frame **3**, and in **every frame 3–35** its box has IoU at least 0.5 with
reference **85**, but less than 0.5 with reference **89**. Both pedestrian
references are present throughout frames 1–35. Frames 1–2 have no public 19;
that does not mean an internal tentative track did not exist.

| Saved-box measurement | Frame 3 | Frame 35 | Across all 33 public frames |
| --- | --- | --- | --- |
| 19 against reference 85 | 0.9278318918 | 0.7495035758 | Minimum 0.7495035758 |
| 19 against reference 89 | 0.0348613045 | 0.3875471796 | Maximum 0.3875471796 |
| Reference 85 against 89 | 0.0174672489 | 0.2763694522 | Maximum 0.2763694522 |

IoU describes how much two rectangles overlap. The 0.5 boundary is a fixed
descriptive rule here, not a newly optimized tracker threshold. These are
original saved coordinates; no smoothing, relabeling or tracker rerun occurred.

Combined with the existing later evidence, the sequence is now clearer:

1. **3–35:** 19 has geometric support from 85, not 89, under this two-reference rule.
2. **36–57:** the already inspected figures overlap and separate. In later
   frames 19 aligns with 89; 31 becomes public over 85 at 54. The actual-call
   trace shows 19 remained updated/public, and 31 was spawned at 52.
3. **Still unresolved:** whether the published reference paths consistently
   correspond to the same physical figures through the overlap. We have not
   viewed frames 1–35 or obtained a separate person's independent review.

This strengthens a **reference-relative correspondence-change hypothesis**.
It does not independently prove a physical-person switch, correct labels,
the causal contribution of each tracker stage, or an effective remedy.
In particular, it does not justify increasing lifetime or adding persistent
identity memory. A continuously updated box following a different reference
is a different problem from a deleted track being recreated after absence.

## Scope fixed before inspecting this prefix

The audit inspected **all frames 1–35**, not only a favorable earlier frame:
the complete saved prefix preceding the existing 36–57 window. It reused the
sealed full-sequence baseline, public track **19**, and references **85/89**.
The question, scope and rule were written to `method.json` before calculation.
The case and later findings were already known, so this is **exploratory**,
not untouched validation or a prospectively registered intervention.

For each source frame it retains the original public box, reference boxes,
published visibility, reference-to-reference IoU and each available
19-to-reference IoU. All overlaps at least 0.5 are retained: if both pass,
the result is **both**, not a forced maximum-IoU winner. Missing references
or output have `null` overlap rather than a misleading zero. Consecutive
state summaries also preserve reference-presence changes.

This calculation does **not** reproduce the metric's global assignment or its
history rules; other objects can compete for matches. It must not be substituted
for evaluator-v2 events. Nor is rectangle overlap person recognition or a
biometric identity label. Visibility values are supplied annotations, not an
independent assessment of image quality.

No images were acquired, source files changed, tracking parameters altered,
new comparison run, labels accepted, private information published or C++ code
ported. No owner recording, email, cloud service or browser automation was used.

## What we do next

- [x] Establish whether earlier saved public-output support exists: 33/33
      earlier public frames support reference 85 alone under the stated rule.
- [ ] A separate reviewer uses the existing staged 36–57 page, recording
      uncertainty/disagreement before seeing these conclusions.
- [ ] If that review needs earlier pixels to follow the figures, write down
      its exact unresolved question and a fixed additional range **before**
      acquiring them. This audit does not authorize or silently perform that intake.
- [ ] Decide on one justified, prospectively fixed comparison with fresh
      validation, or publish a reasoned non-intervention with its open limits.

The current decision remains **no tracker change pending review**. That is not
a measured negative result for an intervention we never ran. C++ remains at its
accepted reference contract; measurement/diagnostic tools are not a port request.

## Reproduce without altering old evidence

Offline method preview (no input reads or writes):

```bash
PYTHONPATH=src:. python -m experiments.mot17_prior_context
```

With the pinned local baseline and an existing private parent, explicitly write
to a **new external** output directory:

```bash
PYTHONPATH=src:. python -m experiments.mot17_prior_context \
  --baseline ../visiontrack-walkthrough/mot17-baseline-NvcCNo/bundle \
  --output /absolute/private/new-prior-context-directory --write
```

The tool verifies all 11 baseline members, both saved runs' exact equality and
the pinned baseline manifest. It requires the complete ordered 1,050-frame raw
sequence, analyzes only 1–35, checks unique aligned IDs and valid target boxes,
and rechecks inputs and calculation source after analysis. Existing output and
in-repository output are rejected. Failure retains a method/failure receipt
without a success manifest. It does not import or execute the tracker.

Actual local packet:
`../visiontrack-walkthrough/mot17-prior-context-fWBzgJ/analysis/`.

| Receipt | SHA-256 |
| --- | --- |
| Baseline manifest | `4ff57df09d5b4cf06491e984cf7b61f37b79ee22c0a087677f6587d5081984a8` |
| Method | `59a37052dc0b8cb16c095d365a33061d8c48967e7e06cb78c64f5c5de7a5203f` |
| Summary | `158df4f087fa33102e52c9cb2e7810613696c970b76ebfbaa5c209f51eb4e824` |
| Packet manifest | `0cbbc64ba357c91aa1847e7abb7e74e8d5881771dd911129bbf5042a93fb2a9e` |

The packet contains the method, all 35 rows and summary, with per-file digests.
It stays outside Git. The 14 new authored tests cover the geometric rule,
threshold equality, ambiguous support, missing values, validation, immutability,
offline preview and success/failure receipts. They are not scene annotations or
accuracy evidence. The independent-review and actual-browser QA gates remain open.

Local verification for this checkpoint: **1,022 tests pass, one slow test
deselected**, including the isolated historical bootstrap at its original
revision (1,099 historical tests). All eight existing web contract/workflow
checks, the offline staged-review check, TypeScript, the app production build,
Ruff and strict documentation pass. These checks do not verify a person's
identity or complete the independent scene review. Remote CI/deployment are
separate post-push checks.
