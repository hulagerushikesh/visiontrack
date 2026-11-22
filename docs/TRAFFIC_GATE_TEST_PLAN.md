# Traffic motion-gate test — plan

**Drafted 2026-11-22. A plan, not a frozen protocol.** Nothing here changes a
frozen rule until the owner approves it and it is written into the protocol it
amends, with a date, before that test's data is downloaded or opened.

## The question

Does switching the Mahalanobis motion gate off (or using the aspect-free gate)
count fixed-camera vehicle traffic better than the default gate, on video that
no earlier comparison has touched, without hurting identities?

## What we already know, all on used data

| Source | Missed crossings: gate on → gate off | Status |
| --- | --- | --- |
| RoundaboutHD, development, 4 cameras | 135 → 28 of 361 | Used for development |
| RoundaboutHD frozen test, c001/c003/c004 | 69 → 22 of 245 | Not supported: c003 got worse by one error |
| GRAM-RTM frozen test, M-30 and M-30-HD | 30 → 24 of 502 | Gate off supported and preferred |
| SVMOT frozen test, 9 sequences (2026-11-22) | 23 → 4 of 99; ID switches 583 → 244 | Gate off supported and preferred; aspect-free gate supported at its false-crossing limit |
| MOT17 val-half, pedestrians | HOTA 47.78 → 47.97, ID switches 190 → 185 | Pedestrian guard passes for both candidates |

The direction is consistent: the default gate, tuned for slow pedestrians,
stops tracks from confirming on fast near-camera vehicles. But every frame of
RoundaboutHD and GRAM-RTM M-30/M-30-HD has now been seen by a comparison, so
none of them can confirm it. The pedestrian guard is already measured, so a
traffic win could support a default change, not only a traffic preset.

## The test: two independent venues

A default change needs the result on **two unused sources**, not one.

**Venue 1 — UA-DETRAC (frozen, waiting on terms).** The
[protocol](UA_DETRAC_TEST_PROTOCOL.md) already judges gate on, gate off and
the aspect-free gate on all 40 test sequences, with supplied detections. No
detector run is needed, so it is light laptop work. It runs as frozen once the
authors confirm the terms in writing.

**Amendment approved by the owner, 2026-11-22, and written into the
protocol before any download:** add an
identity safeguard, because counting alone cannot see swapped identities.
UA-DETRAC has per-frame vehicle IDs. Report pooled ID switches for every
variant. A candidate whose pooled ID switches rise by more than 10% over gate
on is **not supported**, whatever its counts.

**Venue 2 — choose one (owner decision):**

| Option | Wait | Laptop and owner cost | Weakness |
| --- | --- | --- | --- |
| **A. Own recording** | None | One fixed phone video of a road from a window or bridge, 30 fps, 5 minutes (9,000 frames). Detector about 2.5 hours, in approved 40-minute sessions. About an hour of the owner's time confirming crossings, as in the c002 label audit. | One site; we make the reference ourselves. Faces or plates may be visible, so the video stays owner-local and only counts are published. |
| B. SVMOT test scenes | None | 18.3 GB download, own detector run on 9 test sequences. | Non-commercial licence; mostly parked vehicles, so few line crossings; known label-quality concerns. |
| C. GRAM-RTM Urban1 | Authors' reply on image rights | Light detector run at 600×360. | Blocked until the authors answer. |

**Owner's choice, 2026-11-22: option B, SVMOT test scenes.** Its rules are
frozen in the [SVMOT protocol](SVMOT_GATE_TEST_PROTOCOL.md). Only the nine
test sequences are range-read, not the whole 18.3 GB archive.

Option A is the only one that can start now. Its reference method has already
passed once: our own crossing marks matched RoundaboutHD's labels on 23 of 23.

## Rules for venue 2, to freeze before recording

- Same three variants, same cancel-reversals counter, same matching limits
  scaled to frame width, same decision rule as GRAM-RTM (two-or-few sequences),
  plus the identity safeguard if labels allow it. Option A has no per-frame IDs,
  so for it the safeguard is skipped and that limit is stated.
- One horizontal or vertical line, placed from the scene layout before any
  tracker runs.
- Crossings are marked by the owner before any tracker output is viewed.
- The pinned YOLOX-X detector, run once, saved with a hash, replayed into every
  variant twice.

## What would follow

**Meanwhile, 2026-11-22:** an opt-in [`traffic` preset](TRAFFIC_PRESET.md)
(gate off) was added at the owner's request, backed by GRAM-RTM and SVMOT. It
does not change the default or any rule here.

- **Both venues support one candidate:** a default-change proposal, a Python
  release, then a C++ synchronisation milestone.
- **They disagree or neither supports it:** the default stays, and every
  number is published.
- This plan cannot show behaviour on turning traffic at busy junctions unless
  the chosen venue has it.
