# Real fixed-camera traffic evidence — admission decision

Checked **2026-10-26–28**. This is a source and task-fit screen, **not** a legal
opinion, a new tracking experiment, or evidence that
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
| [GRAM-RTM](https://gram.web.uah.es/data/datasets/rtm/index.html), especially Urban1 | The authors describe a fixed surveillance traffic camera, 23,435 frames, manually annotated vehicle IDs, and research use. The official page says images are **test-only**, not for training/tuning. | **First candidate for local non-commercial research, not yet admitted.** The official development-kit URL returned HTTP 403 again from this machine on 2026-10-28; the linked Urban1 host redirected to Microsoft sign-in in the public web check. Complete annotation schema, original-file checksums, actual image access and publication/redistribution scope remain unverified. Do not use an unattributed mirror or treat this single site as OpenTrafficCam-like deployment evidence. |
| [AI City Challenge 2021 Track 1](https://www.aicitychallenge.org/2021-data-and-evaluation/) | A fixed-camera, movement-specific vehicle-counting task across 20 camera views, with cross-validated counts. The organizer now lists the [dataset for quick access](https://www.aicitychallenge.org/ai-city-challenge-dataset-access/). | **Task-relevant, but not a dense tracking holdout.** The organizer says the accessible A split includes only a small ground-truth subset for demonstration; the B labels were reserved. The [2021 data agreement](https://www.aicitychallenge.org/wp-content/uploads/2021/01/DataLicenseAgreement_AICityChallenge_2021.pdf) limits post-challenge use to non-commercial academic purposes and restricts distribution. No files were opened. A count-only research question would need its own rights/task/label intake and cannot verify ID-switch or trajectory-warning truth. |
| [AI City Challenge 2022 Track 1 / CityFlowV2](https://www.aicitychallenge.org/2022-data-and-evaluation/) | Fixed intersection/highway cameras, vehicle IDs, and provided baseline detections/single-camera tracks; the organizer now lists [direct access](https://www.aicitychallenge.org/2022-track1-download/). | **Hold for rights and label coverage.** The organizer says only vehicles seen in at least two cameras are annotated, so its labels cannot be assumed complete single-camera traffic truth. The [2022 agreement](https://www.aicitychallenge.org/wp-content/uploads/2022/02/Dataset-License-AIC2022.pdf) limits post-challenge use to non-commercial academic purposes and prohibits general redistribution or production use. No files were opened or license accepted. Clarify project-use fit and inspect annotation coverage before any narrow research intake. |
| [UA-DETRAC](https://sites.google.com/view/daweidu/projects/ua-detrac) | The author's official page describes 100 traffic videos with boxes, occlusion and vehicle-type annotations, and offers image, annotation and detection downloads. | **Hold on asset-level terms and file access.** That page does not state a dataset-use license or enough about the precise ID/flow-label scope for this decision. No files were downloaded; a code repository or public download link alone would not settle footage, derivative-report or product-use rights. |
| [FE-DETRAC](https://scidm.nchc.org.tw/en/dataset/fe-detrac) | The catalog describes 22 fixed fisheye traffic cameras, MOT-format annotations and camera-disjoint splits. | **Hold on terms/provenance.** The body states CC BY-NC-SA 4.0, while the page's license footer says CC BY-NC 4.0; listed resources are also labeled Fisheye8K. Resolve the exact asset/version and governing terms with the publisher before download or derived public material. |
| [SVMOT](https://zenodo.org/records/19468203) | The record lists 30 sequences, MOT-format GT **and detections**, occlusion fields, and scene-level splits. | **Hold on rights.** The Zenodo record shows no usable license value in its Rights section as checked. The publisher-hosted 3.8 KB [release README](https://zenodo.org/records/19468203/files/README_RELEASE_v1.0.md?download=1) only refers back to that metadata for licensing. The 18.3 GB archive has not been downloaded, and fixed-camera/site and label details have not been inspected. |
| [RoundaboutHD](https://researchdata.bath.ac.uk/1574/) | Four fixed 4K cameras, labeled vehicle trajectories and a single-camera tracking subset. | **Hold on asset-level rights and practicality.** The archive is 8 GB; the catalog's `Software: MIT License` label does not by itself establish the scope for footage, frames or derived public visuals. No files were downloaded or annotations inspected. |
| [Drive-Thru partial set](https://figshare.com/articles/dataset/Dataset_for_Multicamera_multitarget_tracking_on_Drive_Thru_Areas/29277770) | Figshare's public record and API state CC BY 4.0. | **Not suitable for this dense-tracking gate.** The public manifest lists only 124 dispersed JPEGs across three cameras and three `vehicle0` trajectory CSVs; it is explicitly a partial release. Those are not a complete independently adjudicated dense multi-object sequence or flow truth. No images were downloaded. |
| [Khan/Kelly vehicle set](https://data.mendeley.com/datasets/5d8k5bkb93/1) | The publisher page states CC BY 4.0, seven videos and 24,700 annotated frames under varied conditions. | **Hold on task fit/provenance.** The page describes DarkLabel annotations and source clips from other Creative-Commons material, but the per-frame ID continuity, clip-level rights chain, fixed-camera metadata and exact file structure were not verified. |
| [Highway Vehicle Surveillance Dataset V1](https://data.mendeley.com/datasets/zdgmdg7p25/1) | The publisher page states CC BY 4.0 and offers day, night, and rainy highway footage. | **Not suitable as supplied for this dense-tracking gate.** The original archive and four companion ZIPs were downloaded to owner-local storage outside Git on 2026-10-27. The video ZIP contains three MP4s; day/night/rainy experiment ZIPs contain 12/10/12 sparse PNGs; the article ZIP contains TeX and illustration assets. Archive member lists contain no independent dense frame-level IDs or boxes. The first four ZIP SHA-256 digests match the publisher's file information. No image/video was extracted, republished, or used for a tracker score. The page's processed-results description does not substitute for inspectable ground truth. |
| [UVH-26, IISc AIM](https://huggingface.co/datasets/iisc-aim/UVH-26) | An official CC BY 4.0 release of fixed Bengaluru traffic-camera images with two consensus box-label sets. | **Detection data, not tracking truth.** Its documented COCO annotations have image IDs, class IDs, and boxes but no temporal object IDs; 26,646 frames were sampled from about 2,800 cameras. Useful to consider separately for a future detector-domain study, not as a dense single-camera tracking or flow-count reference. Its 90 GB image set was not downloaded. |
| [Traffic Surveillance Video Corpus](https://huggingface.co/datasets/thundarstrom/traffic-surveillance-video-corpus) | Its maintainer's card advertises continuous drives and CVAT track annotations under CC BY 4.0. | **Not an available fixed-camera source.** The card describes dashcam drives, not fixed surveillance views, and the host's current file inventory says the dataset is empty (2.34 KB card only). No media or annotations were downloaded. Do not infer data availability from the description alone. |

These are **source observations**, not a ranking of tracker performance or a
claim that other datasets are unusable. Terms can change; repeat this check at
the exact version and file level before handling media. A public webpage, an
open repository, and a code license are not interchangeable permission for
video, faces, plates, annotations, publication, or commercial use.

For the HVSD intake, publisher-listed and locally matched SHA-256 receipts were
`Dataset.zip` `e32476f77547bf3498835e74b78317794ab1ba78f78023b647f2d02f9a89e9c0`,
`DAY_Experiment.zip` `9b126e45d806afa23ca7007221d3f9221f964a9fad1911657a7e7ce141a21b45`,
`NIGHT_Experiment.zip` `3cc2b812220d765998e5976b9abeb9c05ab5101337a625f0b74f81994f8773ba`,
and `RAINY_Experiment.zip` `9d7850cfe95add0f2a855116008db3fe41dba0294d605b9a4efbdfa849895f52`.
The article archive was inspected by member list only; its independently
computed digest was `7e42b53ba3a2d7d01bbe380753e8419a548945f40dcf822b063c121a9265fa59`,
but no publisher checksum comparison is claimed for it.

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
  **read-only**. If it remains unavailable, seek a different source with
  explicit asset-level terms and *complete labels for the chosen decision*;
  do not bypass an access restriction or use a mirror. AI City 2021 is a
  possible count-only question, not an ID/trajectory validation shortcut;
  CityFlowV2's annotated subset is not complete single-camera truth.
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
