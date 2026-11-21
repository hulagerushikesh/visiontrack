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

`experiments/svmot_gate.py` will be written and committed before the
detector run, reusing the GRAM-RTM runner's detection, replay, counting and
matching code.
