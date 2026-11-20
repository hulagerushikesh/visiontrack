# UA-DETRAC motion-gate test — frozen protocol

**Frozen 2026-11-20, before any UA-DETRAC file is downloaded, opened or
inspected.** VisionTrack has never used UA-DETRAC. Every choice below is fixed
from the dataset's public description and from the rules of the earlier
RoundaboutHD tests. None comes from looking at its frames, labels, detections
or tracker output. Any later change must be a dated amendment written before
the first tracker run. After that run, no rule may change.

**Precondition.** The authors must confirm the reuse terms in writing, and the
owner must approve the download. Until both happen, nothing is fetched. If the
terms forbid this use, the test stops and this protocol is kept as a record.

## Question

On unused fixed-camera traffic video, does the
[aspect-free gate](ASPECT_GATE_DEVELOPMENT.md) count line crossings better
than the current default gate, without adding false counts? A second question
is whether it is preferable to switching the gate off.

## Data

- **Sequences:** every sequence in the official test split (40 according to
  the dataset paper). If the release has no ground truth for the test split,
  use every sequence in the training split (60) instead. No sequence is
  dropped for any reason other than a file that fails the format check below.
  Sequences with no reference crossings are kept in the report. They count
  toward false crossings but cannot add correct or missed ones.
- **Detections:** the dataset's own supplied detection sets, used unchanged,
  with no detector run. The set is chosen by a fixed order of preference:
  R-CNN, then CompACT, then ACF, then DPM. The first set whose scores all lie
  between 0 and 1 on every chosen sequence is used. If none does, the test
  stops for a dated amendment before any tracker run. Supplied detections have
  no vehicle type, so every box gets one shared class.
- **Reference:** the ground-truth vehicle tracks, using the centre of each
  box, as on RoundaboutHD.
- **Ignored regions:** the dataset marks regions where vehicles are not
  labelled. A crossing whose crossing point lies inside one is removed from
  both the reference and the tracker output. Detections themselves are not
  filtered.

**Format check (allowed before the run).** Count files, sequences and frames;
read file headers; check the score range of each detection set; confirm frame
numbering between detections and labels. Record the results here as a dated
note. No counting, tracking or per-vehicle inspection happens at this step.

## Counting lines

UA-DETRAC is shot from overpasses looking along the road, so traffic mainly
moves up and down the image. Each sequence gets one **horizontal line across
the full width at half the image height**: from (0, 270) to (960, 270) in
960×540 pixels. If a release uses another resolution, the line scales with the
height. The line is placed by this rule, not by viewing the video.

Two more lines at 40% and 60% of the height are reported as a sensitivity
check only. They do not decide the result.

## Counter and matching

These are the RoundaboutHD rules, scaled for a smaller, faster video:

- A crossing is a step between two adjacent frames, by the same ID, in which
  the box centre moves from one side of the line to the other. Its direction is
  kept. The counter is unchanged from the earlier tests, so a vehicle jittering
  back across the line still counts twice. That affects every variant
  equally. Fixing it is separate work.
- A tracker crossing matches a reference crossing one to one if both go in the
  same direction, are at most **5 frames** apart, and their crossing points are
  at most **38 pixels** apart. RoundaboutHD allowed 3 frames at 15 fps
  (0.2 seconds) and 150 pixels on 3,840-pixel-wide frames. Both limits are
  scaled to 25 fps and 960 pixels.
- Correct counts are matched pairs; false counts are unmatched tracker
  crossings; missed counts are unmatched reference crossings.

## Variants

All three run on identical inputs with every other tracker setting at the
library default:

1. **Gate on**: the current default.
2. **Gate off**: `use_mahalanobis_gating=False`.
3. **Aspect-free gate**: the candidate from `experiments/aspect_gate.py`,
   unchanged since 2026-11-20.

Each variant runs twice per sequence, and both runs must give byte-identical
output. Runs go one sequence at a time on the laptop. The work is tracking
only, on supplied boxes, comparable to the RoundaboutHD runs.

## Decision rule

**Main question: aspect-free gate versus gate on.** The candidate is
**supported** only if all three hold:

1. Pooled missed crossings fall.
2. Pooled false crossings rise by no more than 2, or by 10% of the pooled gain
   in correct crossings, whichever is larger.
3. Across sequences where total errors (false plus missed) differ between the
   two, the candidate has fewer errors in significantly more of them: a
   one-sided sign test at the 5% level.

Otherwise it is **not supported**. The RoundaboutHD rule asked that no single
camera got worse. With dozens of sequences, one sequence going the wrong way
by one count is expected noise, so the sign test replaces that condition. It
is set here, before any result exists.

**Second question: aspect-free gate versus gate off.** Gate off is judged by
the same three conditions against gate on. If both pass, the aspect-free gate
is preferred unless gate off has at least 10% fewer pooled total errors and no
more pooled false crossings. If only one passes, that one is preferred. If
neither passes, the default stays.

## What a result allows

- **Supported:** a proposal to change the library default may be written. It
  still needs the pedestrian guard: MOT17 val-half must not drop by more than
  0.5 HOTA. The development run already shows a 0.18 rise, and it is repeated
  on the release candidate. Then comes a Python release, and only after that a
  C++ synchronisation milestone.
- **Not supported:** the default stays. The result is reported in full,
  including any sequences where a change helped.
- Either way, every pooled and per-sequence number is published with this
  protocol. The UA-DETRAC files stay owner-local unless the terms say
  otherwise.

## Runner

`experiments/ua_detrac_gate.py` will be written and committed after the
format check and before the first tracker run. It reuses the RoundaboutHD
crossing and matching code, with the limits above passed in.
