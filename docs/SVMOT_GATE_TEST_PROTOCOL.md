# SVMOT motion-gate test — frozen protocol

**Frozen 2026-11-22, before any SVMOT test-scene file is downloaded or
opened.** This is the second venue in the
[traffic gate test plan](TRAFFIC_GATE_TEST_PLAN.md), chosen by the owner. It
asks the same question as the [UA-DETRAC](UA_DETRAC_TEST_PROTOCOL.md) and
[GRAM-RTM](GRAM_RTM_TEST_PROTOCOL.md) tests. Any later change must be a dated
amendment written before the first detector run. After that run, no rule may
change.

What has been opened so far: the publisher's metadata, split files, and a few
files from four **training** sequences ([intake](SVMOT_INTAKE.md)). No
test-scene member has been opened.

## Data

- **Sequences:** the publisher's nine test sequences, all frames:
  `seq_22_morning` to `seq_25_morning` (scene 5) and `seq_26_evening` to
  `seq_30_evening` (scene 6). Training scenes are not used. Sequences are
  named by directory, not by `seqinfo.ini`, which is known to disagree.
- **Download:** only the test sequences' members are range-read from the
  publisher archive: images, `gt/gt.txt`, `seqinfo.ini` and `roi_mask.png`.
  Each member must pass its ZIP CRC. The publisher's `det/det.txt` is not
  used, because on training sequences it copies the ground-truth boxes.
- **Licence:** CC BY-NC 4.0, research use only. Images and labels stay
  owner-local. Only counts, ID-switch totals and hashes are published.

**Format check (allowed before the run).** Count frames, label rows and IDs
per sequence, and confirm frame size and frame rate. Nothing is plotted or
scored.

**Download and format check, 2026-11-22. No rule changes.** With the owner's
approval, the nine test sequences' images, labels, settings files and road
masks were range-read from the publisher archive: **8,277 files, 5.2 GB, every
ZIP CRC passed**, with a per-file SHA-256 receipt kept owner-local. The format
check found:

- **8,250 frames**, all 1920×1080 at 30 fps, numbered without gaps, matching
  each settings file's length (1,200 for `seq_22_morning`, 900 for scene 5's
  other three, 870 for each scene 6 sequence).
- **70,220 label rows and 168 vehicle IDs** in total, 13 to 29 per sequence,
  on every frame. All labelled classes are vehicle types.
- A road mask in every sequence.
- Four settings files name a different sequence than their folder
  (`seq_22`→20, `seq_23`→22, `seq_25`→26, `seq_26`→25), as already seen on
  training data. Folder names are used, as frozen.

Only 168 vehicles appear, many of them parked, so the 30-crossing minimum is a
real risk. No image was viewed, no line was drawn, and nothing was scored.

## Reference and counting line

- **Reference:** the ground-truth tracks, using the box centre, on every
  labelled row, including rows with zero visibility. A vehicle hidden behind
  another still crosses the line.
- **Region:** labels exist only inside each sequence's road mask. A crossing
  whose point lies outside the mask is dropped from both the reference and
  every variant. Detections are not filtered.
- **Line, set from the mask alone, before any label is read:** take the mask's
  white pixels, find their centroid and their principal axis (the direction of
  greatest spread). The counting line passes through the centroid,
  perpendicular to that axis, and spans the mask. If the mask's two axis
  lengths differ by less than a factor of 1.5, the line is horizontal through
  the centroid instead. One line per sequence. No sensitivity lines.
- **Too few crossings:** if the nine sequences hold fewer than **30**
  reference crossings in total, the test is reported as **inconclusive** and
  judges nothing. SVMOT has many parked vehicles, so this is a real risk.

## Detector

The same pinned YOLOX-X as the GRAM-RTM test: same file, 640-pixel input,
`legacy` resize with BGR frames, confidence floor 0.10, NMS 0.45, COCO car,
motorcycle, bus and truck, each its own class. It runs once per sequence in
owner-approved sessions of at most 40 minutes, saving resumable parts, and the
joined detections are hashed and replayed identically into every variant.
About 8,000 frames is roughly 2–2.5 hours in total.

## Counter, matching and identity

- The cancel-reversals counter with a **30-frame** window (30 fps).
- Matching: same direction, at most **6 frames** apart, crossing points at
  most **3.9% of the frame width** apart: **75 pixels** at 1920.
- **ID switches:** TrackEval's CLEAR metric at IoU 0.5 against the full
  ground truth, summed over sequences, the same tool used for MOT17.

## Variants

Gate on (default), gate off, and the aspect-free gate, every other setting at
the library default. Each runs twice per sequence, and both runs must give
byte-identical output.

## Decision rule

For **aspect-free gate versus gate on**, the result is:

- **Supported** if pooled missed crossings fall; pooled false crossings rise
  by no more than 2, or by 10% of the pooled gain in correct crossings,
  whichever is larger; no sequence's total errors (false plus missed) rise by
  more than 2; and pooled ID switches rise by no more than 10%.
