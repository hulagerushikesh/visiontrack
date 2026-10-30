# DroneTrafficZA2020 — bounded count-source intake

Checked 2026-10-30 from the [publisher's version 1 record](https://data.mendeley.com/datasets/wdfkxsnpzc/1)
and its [versioned file manifest](https://data.mendeley.com/public-api/datasets/wdfkxsnpzc/files?folder_id=root&version=1).
The record labels the release CC BY 4.0, says the video was captured by a
DJI Mavic Air above a South African freeway, and provides separate
vehicle-entry reference events. This is a possible **counting-task** source,
not dense tracking identity truth or a fixed roadside-camera transfer test.

## Exact small-file check

Only `groundTruth.csv` (5,134 bytes), `OpenDataCam.csv` (99,769 bytes),
`line_counter_config.json` (1,537 bytes), and `processOpenDataCam.py`
(12,976 bytes) were downloaded from the publisher. Their SHA-256 values match
the publisher manifest. Files and the generated `source-screen-v1.json` receipt
are kept outside Git at `../visiontrack-walkthrough/dronetrafficza-intake-v1/`.
The two videos (1,218,331,523 and 2,498,751,479 bytes in the manifest) were
not downloaded or decoded. The publisher's script was read, not executed.

The [source audit](https://github.com/hulagerushikesh/visiontrack/blob/main/experiments/dronetrafficza_source_audit.py) verifies
the exact count-file hashes and records:

| Check | Finding |
| --- | --- |
| Reference shape | 594 rows; 593 valid two-column rows; line 145 is `7626.c` rather than a two-column event. No repair is assumed. |
| Reference event range | Frames 58–33,672; valid classes: 454 cars, 134 trucks, four motorbikes, one person. |
| OpenDataCam event range | 974 valid eight-column records; frames 42–20,397; lines 1/2/3 have 326/327/321 events. |
| Uncovered interval question | 255 valid reference events occur after the last OpenDataCam event. This does **not** prove processing stopped there; it requires checking the video and processing interval. |
| Event definition | Reference labels first entry into the video frame for westbound traffic. OpenDataCam reports crossings of three configured lines, with both directions represented. Event times and counts are not directly interchangeable. |

The publisher's sample script compares cumulative counts on line 2 with the
reference, but that alone does not resolve the event definition or horizon
questions. The script's comments describe the eight OpenDataCam columns and
two reference columns; its stated `29.97` FPS is not a measured timestamp
audit. No VisionTrack tracker was run, and no comparative score was computed.

**Decision: hold.** This release can later support a bounded exploratory
counting study if the malformed reference row is independently resolved,
video/frame correspondence and the OpenDataCam processing interval are checked,
and a frame-entry versus line-crossing comparison rule is frozen before
scoring. It remains one drone scene without scene-disjoint validation or
independent dense box/ID annotations. It cannot close the current
fixed-camera tracking evidence gate or justify a C++ behavior change.
