# RQ5 real-data feasibility audit

Checked: 2026-10-14. This is a read-only audit of local annotations and
upstream dataset terms. It does **not** report identity-restoration accuracy.

## Available candidate: DanceTrack validation split

The [official DanceTrack repository](https://github.com/DanceTrack/DanceTrack)
describes 25 publicly annotated validation videos with bounding boxes and
identity IDs. Its annotations are CC BY 4.0; its videos/images are for
**non-commercial research only**, and the maintainers state that those images
were obtained from the Internet rather than owned by their institutions.
Therefore this split can support a local research feasibility study under its
stated limits. It is not cleared as product demo footage or a commercial
deployment validation set. No images or derived person crops should be
committed to either repository.

The locally present validation split has 25 `gt.txt` files. A read-only pass
over the annotations found:

| Annotation property | Count |
|---|---:|
| GT rows | 225,148 |
| Identity-within-sequence keys | 273 |
| Consecutive annotation gaps of at least 1 missing frame | 1,370 |
| Gaps of at least 10 missing frames | 344 |
| Gaps of at least 30 missing frames | 116 |
| Gaps of at least 100 missing frames | 15 |

The reproducible, metadata-only extractor is
[`experiments/reentry_gap_audit.py`](https://github.com/hulagerushikesh/visiontrack/blob/main/experiments/reentry_gap_audit.py).
Run it locally with:

```bash
python -m experiments.reentry_gap_audit --root /path/to/dancetrack/val
```

It found the same 225,148 rows, 273 sequence-scoped identity keys, and 1,370
gap candidates across the 25 validation sequences. The duration strata are:

| Missing frames | Candidate count |
|---|---:|
| 1–9 | 1,026 |
| 10–29 | 228 |
| 30–99 | 101 |
| 100+ | 15 |

The canonical candidate-list SHA-256 is
`8f2036b0f81df88f2872061054a8236fbdb790cce0ec14b3c108cd189dff7a04`.
The CLI deterministically selects the five lowest SHA-256-ranked events in
each stratum for a **20-candidate visual audit**, before opening frames. Its
output includes only sequence IDs and frame numbers; it reads no images and
writes no files. One sequence contains no gap candidate, which is why the
per-sequence candidate summary lists 24 rather than 25 sequences.

These are **candidate absence windows**, not verified returns. A missing GT
box may mean occlusion, annotation policy, movement outside the frame, or
another cause. Several gaps may belong to one person, so event counts are
not independent sample sizes. The audit uses only sequence-scoped IDs; IDs
with the same number in different videos are not assumed to identify the same
person. Validation is the only DanceTrack split found at the expected local
path, so a held-out protocol must divide these 25 recordings and may have
limited statistical power.

## Alternative: SportsMOT

The [official SportsMOT README](https://github.com/MCG-NJU/SportsMOT/blob/main/README.md)
describes player identities and track gaps in sports clips. It states a
CC BY-NC 4.0 license, requires acceptance of competition terms, and says the
dataset may not be redistributed without prior written permission. Existing
VisionTrack caches contain SportsMOT detections and embeddings, but the raw
validation split was not found at the previously documented Downloads path in
this audit. It remains a possible independent domain check after confirming
the local dataset path and exact accepted terms; the caches alone do not
establish a publishable RQ5 protocol.

## Gate for the first real-data RQ5 study

1. Review the upstream dataset conditions again at execution time and record
   the exact source/version and permitted use. Keep raw media local.
2. Use the frozen 20-candidate audit sample above. Inspect local frames around
   each window and label whether the person truly leaves the observable scene,
   is merely occluded, remains visible but unannotated, or is indeterminate.
   Record who reviewed each event, the decision rubric, and disagreement; do
   not change the sample after seeing frames. A GT gap is never auto-promoted
   to a true re-entry label.
3. Identify the source recordings where possible. Split development and test
   by recording/source, and assess whether the same performers might appear
   across clips. If identity separation cannot be established, label the
   result as within-DanceTrack sequence transfer, not unseen-person transfer.
4. Freeze one detector, crop policy, embedding adapter, gallery expiry rule,
   threshold grid, and event exclusions. Keep the test videos unseen until
   those choices are saved.
5. Report novel arrivals and evicted/expired returns as separate groups, with
   grouped uncertainty by sequence and identity. If the split has too few
   restoration attempts to bound risk, report **insufficient evidence**.

The [registered protocol](IDENTITY_CONTINUITY_PROTOCOL.md) and
[synthetic probe](IDENTITY_CONTINUITY_SYNTHETIC.md) provide the decision and
scoring definitions. This audit establishes feasibility for event extraction;
it does not satisfy the rights, annotation, split, or statistical gates above.
