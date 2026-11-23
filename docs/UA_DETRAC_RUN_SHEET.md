# UA-DETRAC run sheet

Written 2026-11-23 (plan item B4). This page is for the owner's download
decision. It changes no rule in the [frozen protocol](UA_DETRAC_TEST_PROTOCOL.md).
**Nothing from UA-DETRAC has been downloaded.** The timings below come from
made-up files of the same shape and size, not from the dataset.

## Before anything is fetched

1. The authors confirm the reuse terms in writing.
2. The owner approves the download, naming each file and its size.

## Files needed

The dataset page lists four downloads: images, annotations, detections and
toolkits. The test needs **two**:

| File | Why | Needed? |
|---|---|---|
| Annotations (DETRAC-Annos), **test split** XML | Reference vehicle tracks and the ignored regions | Yes |
| Detections (DETRAC-Detections), **test split** | The supplied boxes the trackers run on. The protocol tries R-CNN first, then CompACT, ACF and DPM. Only the first set whose scores all lie between 0 and 1 is used. | Yes |
| Images (DETRAC-Images) | Only the frame size and count are read, and both are known without them (960 x 540, frame count from the labels) | **No** |
| Toolkits | Not used | No |

If the test-split annotations hold no ground truth, the protocol switches to
the training split (60 sequences), and the training annotations and
detections are needed instead.

**Sizes.** The dataset page does not show file sizes in its listing, so the
owner reads them from the download links before approving. As a guide, the
made-up files at full test size took **64 MB** for the annotations and
**31 MB** for one detection set, uncompressed. The real files have about a
third fewer boxes, so they should be smaller. An unofficial 11.8 GB mirror
exists but is not used: the terms are agreed with the authors, so files come
from their own links.

## Steps

| Step | What happens | Time on the laptop (measured on made-up files) |
|---|---|---|
| 1. Unpack | Files go into one owner-local folder with `annotations/` and `detections/<SET>/`, outside Git | Minutes |
| 2. Format check | Count sequences and frames, read headers, check each detection set's score range. No counting or tracking. Results recorded as a dated note in the protocol. | **3 seconds**, 100 MB memory |
| 3. Reader fix, only if needed | If the real layout differs from the expected one, only the file readers change, recorded with a date before any tracker run | — |
| 4. The run | All 40 sequences, three variants, each run twice and required to be byte-identical, plus ID switches | **10 minutes**, 130 MB memory |
| 5. Record | Copy the verdicts and pooled numbers into the protocol and the [default-change proposal](DEFAULT_CHANGE_PROPOSAL.md) without rewording | Under an hour |

The made-up set was 40 sequences and 56,000 frames at 960 x 540, with about
13 labelled vehicles per frame (725,901 label rows). That is the frame count
the dataset paper gives for the test split, at a heavier vehicle density, so
the real run should be no slower. The 60-sequence fallback would take about
15 minutes. Both are well under the 30-minute laptop limit and run one job
at a time.

Reproduce the timing:

```bash
python -m experiments.ua_detrac_synthetic --root <empty folder>
python -m experiments.ua_detrac_gate check --root <that folder>
python -m experiments.ua_detrac_gate run --root <that folder> --output <json>
```

## What this sheet does not show

The made-up files were shaped from the dataset's public description, not
from the real files. The real layout, field names or frame numbering may
differ, and step 3 exists for that. The made-up run's verdicts mean nothing
and are not recorded.
