# SVMOT v1.0: bounded research intake

Checked **2026-10-29**. This is a release-metadata and development-sample check,
not an admitted tracking experiment. The [publisher record](https://zenodo.org/records/19468203)
and [record API](https://zenodo.org/api/records/19468203) identify version
`v1.0`, DOI `10.5281/zenodo.19468203`, and `cc-by-nc-4.0` in the API license
field. The rendered record's Rights field is blank, so the API value is the
explicit metadata evidence used here. The non-commercial condition limits this lead to
research; it is not a basis for commercial product use or publication of source
images without a separate exact-use review.

## Small publisher files verified locally

The five small release files were fetched from the publisher API to
`../visiontrack-walkthrough/svmot-intake-v1/`, outside both Git repositories.
Each byte count and MD5 matched the publisher's file metadata. The computed
SHA-256 values of the four content files match their lines in the downloaded
`SHA256SUMS`.
The same file names and digests are in the owner-local `metadata-receipt.json`.

| File | SHA-256 |
| --- | --- |
| `README_RELEASE_v1.0.md` | `f4d9ad68d43bb052d58dcbcfe2f0be0e0d00ea37eac7758054c561d33d772a3a` |
| `by_scene.json` | `6d4f00b86b534dcac1f074cc4656f4f12ecd14fac2f56a1f29bff3a3b371efeb` |
| `train.txt` | `45afa8d7e35e0940577ae1bcb5dc39aa0958336cf50113b312631a259f4b6a7a` |
| `test.txt` | `33d6c6aa614e58965bf1a7c705feea32f9b131a35f6bfd6247a36bb1a812ac81` |
| `SHA256SUMS` | `50ee57ee22f23d608e7cd9338507bcd7a01f87764ee323d85b6d43e5feff7147` |

The publisher's split files agree exactly with `by_scene.json`: **21 training
sequences from four scenes**, **nine test sequences from two different scenes**,
and no sequence/scene overlap. The publisher lists 30 sequences, 26,900 frames,
243,462 boxes and 1,017 IDs, plus occlusion fields. Those aggregate counts are
publisher statements, not locally verified archive contents. The release README
describes MOTChallenge-like `img/`, `gt/`, `det/` and metadata paths but does not
provide a usable link to the companion annotation/evaluation documentation it
mentions.

## Admission decision

**Hold.** The full archive is **18.3 GB**; its publisher-listed checksum
`aae153a21a46f9fe37068ee006a65abd58894efaabc4390404eadcc08be8bd7a`
has not been checked against a complete local copy. Before outcome scoring, determine the precise
camera/site provenance, annotation creation and review process, per-frame ID
coverage, class and ignore semantics, fixed-camera suitability, and whether
the chosen research use and derived public aggregate findings fit the terms.
Keep publisher test scenes unopened while freezing the comparison question,
metric, detector input, baseline, and negative-result rule. A scene-disjoint
split prevents one kind of leakage; it does not prove label quality or target-
domain transfer.

This source could support non-commercial research on occlusion and identity
continuity if those checks pass. It cannot yet validate VisionTrack's traffic
counting utility or a product claim.

## Bounded development sample, 2026-10-29

After the metadata screen, the publisher archive's central directory was read
through HTTP byte ranges. Only `classes.txt` and `seqinfo.ini`, `gt.txt`,
`det.txt`, and frame `0001.jpg` from one sequence in each of the **four official
training scenes** were fetched. The four images visually show elevated road
views; one first frame per sequence does not establish camera stability through
time. These files and the range probe remain owner-local, outside Git. The
selected ZIP members passed their CRC checks; this does **not** verify the full
archive SHA-256 or all frames. No test-scene member was opened.

The repeatable [source audit](../experiments/svmot_source_audit.py) checked
30,762 sampled GT rows across those four sequences. Each of their 30,762
supplied `det.txt` rows has an exact GT box coordinate match. This may be a
deliberate release design, but these detections cannot be used as an
independent detector stream for a detector-plus-tracker comparison. Three
`seqinfo.ini` names disagree with their directory/split names:
`seq_04_morning` declares `seq_02_morning`, `seq_13_evening` declares
`seq_07_evening`, and `seq_17_evening` declares `seq_15_evening`. Use directory
names only after resolving this discrepancy; do not silently trust metadata.
The owner-local machine-readable audit is `development-audit.json` in the
intake folder. No tracker was run and no performance result was computed.

This evidence narrows the next check: independently review a bounded
development label span for ID and occlusion quality, then use a separately
pinned real detector stream if SVMOT is admitted. Keep the publisher test
scenes unopened until a protocol is frozen. The current `hold` remains.

## Temporal and occlusion check, 2026-10-29

The owner-local byte-range probe then read frames 300, 600 and the final frame
for each of the same four training sequences, plus their `roi_mask.png` and
`occlusion.json`. Each of the 16 selected JPEG members (including the earlier
first frames), four masks and four occlusion files passed ZIP-member CRC checks.
The two bounded range passes fetched about 15.6 MB combined; they did not
download or verify the complete archive. The four views appear camera-fixed
across these widely separated samples; continuous frame-to-frame stability,
timestamps and site provenance are not established. No test-scene member was
opened.

The extended [source audit](../experiments/svmot_source_audit.py) now checks
that every occlusion record is in frame order, refers to the same GT object ID
and box, names an occluder present in that frame, and has valid within-object
occlusion geometry. All **30,762** records and **25,607** occlusion links in
these four development sequences passed these structural checks. This verifies
internal consistency, **not** that an identity or occlusion label is physically
correct. Three owner-local GT overlays at selected frames showed the labeled
boxes on vehicles, but this is a spot check only. The masks delimit a road
region; all 30,762 sampled GT box centers fall inside their respective mask.
Visible vehicles outside the mask must not be called missing labels. Completeness
inside the mask and ID preservation through particular occlusions still need an
independent bounded review.

This source is better aligned with a **stationary-vehicle/occlusion continuity**
question than with the current directed-flow counting question. An ROI-limited
MOT label set does not supply reviewed crossing events, flows, or customer
decision truth. Keep SVMOT on hold for comparative tracking and product claims;
do not use its GT-mirroring `det.txt` as the shared detector input.
