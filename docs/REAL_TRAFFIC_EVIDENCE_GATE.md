# Real fixed-camera traffic evidence — admission decision

Checked **2026-10-26**. This is a source and task-fit screen, **not** a dataset
download, a legal opinion, a new tracking experiment, or evidence that
VisionTrack works in traffic. The immediate research question is whether a
local engineer can make a better review or configuration decision using a
reproducible detector/tracker comparison and its failure evidence. A second,
separate question is whether any candidate tracker improves a traffic outcome.
Do not collapse those questions into a single benchmark score.

## Decision today

**No new traffic dataset is admitted to an outcome study.** The known MOT17
pedestrian sequence has already been opened and cannot be repackaged as a fresh
fixed-traffic holdout. The two-adult indoor re-entry rehearsal is a different
camera/domain/task; it cannot validate road-user flow counts. Keep the failed
[box-gate intervention](BOX_GATE_FINDINGS.md) and the ineffective
[continuity-warning triage rule](CONTINUITY_WARNING_MOT17_FINDINGS.md) offline.
No C++ port, default change, product accuracy claim, or public example image
follows from this screen.

## Source screen

| Candidate and primary source | Why it is interesting | Admission result and exact missing check |
| --- | --- | --- |
| [GRAM-RTM](https://gram.web.uah.es/data/datasets/rtm/index.html), especially Urban1 | The authors describe a fixed surveillance traffic camera, 23,435 frames, manually annotated vehicle IDs, and research use. The official page says images are **test-only**, not for training/tuning. | **First candidate for local non-commercial research, not yet admitted.** The official development-kit URL returned HTTP 403 from this environment on 2026-10-26; the image-host access, complete annotation schema, file checksums, sequence timing and publication/redistribution scope are not verified. Do not replace it with an unattributed mirror or treat its single site as OpenTrafficCam-like deployment evidence. |
| [FE-DETRAC](https://scidm.nchc.org.tw/en/dataset/fe-detrac) | The catalog describes 22 fixed fisheye traffic cameras, MOT-format annotations and camera-disjoint splits. | **Hold on terms/provenance.** The body states CC BY-NC-SA 4.0, while the page's license footer says CC BY-NC 4.0; listed resources are also labeled Fisheye8K. Resolve the exact asset/version and governing terms with the publisher before download or derived public material. |
| [SVMOT](https://zenodo.org/records/19468203) | The record lists 30 sequences, MOT-format GT **and detections**, occlusion fields, and scene-level splits. | **Hold on rights.** The Zenodo record shows no usable license value in its Rights section as checked. The 18.3 GB archive has not been downloaded, and fixed-camera/site and label details have not been inspected. |
| [RoundaboutHD](https://researchdata.bath.ac.uk/1574/) | Four fixed 4K cameras, labeled vehicle trajectories and a single-camera tracking subset. | **Hold on asset-level rights and practicality.** The archive is 8 GB; the catalog's `Software: MIT License` label does not by itself establish the scope for footage, frames or derived public visuals. No files were downloaded or annotations inspected. |
| [Drive-Thru partial set](https://figshare.com/articles/dataset/Dataset_for_Multicamera_multitarget_tracking_on_Drive_Thru_Areas/29277770) | Figshare's public record and API state CC BY 4.0. | **Not suitable for this dense-tracking gate.** The public manifest lists only 124 dispersed JPEGs across three cameras and three `vehicle0` trajectory CSVs; it is explicitly a partial release. Those are not a complete independently adjudicated dense multi-object sequence or flow truth. No images were downloaded. |
| [Khan/Kelly vehicle set](https://data.mendeley.com/datasets/5d8k5bkb93/1) | The publisher page states CC BY 4.0, seven videos and 24,700 annotated frames under varied conditions. | **Hold on task fit/provenance.** The page describes DarkLabel annotations and source clips from other Creative-Commons material, but the per-frame ID continuity, clip-level rights chain, fixed-camera metadata and exact file structure were not verified. |

These are **source observations**, not a ranking of tracker performance or a
claim that other datasets are unusable. Terms can change; repeat this check at
the exact version and file level before handling media. A public webpage, an
open repository, and a code license are not interchangeable permission for
video, faces, plates, annotations, publication, or commercial use.

## What admits one dataset

Record these in an owner-local intake outside Git **before** opening outcome
scores. A missing answer leaves the source at `hold`:

1. **Rights and privacy:** exact publisher/version, terms for private research,
   derived annotations/reports, publication and commercial use; whether people,
   plates or other sensitive material appear; permitted machine, access and
   deletion date. Keep image bytes and dataset annotations out of both repos.
2. **Source integrity:** original URL and immutable archive/file digests; frame
   naming/index origin, dimensions, timestamps or trustworthy constant-FPS
   evidence, missing frames, camera/site IDs and clip chronology. Do not infer
   elapsed time from a nominal FPS alone.
3. **Truth quality:** inspect a preselected *development* slice for ID, box,
   class, ignore/occlusion and visibility semantics. Independently review a
   bounded event sample. Mark disagreements/indeterminate cases rather than
   manufacturing clean identities. Provider labels are a reference, not
   infallible physical truth.
4. **Task fit:** choose one operational decision and its unit: e.g. whether
   an engineer must review a candidate broken trajectory, or whether a
   directed vehicle crossing was missed/assigned to the wrong flow. A dataset
   with box/ID labels alone does not automatically have flow, journey or
   decision-time truth.
5. **Fixed comparison:** one detector/version and immutable detection stream
   shared by every tracker variant; predeclared classes, camera/site split,
   baseline, metrics, safety margins, review workload and negative-result
   rules. Distinguish detector misses from association failures. Never tune on
   the unopened test site or recycle an inspected case as holdout.

Only after all five pass should we freeze a narrow protocol in Git **before**
the first comparative run. The first admitted source may support a useful
*external-domain research screen* without representing the blurred, angled
European cameras described by OpenTrafficCam. A transfer or product claim
requires evidence from the actual target setting and a real engineer's
decision, not only a public benchmark.

## Next executable path

- Resolve official GRAM kit/image access and inspect its rights/file schema
  **read-only**. If unavailable, move to a different source with explicit
  asset-level terms; do not bypass an access restriction or use a mirror.
- When one candidate passes rights and integrity, make a source inventory and
  a small *development-only* annotation audit. Record any ambiguity before
  selecting a tracking variant.
- Separately ask one relevant engineer to name the costly decision, existing
  evidence workflow and acceptable review burden **before** demonstrating a
  proposed warning. Outreach or data transfer needs a fresh owner decision.
- Keep the two-person consented indoor rehearsal as an optional pipeline test
  under its own [recording guide](IDENTITY_CONTINUITY_RECORDING_DAY.md). It is
  neither a traffic benchmark nor an independent-person holdout.

This gate prevents more speculative tracker code while identifying exactly what
new evidence would justify implementation. VisionTrack C++ remains at the
accepted NumPy 0.3.0 / C++ 0.1.1 contract.
