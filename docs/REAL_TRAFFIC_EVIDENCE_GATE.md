# Real fixed-camera traffic evidence — admission decision

Checked **2026-10-26–29**. This is a source and task-fit screen, **not** a legal
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
The owner cannot record a private traffic clip; public publisher-hosted footage
is the active path. The [HVSD local feasibility check](PUBLIC_TRAFFIC_VIDEO_FEASIBILITY.md)
now verifies all three clip bytes and frame timelines and executes one
unchanged rain-clip pipeline smoke run. Its lack of independent dense truth
keeps outcome admission closed. An owner source-only event review now supplies
five exploratory crossing marks for the rain clip, documented in the
[rain review audit](HVSD_RAIN_REVIEW.md); those marks are not dense ID truth or
an untouched outcome test. No C++ port, default change, product accuracy claim, or public example image
follows from this screen.

## Source screen

| Candidate and primary source | Why it is interesting | Admission result and exact missing check |
| --- | --- | --- |
| [GRAM-RTM](https://gram.web.uah.es/data/datasets/rtm/index.html), especially Urban1 | The authors describe a fixed surveillance traffic camera, 23,435 frames, manually annotated vehicle IDs, and research use. The official page says images are **test-only**, not for training/tuning. | **First candidate for local non-commercial research, not yet admitted.** The official development-kit URL returned HTTP 403 again from this machine on 2026-10-28; the linked Urban1 host redirected to Microsoft sign-in in the public web check. Complete annotation schema, original-file checksums, actual image access and publication/redistribution scope remain unverified. Do not use an unattributed mirror or treat this single site as OpenTrafficCam-like deployment evidence. |
| [AI City Challenge 2021 Track 1](https://www.aicitychallenge.org/2021-data-and-evaluation/) | A fixed-camera, movement-specific vehicle-counting task across 20 camera views, with cross-validated counts. The organizer now lists the [dataset for quick access](https://www.aicitychallenge.org/ai-city-challenge-dataset-access/). | **Task-relevant, but not a dense tracking holdout.** The organizer says the accessible A split includes only a small ground-truth subset for demonstration; the B labels were reserved. The [2021 data agreement](https://www.aicitychallenge.org/wp-content/uploads/2021/01/DataLicenseAgreement_AICityChallenge_2021.pdf) limits post-challenge use to non-commercial academic purposes and restricts distribution. No files were opened. A count-only research question would need its own rights/task/label intake and cannot verify ID-switch or trajectory-warning truth. |
| [AI City Challenge 2022 Track 1 / CityFlowV2](https://www.aicitychallenge.org/2022-data-and-evaluation/) | Fixed intersection/highway cameras, vehicle IDs, and provided baseline detections/single-camera tracks; the organizer now lists [direct access](https://www.aicitychallenge.org/2022-track1-download/). | **Hold for rights and label coverage.** The organizer says only vehicles seen in at least two cameras are annotated, so its labels cannot be assumed complete single-camera traffic truth. The [2022 agreement](https://www.aicitychallenge.org/wp-content/uploads/2022/02/Dataset-License-AIC2022.pdf) limits post-challenge use to non-commercial academic purposes and prohibits general redistribution or production use. No files were opened or license accepted. Clarify project-use fit and inspect annotation coverage before any narrow research intake. |
| [UA-DETRAC](https://sites.google.com/view/daweidu/projects/ua-detrac) | The author's official page describes 100 traffic videos with boxes, occlusion and vehicle-type annotations, and offers image, annotation and detection downloads. | **Hold on asset-level terms and file access.** That page does not state a dataset-use license or enough about the precise ID/flow-label scope for this decision. No files were downloaded; a code repository or public download link alone would not settle footage, derivative-report or product-use rights. |
| [FE-DETRAC](https://scidm.nchc.org.tw/en/dataset/fe-detrac) | The catalog describes 22 fixed fisheye traffic cameras, MOT-format annotations and camera-disjoint splits. | **Hold on terms/provenance.** The body states CC BY-NC-SA 4.0, while the page's license footer says CC BY-NC 4.0; listed resources are also labeled Fisheye8K. Resolve the exact asset/version and governing terms with the publisher before download or derived public material. |
| [SVMOT](https://zenodo.org/records/19468203) | The publisher lists 30 sequences from six traffic scenes, MOT-format GT **and detections**, occlusion fields, and a [scene-level train/test split](https://zenodo.org/records/19468203/preview/by_scene.json?include_deleted=0). Its [record API](https://zenodo.org/api/records/19468203) exposes `license.id = cc-by-nc-4.0`, although the rendered page's Rights field is blank. | **Non-commercial research intake, not admitted.** Small release files and a four-sequence development sample were checked without opening test scenes. All 30,762 supplied detection boxes in that sample exactly match GT box coordinates; three sequence metadata names disagree with directory names. A bounded visual review found one plausible ID-through-occlusion example, but its fully hidden frame cannot independently verify identity. All sampled occlusion rectangles equal GT-box intersections, and visibility is derived from those overlaps to three decimals, so these fields do not independently verify label quality. This is a better candidate for stationary-vehicle/occlusion continuity than directed-flow counting. Use a separately pinned detector stream if admitted. The full 18.3 GB archive checksum, camera provenance, label protocol/completeness, and product-use rights remain unresolved. See [bounded intake](SVMOT_INTAKE.md). Freeze a scene-disjoint protocol before opening test labels. |
| [RoundaboutHD](https://researchdata.bath.ac.uk/1574/) | Four fixed 4K cameras, labeled vehicle trajectories and a single-camera tracking subset. | **Hold on asset-level rights and practicality.** The archive is 8 GB; the catalog's `Software: MIT License` label does not by itself establish the scope for footage, frames or derived public visuals. No files were downloaded or annotations inspected. |
| [Drive-Thru partial set](https://figshare.com/articles/dataset/Dataset_for_Multicamera_multitarget_tracking_on_Drive_Thru_Areas/29277770) | Figshare's public record and API state CC BY 4.0. | **Not suitable for this dense-tracking gate.** The public manifest lists only 124 dispersed JPEGs across three cameras and three `vehicle0` trajectory CSVs; it is explicitly a partial release. Those are not a complete independently adjudicated dense multi-object sequence or flow truth. No images were downloaded. |
| [Khan/Kelly vehicle set](https://data.mendeley.com/datasets/5d8k5bkb93/1) | The publisher page states CC BY 4.0, seven videos and 24,700 annotated frames under varied conditions. | **Hold on task fit/provenance.** The page describes DarkLabel annotations and source clips from other Creative-Commons material, but the per-frame ID continuity, clip-level rights chain, fixed-camera metadata and exact file structure were not verified. |
| [Highway Vehicle Surveillance Dataset V1](https://data.mendeley.com/datasets/zdgmdg7p25/1) | The publisher page states CC BY 4.0 and offers day, night, and rainy highway footage. | **Source-only feasibility passed; dense-tracking outcome gate held.** The original archive and four companion ZIPs were downloaded to owner-local storage outside Git on 2026-10-27. The video ZIP contains three MP4s; day/night/rainy experiment ZIPs contain 12/10/12 sparse PNGs; the article ZIP contains TeX and illustration assets. Archive member lists contain no independent dense frame-level IDs or boxes. The first four ZIP SHA-256 digests match the publisher's file information. On 2026-10-29 all three MP4s were extracted privately, byte-checked and decoded; the rain clip had one unchanged metadata-only pipeline smoke run. No pixels were republished or tracker accuracy score computed. The page's processed-results description does not substitute for inspectable ground truth. |
| [I-24 MOTION I24V](https://github.com/I24-MOTION/i24-video-dataset-utils#data-use-agreement) | Its official data-use agreement allows academic and commercial use and derivative products, with attribution for published academic work, while prohibiting individual re-identification. Fixed roadside cameras, supplied detections and manually corrected GPS trajectories offer a relevant but different task. | **Hold on access, scale and truth coverage.** The official documentation says 234 hours from 234 cameras, but only 270 vehicle passes have manually corrected GPS trajectories; this is not complete dense box/ID truth. The linked publisher download endpoint returned a request rejection here on 2026-10-29. No dataset files were downloaded. Select one camera/time subset and a recall-oriented question only after access and exact terms are rechecked. The code repository's MIT license is separate from the dataset agreement. |
| [TrafficMOT](https://github.com/lihaoliu-cambridge/trafficmot) | The authors' repository links a fixed-CCTV traffic tracking dataset and paper. | **Hold on media terms and asset inventory.** The small public repository links a Google Drive dataset but does not display an asset license or a verifiable per-file manifest. No download, mirror or inference of permission from the repository's public status. |
| [UVH-26, IISc AIM](https://huggingface.co/datasets/iisc-aim/UVH-26) | An official CC BY 4.0 release of fixed Bengaluru traffic-camera images with two consensus box-label sets. | **Detection data, not tracking truth.** Its documented COCO annotations have image IDs, class IDs, and boxes but no temporal object IDs; 26,646 frames were sampled from about 2,800 cameras. Useful to consider separately for a future detector-domain study, not as a dense single-camera tracking or flow-count reference. Its 90 GB image set was not downloaded. |
| [Traffic Surveillance Video Corpus](https://huggingface.co/datasets/thundarstrom/traffic-surveillance-video-corpus) | Its maintainer's card advertises continuous drives and CVAT track annotations under CC BY 4.0. | **Not an available fixed-camera source.** The card describes dashcam drives, not fixed surveillance views, and the host's current file inventory says the dataset is empty (2.34 KB card only). No media or annotations were downloaded. Do not infer data availability from the description alone. |
| [UTUAV urban traffic v2](https://videodatasets.org/UTUAV/index.html), B/C | The current publisher page documents per-frame `track_id` and MOT-format labels, including stationary vehicles. Its `SequentialGap300` split keeps the evaluation segment later in the same sequence, with 300 dropped frames between partitions. B/C are near-overhead UAV views. | **Best new access lead, not admitted.** The publisher limits use to research and requests contact with identity, institution and purpose; the 17.1 GB image download needs credentials, and the page also says to contact them for tracking IDs. Do not take the annotation link as independent access permission. Confirm terms for VisionTrack's private research, derived metrics and public aggregate findings, then check exact label/image versions and per-frame completeness. The oblique roadside-like A set is explicitly no longer maintained; v1 is historical and may be inaccurate. B/C UAV views are not automatically representative of a mounted angled traffic camera. No contact or file intake was made. |
| [MEVDT](https://pmc.ncbi.nlm.nih.gov/articles/PMC11720431/) / [publisher record](https://doi.org/10.7302/d5k3-9150) | A fixed, low-resolution grayscale/event camera over two traffic scenes; the paper reports 63 sequences, manual boxes and IDs at roughly 24 Hz. This is closer to the low-visual-information problem, though many sequences have only one labeled vehicle. | **Hold on repository access, rights and task power.** The publisher's Deep Blue endpoint returned HTTP 403 here on 2026-10-28. Its DataCite DOI metadata has no `rightsList` value; the article's open-access license is not proof of the dataset's media terms. The paper's per-sequence table shows that most sequences have one object ID, so select multi-object cases before treating this as an association test. No archive was downloaded. |
| [eTraM](https://github.com/eventbasedvision/eTraM) / [dataset documentation](https://eventbasedvision.github.io/eTraM/docs/eTraM%20Dataset%20Documentation.pdf) | Fixed traffic views over multiple scenes, weather and light; its documentation defines per-object IDs in annotations. | **Hold on modality and conflicting terms.** This is an event-camera dataset, while the current VisionTrack detector consumes ordinary image detections. The project README says CC BY-SA 4.0; the dataset documentation says CC BY-NC-SA. Resolve the actual asset terms and an honest fixed detector input before use. No event data was downloaded or converted. |
| [FLUID v2](https://figshare.com/articles/dataset/FLUID_A_Fine-Grained_Lightweight_Urban_Signalized-Intersection_Dataset_of_Dense_Conflict_Trajectories/29974954) / [publisher API](https://api.figshare.com/v2/articles/29974954) | CC BY 4.0 aerial intersection videos and derived per-frame object IDs, directions and trajectories could support a separate workflow/counting study. The publisher API lists three multi-GB video archives and smaller derived-data files. | **Hold for independent tracking truth.** The publisher's `README.md` describes trajectories extracted from processed video by its tracking framework, with detection confidence and interpolation flags. These are useful reference outputs, but cannot be treated as independently adjudicated ground truth against another tracker without a bounded manual audit. Camera is aerial, not a fixed roadside mount. Only the 22 KB README and metadata were read; no media or derived-data archive was downloaded. |

These are **source observations**, not a ranking of tracker performance or a
claim that other datasets are unusable. Terms can change; repeat this check at
the exact version and file level before handling media. A public webpage, an
open repository, and a code license are not interchangeable permission for
video, faces, plates, annotations, publication, or commercial use. A YouTube
watch page is a way to view a clip, not an automatic grant to copy, annotate,
redistribute, or use it as a benchmark.

**2026-10-29 HVSD update:** the original `Dataset.zip` and three locally
extracted MP4s passed byte correspondence. All decoded timestamps increase;
the night stream header says 352 frames, but the decoder yields 351. The small
rain clip completed an unchanged detector/tracker metadata-only smoke run.
The owner later reviewed all frames and supplied five distinct crossing marks;
the [bounded rain review](HVSD_RAIN_REVIEW.md) now includes a focused source-
window diagnosis of four unmatched marks and its limitations.
Details and exact receipts are in
[Public traffic video feasibility](PUBLIC_TRAFFIC_VIDEO_FEASIBILITY.md). This
replaces the earlier "no video was extracted" status for this local check;
there is still no independent dense GT or outcome score.

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

For MOT-format sources that supply both GT and detections, run the
[`numeric geometry screen`](../experiments/mot_detection_provenance.py) on an
explicit development-only pair before treating the supplied detections as a
separate detector. It pins file hashes and counts exact frame/box geometry
with duplicate multiplicity. An all-matching result requires provenance
review; a non-matching result still does **not** prove detector independence.
The screen does not check asset rights, labels against pixels, or test scenes.

Only after all five pass should we freeze a narrow protocol in Git **before**
the first comparative run. The first admitted source may support a useful
*external-domain research screen* without representing the blurred, angled
European cameras described by OpenTrafficCam. A transfer or product claim
requires evidence from the actual target setting and a real engineer's
decision, not only a public benchmark.

## Next executable path

- Keep the completed HVSD rain source-window diagnosis as *development*
  evidence. Dense independent identity truth, exact physical object linkage
  and the effect of alternative gate settings are still missing. Do not
  convert this short inspected clip into a general
  accuracy claim.
  Investigate a bounded I24V camera/time subset if its official download route
  becomes accessible; its manually corrected GPS subset is recall-oriented,
  not complete per-object single-camera truth. GRAM remains an official
  research candidate but its kit/image hosts are blocked here. UTUAV v2 B/C
  requires publisher contact and credentials; do not bypass that gate.
- Screen SVMOT's source provenance and annotation protocol before committing
  to its large archive. Its scene-level split is useful for a future research
  comparison, but the non-commercial license and missing local integrity/truth
  checks keep it out of product evidence today.
- When one candidate passes rights and integrity, make a source inventory and
  a small *development-only* annotation audit. Record any ambiguity before
  selecting a tracking variant.
- Separately ask one relevant engineer to name the costly decision, existing
  evidence workflow and acceptable review burden **before** demonstrating a
  proposed warning. Outreach or data transfer needs a fresh owner decision.
- The earlier two-person indoor rehearsal is optional and inactive at the
  owner's request. It is neither needed for traffic work nor a traffic benchmark.

This gate prevents more speculative tracker code while identifying exactly what
new evidence would justify implementation. VisionTrack C++ remains at the
accepted NumPy 0.3.0 / C++ 0.1.1 contract.
