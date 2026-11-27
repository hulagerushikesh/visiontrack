# GRAM-RTM: label-kit intake

Status, 2026-11-20: **backup source for the motion-gate test, not admitted.** Label kit and motorway images are owner-local; see below.
The owner approved downloading the label kit only. No image was downloaded or
opened. No tracker ran, no counting line was drawn, and no crossing was
computed. These were format and completeness counts only, the same kind the
[UA-DETRAC protocol](UA_DETRAC_TEST_PROTOCOL.md) allows before a run.

## What was downloaded

`GRAM-RTMv4.zip` (version 2013.4) from the
[official page](https://gram.web.uah.es/data/datasets/rtm/index.html):
24,732,734 bytes, SHA-256
`acf7d560f0eb27e45325c35feea3e64d0ad1ba324db62ca0656c8ecf56bffb00`. The
publisher lists no checksum. It is kept owner-local, and none of its MATLAB
code was run.

It holds per-frame PASCAL VOC XML labels for three sequences, exclusion-region
maps, the authors' own detection and tracking results from their 2013 paper,
and evaluation code under GPL v3.

## Terms, as the kit's README states them

- **M-30 and M-30-HD images:** recorded by the authors themselves from a
  tripod, licensed **CC BY 3.0**.
- **Urban1 images:** recorded by a traffic surveillance camera. The README's
  licence covers only the two M-30 sequences, so **Urban1's image rights are
  not stated**. The web page says the database is public "for scientific
  research purposes". That does not clearly cover third-party camera footage,
  so ask the authors before using Urban1. *Answered 2026-11-27:* an author
  confirmed Urban1 images and labels may be used for non-commercial research
  as local test data, with citation and no redistribution, and that its labels
  were manually annotated and verified. See the
  [Urban1 protocol](GRAM_RTM_URBAN1_TEST_PROTOCOL.md).
- **Labels:** no separate licence. The web page's research-use statement
  applies, with the 2013 IWINAC paper cited.

## Completeness counts

| Sequence | Frames | Size | Boxes | Vehicle IDs | Frames with no vehicles | Track gaps |
| --- | ---: | --- | ---: | ---: | ---: | ---: |
| M-30 | 7,520 | 800×480 | 35,601 | 270 | 192 | 0 |
| M-30-HD | 9,390 | 1200×720 | 34,149 | 238 | 314 | 0 |
| Urban1 | 23,435 | 600×360 | 59,693 | 243 | 0 | 0 |

Every sequence has one label file per frame, with no missing frame numbers.
No ID appears twice in one frame. **No vehicle's track has a gap**: once a
vehicle appears, it is labelled in every frame until it leaves, and no ID
lasts under 5 frames. That is unusually clean. It may mean frames were filled
in between key frames, as RoundaboutHD's were, which a visual check would
need to settle. Vehicles inside the marked exclusion regions are not labelled.

## The supplied detections do not fit the protocol

The authors' 2013 detector output covers every frame. Its scores run up to
2.41 (M-30), 2.09 (M-30-HD) and 1.21 (Urban1), so they fail the protocol's
0-to-1 score rule. There are also only about half as many detections as
labelled boxes on M-30 (17,416 against 35,601). A test here would need our
own detector run. At these resolutions the run is moderate, but it still needs
laptop-load approval first.

## Motorway images, downloaded 2026-11-20

With owner approval, both CC BY 3.0 image archives were downloaded through
the publisher's public OneDrive page in the browser pane. Only archive lists
and integrity were checked. No image was opened or viewed.

| Archive | Bytes | SHA-256 | Integrity | Images |
| --- | ---: | --- | --- | ---: |
| `M-30.zip` | 275,877,710 | `58b0c0a817b002138a6a22608f78e3701e0228c307a8f6bcc957e59290df3fb0` | No errors | 7,520 JPEG |
| `M-30-HD.zip` | 1,817,487,796 | `7819e26b5342c43fdf7a5ced1e01b099b859d5bd0cc01f204e4ab16528dbe547` | No errors | 9,390 JPEG |

The byte counts match the sizes the host reported. The first M-30-HD attempt
stalled at 223 MB and was deleted. The publisher lists no checksums, so the
hashes are our own receipts. Image counts match the label files exactly.
**Numbering differs:** images run from 1, labels from 0. The label file for
frame *k* most likely belongs to image *k*+1, as with the authors' detections,
which start at 1. A box-to-detection distance check must confirm the offset
before any run, as on RoundaboutHD.

## Test protocol

Frozen on 2026-11-20 before any image was viewed: the
[GRAM-RTM test protocol](GRAM_RTM_TEST_PROTOCOL.md).

## What would admit it

1. Urban1 waits on the authors' answer about its rights. The motorway images
   are in hand.
2. With owner approval, run one pinned detector on those images. Freeze the
   detector and the dataset-specific protocol amendment (sequences, line rule)
   in writing before any label is used for counting.
3. Note the limit: M-30 is a straight motorway seen from a bridge, so cars
   turn and change shape less than at a roundabout. A pass there would show
   the aspect-free gate does no harm on ordinary traffic, not that it helps
   at turns.