- **No harm** if not supported but pooled total errors rise by no more than 2
  and pooled ID switches rise by no more than 10%.
- **Harmful** otherwise.

Gate off is judged by the same rule. If both pass, the aspect-free gate is
preferred unless gate off has at least 10% fewer pooled total errors and no
more pooled false crossings.

## What a result allows

The test has two scenes only, both elevated views of mostly straight roads.

- Together with a supported UA-DETRAC result for the same candidate, a
  supported result here can back a default-change proposal. On its own, it
  cannot.
- **Harmful** blocks that candidate as a default until the harm is explained
  and a new frozen test passes.
- **Inconclusive** means the plan needs another second venue.
- Every number is published with this protocol, whatever the result.

## Runner

`experiments/svmot_gate.py`, committed 2026-11-22 before the detector run. It
reuses the GRAM-RTM runner's detector settings, exclusion filter and matching.
Its tests cover the mask line rule, the decision rule with the ID-switch
safeguard and the 30-crossing minimum, a known ID swap, and resuming detection.

**Lines, computed from the masks alone, 2026-11-22.** Each scene uses one
mask for all its sequences, so scene 5 and scene 6 each get one line. Both
masks are clearly elongated (axis ratios 1.85 and 1.74), so both lines are
the perpendicular kind: nearly vertical, near the middle of the frame, from
about x = 1,215 to 1,342 (scene 5) and 1,190 to 1,291 (scene 6). No label was
read to place them.

**Detections complete, 2026-11-22. No rule changes.** Five owner-approved
sessions of at most 48 minutes, each after a 5-minute cool-down, saved every
part with no heat warning. All nine sequences are complete: **8,250 frames and
144,983 detections** (scene 5: 23,203, 18,614, 18,348 and 20,643; scene 6:
13,256, 12,037, 14,045, 12,096 and 12,741). Each sequence's joined file is
hashed in its receipt, kept owner-local with the frames. No tracker has run on
them and no label has been used for counting yet.

## Result, 2026-11-22

Run once, with the owner's approval, under the rules above. Each variant ran
twice on each sequence, and both runs gave byte-identical output. Full numbers
are in [`experiments/svmot_gate_v1_result.json`](https://github.com/hulagerushikesh/visiontrack/blob/main/experiments/svmot_gate_v1_result.json).

Correct / false / missed crossings, and ID switches:

| Sequence (reference) | Gate on | Gate off | Aspect-free gate |
|---|---|---|---|
| seq_22_morning (14) | 12 / 0 / 2, 111 | 14 / 0 / 0, 42 | 14 / 0 / 0, 46 |
| seq_23_morning (4) | 3 / 2 / 1, 90 | 3 / 1 / 1, 69 | 3 / 3 / 1, 68 |
| seq_24_morning (5) | 4 / 0 / 1, 49 | 4 / 0 / 1, 32 | 4 / 0 / 1, 32 |
| seq_25_morning (9) | 9 / 0 / 0, 34 | 9 / 0 / 0, 18 | 9 / 0 / 0, 18 |
| seq_26_evening (15) | 10 / 0 / 5, 71 | 15 / 0 / 0, 19 | 15 / 0 / 0, 23 |
| seq_27_evening (21) | 16 / 0 / 5, 47 | 21 / 0 / 0, 10 | 21 / 0 / 0, 13 |
| seq_28_evening (16) | 10 / 0 / 6, 56 | 16 / 0 / 0, 5 | 16 / 0 / 0, 30 |
| seq_29_evening (9) | 8 / 0 / 1, 62 | 9 / 0 / 0, 36 | 9 / 0 / 0, 36 |
| seq_30_evening (6) | 4 / 0 / 2, 63 | 4 / 1 / 2, 13 | 4 / 1 / 2, 26 |
| **Pooled (99)** | **76 / 2 / 23, 583** | **95 / 2 / 4, 244** | **95 / 4 / 4, 292** |

- **The test is conclusive:** 99 reference crossings, above the 30 minimum.
- **Gate off versus gate on: supported.** Missed crossings fell from 23 to
  4, false crossings stayed at 2, no sequence's errors rose by more than one,
  and ID switches fell from 583 to 244.
- **Aspect-free gate versus gate on: supported.** Missed crossings fell from
  23 to 4. False crossings rose from 2 to 4, exactly at the allowed limit of
  2. ID switches fell from 583 to 292.
- **Preference:** both pass. Gate off has 6 pooled total errors against 8,
  25% fewer, with fewer false crossings, so by the rule gate off is preferred.

**What this allows.** This is the second unused venue after GRAM-RTM, and it
points the same way: the default gate loses crossings on fast fixed-camera
traffic, and switching it off recovers them without more identity swaps.
The frozen plan names UA-DETRAC as the partner venue for a default-change
proposal, so on its own this result cannot back one. The aspect-free gate
passed only at the edge of its false-crossing limit. Both scenes are elevated
views of mostly straight roads, so turning traffic is still untested.
