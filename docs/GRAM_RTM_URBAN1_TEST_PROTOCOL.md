# GRAM-RTM Urban1 junction test — frozen protocol

**Frozen 2026-11-27, before any Urban1 image is downloaded or viewed, any
detector or tracker runs on it, or any counting line touches its labels.**
This is the turning-traffic test named in the
[turning-traffic screen](TURNING_TRAFFIC_SCREEN.md). It asks whether the
motion-gate settings that helped on straight roads
([GRAM-RTM](GRAM_RTM_TEST_PROTOCOL.md), [SVMOT](SVMOT_GATE_TEST_PROTOCOL.md))
hurt at a junction, where vehicles turn and their boxes change shape. Any
later change must be a dated amendment written before the first detector run.
After that run, no rule may change.

## Permission and what has been opened

On 2026-11-27 R. J. López-Sastre, one of the dataset authors, replied from the
contact address named in the kit's README. He confirmed that the Urban1 images
and annotations may be used for non-commercial scientific research as test
data only, stored locally, with the original work cited, publishing only code
and aggregate results and redistributing neither images nor annotations. He
also stated that the Urban1 boxes and identities were made and checked by human
annotators and may be described as manually annotated and verified. The
earlier download problem was probably temporary.

So far only the label kit has been opened, for the completeness counts in the
[intake record](GRAM_RTM_INTAKE.md): 23,435 frames at 600×360, 59,693 boxes,
243 vehicle IDs, no track gaps. The Urban1 exclusion map's size and dark share
(37% of pixels) were read; its picture was not viewed. No Urban1 image has been
downloaded.

## Data

- **Sequence:** Urban1, all 23,435 frames. Citation: Guerrero-Gómez-Olmedo,
  López-Sastre, Maldonado-Bascón and Fernández-Caballero, IWINAC 2013.
- **Download:** only the Urban1 image archive, from the publisher's link,
  after the owner approves it with the file size stated. A SHA-256 receipt is
  kept. Images and labels stay owner-local; only counts, ID-switch totals and
  hashes are published.
- **Format check (allowed before the run):** the image count must equal the
  label count, and every image must be 600×360. Nothing is plotted or scored.
- **Frame alignment:** as on M-30, label file *k* is expected to belong to
  image *k*+1. Before the full run, the 20 timing frames are scored at offsets
  −1, 0, +1 and +2 by mean best overlap between label boxes and the pinned
  detector's boxes. The best offset is used. If no offset leads by at least
  0.01, +1 is kept.
- **Frame rate:** the source does not state it. The frame-based windows below
  are the ones used on M-30 (30 fps). If Urban1's true rate is lower, the
  windows are longer in seconds than intended. This is recorded as a limit, not
  tuned.

## Reference and exclusion

- **Reference:** every labelled vehicle (car, van, truck, big truck,
  motorbike), using the box centre, on every labelled frame.
- **Exclusion:** the kit's `ROI/Urban1-map.jpg` marks areas where vehicles were
  not labelled. As on M-30, a pixel is excluded where the map is dark (grey
  below 128). A crossing whose point lies in an excluded area is dropped from
  the reference and from every variant. Detections are not filtered.

## Counting lines, set from the exclusion map alone

A junction has traffic in more than one direction, so one line is not enough.
Take the map's labelled (light) pixels, their centroid and their principal
axis (the direction of greatest spread). Draw **two lines** through the
centroid: one perpendicular to that axis and one along it, each spanning the
labelled area. Crossings from both lines are pooled. If the two axis lengths
differ by less than a factor of 1.5, use one horizontal and one vertical line
through the centroid instead. No label or image is read to place them, and
there are no sensitivity lines.

**Too few crossings:** if the two lines hold fewer than **30** reference
crossings in total, the test is **inconclusive** and judges nothing.

## Turning vehicles, defined from the labels before any tracker runs

A labelled vehicle is **turning** if the direction from the mean centre of
its first quarter of frames to the mean centre of its second quarter, and the
same for its last two quarters, differ by more than **45 degrees**. Vehicles
that move less than 20 pixels in either half are left unclassified. Reference
crossings are then split into turning and straight by the vehicle that made
them. This split is computed and recorded before the tracker comparison runs.

