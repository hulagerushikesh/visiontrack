# Turning-traffic source screen

Written 2026-11-23 (plan item R2). A desk screen from public pages only.
**Nothing was downloaded.** Terms were read as published on that date. A
licence on a page is not the same as confirmed permission for the video, so
every candidate still needs the usual check at file level before use.

## Why this matters

Every traffic test so far used fixed cameras over mostly straight roads. The
gate was designed for crossing paths, and [R1](GATE_MISS_EXPLANATION.md) found
it mostly refuses vehicles whose box changes shape. Turning vehicles change
shape the most, so a junction is where a gate-off default is most likely to
hurt. That case is untested.

## What a usable source needs

1. Video or frames we may use, from a **fixed** camera, so our detector can run.
2. Per-vehicle identities as **image boxes** across frames, checked by people,
   not produced by a tracker.
3. Turning traffic at a junction or roundabout.
4. Clear reuse terms, and footage VisionTrack has never touched.

## Short list

| Source | Fits | Gaps | Terms |
|---|---|---|---|
| [GRAM-RTM Urban1](https://gram.web.uah.es/data/datasets/rtm/index.html) | Fixed camera at a busy junction; 23,435 frames, 237 vehicles, hand-labelled IDs (the labels are already in hand and gap-free) | Small; our detector must be run (light at 600 x 360) | Research use stated; **image rights unstated**; the owner sent the question to the group's address on 2026-11-24; no reply yet |
| [TUMTraf Intersection](https://mediatum.ub.tum.de/doc/1713265/rt2hb0lmor6xdmhv2tc0xdr0u.2306.09266.pdf) | Fixed roadside cameras, track IDs, left and right turns | Labels are mainly 3D; about 4,800 frames at 10 per second | CC BY-NC-ND 4.0: research use fits, but derived labels may not be shared |
| [SinD](https://github.com/SOTIF-AVLab/SinD) | Signalized junctions in four cities, track IDs, many left-turn conflicts | Drone view from above; positions and headings, not image boxes; whether video is included is not stated | Non-commercial; full data by emailed application |
| [Waterloo intersection](https://uwaterloo.ca/waterloo-intelligent-systems-engineering-lab/datasets/waterloo-multi-agent-traffic-dataset-intersection) | One junction, about 1 hour, IDs and turn labels, annotated videos | Drone view; map positions, not image boxes; labelling method not stated | **No licence stated** |
| [NGSIM Lankershim / Peachtree](https://catalog.data.gov/dataset/next-generation-simulation-ngsim-vehicle-trajectories-and-supporting-data) | Fixed elevated cameras over city junctions; video published | Trajectories are road positions made with semi-automatic software, with known errors; no image boxes | CC BY-SA 3.0 on the catalogue |

**Screened and not usable:** the Salzburg SIT-PET record (CC BY 4.0, but
tracker output and no video, 42 GB), the Region of York intersection set
(not released; tracks come from a tracker), the Cusco surveillance set (no
video, GPS points from a tracker) and a Tehran left-turn set (CC BY 4.0, but
no video). AI City, CityFlow, UrbanTracker and the other sources in the
[earlier screens](REAL_TRAFFIC_EVIDENCE_GATE.md) keep their status there.

## Recommendation

1. **GRAM-RTM Urban1 stays the first choice.** It is the only candidate with
   a fixed junction camera and hand-checked image-box IDs, and its labels are
   already in hand. It waits only on the image-rights answer. *Correction,
   2026-11-24:* this record first said the question was already being asked.
   It was not; no email had been sent. The owner sent it on 2026-11-24.
2. **TUMTraf Intersection is the second choice,** if its 2D boxes and IDs hold
   up and the owner accepts non-commercial terms that forbid sharing derived
   labels. Results could still be published as counts. Its pages confirm 3D
   boxes with track IDs but not 2D image boxes; a terms question covering
   this was sent by the owner to the dataset contacts on 2026-11-24.
3. The drone sets (SinD, Waterloo) and NGSIM cannot test the tracker as it is
   used: they have no image-box truth from a fixed camera. They could only
   support a motion-model study, which is a different question.

No candidate meets every need today. None should be fetched without the
owner's approval, with the file, source and size stated.

Sources: the pages linked above, and the
[York paper](https://arxiv.org/html/2511.12342v1),
[Cusco paper](https://arxiv.org/abs/2211.09342),
[Tehran record](https://data.mendeley.com/datasets/4xwymbdvr4) and
[SIT-PET record](https://zenodo.org/records/19231310).
