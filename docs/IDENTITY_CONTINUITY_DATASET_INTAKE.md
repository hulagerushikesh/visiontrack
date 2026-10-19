# RQ5 existing-dataset intake — MEVID

2026-10-19. **Annotation intake completed; real-data comparison not started.**
The owner chose an existing dataset for now and expects friends to be available
for a separate consented pilot tomorrow. This does not approve recording,
consent, a frozen split, or a research outcome in advance.

## Source decision

Use **MEVID metadata for the next feasibility stage**, not as an already
admitted same-camera re-entry benchmark. Its consistent participant labels make
it a better candidate to investigate than ordinary tracking gaps. Keep the
friend-volunteer pilot separate; never pool the two sources or silently use
tomorrow's recordings to tune a result reported on MEVID.

The [official MEVID repository](https://github.com/Kitware/MEVID) describes
158 participant identities, 8,092 tracklets, and a five-file annotation package
derived from MEVA. It provides the official annotation ZIP and links to source
videos separately. Its crop packages total over 40 GB; none was downloaded.
No actor check-in photographs, person crops, videos, or embeddings were
downloaded or processed during this intake.

The [official MEVA site](https://mevadata.org/) links MEVID and states that MEVA
data is available under CC BY 4.0. Its
[general data license](https://mevadata.org/resources/MEVA-data-license.txt)
requires attribution and does not grant all privacy/personality rights. This is
a documented source screen, **not blanket legal or deployment clearance**.
Preserve upstream notices and source/version attribution; review any
file-specific terms before the next media-processing step. Cite Davila et al.,
*MEVID*, WACV 2023, and Corona et al., *MEVA*, WACV 2021 as appropriate. Do not
relicense dataset assets as the VisionTrack repository's MIT code.

### Why not simply use MOT17 re-entry labels?

The [official MOTChallenge paper, Appendix D.1](https://arxiv.org/html/2010.07548)
explains that its evaluation treats a target leaving the field of view and
reappearing as an unseen target with a new ID. Therefore a different GT ID
does **not** establish a genuinely new person, and a GT gap does not establish
an observable exit/return. MOT17 remains useful for ordinary MOT regression,
not unmodified truth for our RQ5 decision.

The [current official MOT17 archive](https://motchallenge.net/data/MOT17/)
states CC BY-NC-SA 3.0 with possible additional third-party source conditions.
Only its labels archive was downloaded outside Git for this screen (SHA-256
`0aa79322e91583369f42f17c4d79a0b145380d8732487bba59272048dc82b2b9`).
No MOT17 images were acquired or identity model evaluated in this step. Its
DPM/FRCNN/SDP versions are detector variants of the same recordings, not
independent people or video samples.

## Reproduced annotation audit

The official `mevid-v1-annotation-data.zip` was downloaded outside both repos.
It is 12,211,153 bytes; SHA-256:

```text
18a91691a0ccb3b79302c55643840bc5b7f16a9ed813d93bbe91edd151f982e8
```

Run the read-only audit on an explicitly selected local copy:

```bash
python -m experiments.reentry_mevid_audit --annotations /private/path/mevid-v1-annotation-data.zip
```

The command checks the five known metadata members without extracting them,
bounded ZIP/member sizes, integral inclusive chip ranges, filename-to-track
alignment, local chip-frame numbering, upstream participant separation, and
query indices. It streams the chip-name tables, prints aggregates only, and
never opens a named JPEG or follows a URL. Dataset download is separate and
not performed by this command. Synthetic unit tests need no dataset/network.

| Measured metadata property | Train | Test |
|---|---:|---:|
| Track-table rows | 6,339 | 1,754 |
| Empty chip ranges | 1 | 0 |
| Non-empty tracklets | 6,338 | 1,754 |
| Listed chip filenames | 3,609,156 | 1,186,251 |
| Distinct participant IDs | 104 | 54 |
| Distinct camera IDs | 22 | 11 |
| Participant/outfit/camera groups | 1,919 | 358 |
| Such groups with multiple tracklets | 1,213 | 270 |

The upstream participant-ID intersection is empty. Test metadata has 316 query
and 1,438 gallery tracklets. **These are upstream retrieval roles, not our
chronological RQ5 gallery or a frozen RQ5 event split.** Inspecting their
metadata does not evaluate test outcomes or select thresholds; no pixels,
features, scores, or model decisions were inspected.

One training row (zero-based row 1,889) declares an empty inclusive chip range,
`1128477..1128476`. The audit exposes it and counts only non-empty tracklets;
it does not repair the archive or silently promote the row into evidence.
The original archive is preserved unchanged. Resolve or explicitly exclude the
entry in a dated intake record before creating a study adapter.

## What this does not establish

Multiple tracklets for one participant/outfit/camera may span different clips,
days, occlusions, or tracking fragments. Their count is **not** a count of
same-session exits/returns. The five crop tables do not provide original
recording timestamps or exit boundaries: `F00000` is a local crop-frame index,
not original video frame zero. Do not invent time gaps, TTL eligibility, novel
arrivals, or chronological candidate galleries from these offsets. Distinct
upstream participants do not by themselves prove recording-disjoint RQ5 data.

Current admitted re-entry events: **zero**. This is an intake status, not a
measured zero prevalence or zero-error result. No restore policy was run.

## Next admission gates, in order

1. Establish an exact tracklet-to-original-recording/time/bounding-box mapping
   using official annotation/toolchain provenance. If it cannot be established,
   stop the same-session RQ5 route; any crop-retrieval study needs its own
   separately registered question and must not replace this study implicitly.
2. Select a small, pre-frozen feasibility sample from upstream **training**
   recordings before looking at pixels. Keep sample selection/digests in the
   private study workspace, not raw identity rows in Git.
3. After the media-use review, fetch only the explicitly identified development
   clips needed for that sample. No bulk video/crop/check-in download, network
   upload, or new model training is needed at this stage.
4. Have two independent reviewers verify continuous-scene exits/returns and
   genuinely novel arrivals before looking at tracker decisions. Preserve
   uncertainty and exclusions rather than guessing IDs.
5. Freeze participant- and recording-disjoint development/test event lists,
   detector/crop/embedding adapter and chronological expiry/eviction/reset
   behavior before comparing the four registered rules. Reuse the
   [protocol](IDENTITY_CONTINUITY_PROTOCOL.md), not the upstream retrieval metric.

The remaining source admission work is real work, not a passed milestone.
No product accuracy claim, live-tracker identity feature, or C++ port is earned
by this metadata audit. Tomorrow's owner steps are in the
[recording-day guide](IDENTITY_CONTINUITY_RECORDING_DAY.md).