## Detector

The same pinned YOLOX-X as the GRAM-RTM and SVMOT tests: SHA-256
`c892d7aaf1c4746d8a4d675bec669a4db4f434b4ee1efb654bc9b353379c7c55`, 640-pixel
input, `legacy` resize with BGR frames, confidence floor 0.10, NMS 0.45, COCO
car, motorcycle, bus and truck, each its own class. The input is always 640
pixels, so the small frames do not make it faster: at the measured 0.9 seconds
per frame the run is about **6 hours**, in owner-approved sessions of at most
40 minutes with a 5-minute cool-down between them, saving resumable parts. The
joined detections are hashed and replayed identically into every variant.

## Counter, matching and identity

- The cancel-reversals counter with a **30-frame** window.
- Matching: same direction, at most **6 frames** apart, crossing points at
  most **3.9% of the frame width** apart: **23 pixels** at 600.
- **ID switches:** TrackEval's CLEAR metric at IoU 0.5 against the full
  labels, the same tool as on SVMOT.

## Variants

Gate on (default), gate off, and the aspect-free gate, every other setting at
the library default. Each runs twice, and both runs must give byte-identical
output.

## Decision rule

There is one sequence. For stability it is cut into **five equal blocks of
consecutive frames**; a crossing belongs to the block of its frame. For each
candidate against gate on, the result is:

- **Supported** if pooled missed crossings fall; pooled false crossings rise
  by no more than 2, or by 10% of the gain in correct crossings, whichever is
  larger; no block's total errors (false plus missed) rise by more than 2;
  missed crossings by turning vehicles rise by no more than 2; and ID switches
  rise by no more than 10%.
- **No harm** if not supported, but total errors rise by no more than 2,
  missed turning crossings rise by no more than 2, and ID switches rise by no
  more than 10%.
- **Harmful** otherwise.

If both candidates pass, the aspect-free gate is preferred unless gate off
has at least 10% fewer total errors and no more false crossings. The same
rule as SVMOT.

## What a result allows

This is one junction camera, so it is a check for harm, not proof of benefit.

- **Gate off harmful:** a default change to gate off is blocked, whatever
  UA-DETRAC shows, until the harm is explained and a new frozen test passes.
  The opt-in traffic preset would then carry a written warning about junctions.
- **Gate off supported or no harm:** the "turning traffic is untested" caveat
  is narrowed to one junction. It does not replace UA-DETRAC as the partner
  venue for a default-change proposal.
- **Inconclusive:** nothing changes.
- Every number is published with this protocol, whatever the result.

## Before the run

The runner is extended for Urban1 (sequence size, the two-line rule, the
turning split and the block rule) and tested on made-up files **before** the
image download. Then, each with the owner's approval: the download, the
format and alignment checks, the detector sessions, and the comparison.

## Label-only steps, recorded 2026-11-27

Run with the owner's approval, from the exclusion map and labels only. No
image was viewed and no detector was run. The rules above are unchanged.

- **Lines:** the labelled area is long and level (axis ratio 2.64), so the
  across-and-along rule applies. The across line is vertical at x = 299.5,
  from y = 133 to 359. The along line is horizontal at y = 246, across the
  full width.
- **Reference crossings at offset +1:** 272 in total (208 on the across line,
  64 on the along line), well above the 30 needed.
- **Turning split:** of 243 labelled vehicles, **1 is turning**, 184 are
  straight and 58 are unclassified. None of the 272 reference crossings was
  made by a turning vehicle. Traffic in this view runs almost entirely left
  and right along one road.

**What this means, stated before any detector run:** the turning safeguard
in the decision rule has nothing to measure, so this test **cannot judge
turning traffic**. It can still act as a harm check on dense two-way street
traffic with hand-labelled identities, which no earlier venue covers. The
turning definition is not changed after seeing this split; doing so now
would be choosing a rule from the data.
