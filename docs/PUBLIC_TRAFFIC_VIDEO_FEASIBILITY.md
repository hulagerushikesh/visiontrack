# Public traffic video: first local feasibility screen

Checkpoint: **2026-10-29**. The owner cannot make a private traffic recording.
This route uses publisher-hosted public footage instead. Being viewable on YouTube
or another website is not by itself a dataset license or tracking ground truth.

## Source and permitted scope

The [HVSD V1 publisher page](https://data.mendeley.com/datasets/zdgmdg7p25/1)
lists `Dataset.zip` under **CC BY 4.0** with day, night and rainy highway clips.
The clips were previously downloaded from that page into the owner-local
`visiontrack-walkthrough/traffic-hvsd-v1/` directory. The original archive's
SHA-256 matches the publisher-listed receipt recorded in the
[source gate](REAL_TRAFFIC_EVIDENCE_GATE.md). Media, extracted frames and model
weights remain outside Git; public reuse would need source attribution and a
separate check for identifiable details. This is a source-level research screen,
not legal or privacy clearance for every possible reuse.

## Exact local source check

`experiments/hvsd_video_intake.py` verifies the pinned archive, the three
extracted MP4 bytes against their ZIP members, and every decoded frame's
dimensions and presentation timestamp. It does not trust nominal FPS as a
timeline. All three clips have strictly increasing frame timestamps and stable
dimensions:

| Clip | Decoded frames | Last frame PTS | Dimensions | Stream header count | Timing observation |
| --- | ---: | ---: | ---: | ---: | --- |
| day | 149 | 4.938267 s | 3840 × 2160 | 149 | 0 irregular gaps at >5% of median |
| night | 351 | 14.000000 s | 1280 × 590 | **352** | Header overstates decoded frames by one; 0 irregular decoded gaps |
| rain | 194 | 6.439767 s | 704 × 432 | 194 | 0 irregular gaps at >5% of median |

These are short excerpts, not full-shift surveillance. Night's 352-versus-351
discrepancy is retained as a source issue; never calculate an event's frame
index or duration solely from the stream header. The intake reports no
independent dense GT for any clip.

Reproduce locally (requires `ffprobe` and the owner-local original files):

```bash
python -m experiments.hvsd_video_intake \
  --archive ../visiontrack-walkthrough/traffic-hvsd-v1/Dataset.zip \
  --video-dir ../visiontrack-walkthrough/traffic-hvsd-v1/video
```

## One unchanged pipeline smoke run

The `rain.mp4` clip was chosen as a small, angled and visually degraded road
scene. `experiments/hvsd_rain_screen.py` reads all 194 frames with the existing
local YOLOX nano model, keeps COCO vehicle classes 2/3/5/7, and passes the same
detections to unmodified `ByteTracker()` defaults. The script verifies exact
source/model hashes, does not write media, and reports only metadata:

| Output | Observed value |
| --- | ---: |
| Decoded frames | 194 |
| Detector boxes | 310 |
| Frames without a retained detection | 57 |
| Public tracker boxes | 117 |
| Distinct public run-local track IDs | 4 |
| Maximum simultaneous public tracks | 2 |
| Canonical per-frame count/ID receipt | `0125e1e9644e0df9fb36d3c1353c8e328dd7fc1e03d8117299af0e0afe4f49c6` |

```bash
python -m experiments.hvsd_rain_screen \
  --video ../visiontrack-walkthrough/traffic-hvsd-v1/video/rain.mp4 \
  --model models/yolox_nano.onnx
```

The 57 frames without detections are an **output observation**, not 57 known
missed vehicles: some frames may have no target vehicle. Four track IDs do not
mean four physical vehicles, correct continuity or four flow counts. There are
no independent box/ID/flow labels to decide that. The 416-pixel detector input
also reduces the source image; any later study must freeze detector preprocessing
and separate detector misses from association errors. No tracker setting, C++
behavior, website claim or default is changed by this smoke run.

## Next evidence step

For a bounded real-clip *development* case, choose a predeclared rain or night
window and one question (for example, whether a vehicle crossing a marked line
is reported). Freeze the exact decoded timestamps, vehicle class scope, line,
detector and review rubric **before** inspecting comparative outcomes. Create
independent human event/ID labels from the permitted source, retaining
`uncertain` cases. An assistant-only visual guess is exploratory and cannot
serve as independent truth. A held-out outcome claim also requires a different
uninspected clip/site; three short HVSD excerpts from unclear camera provenance
do not establish target-domain generalization.

For a stronger fixed-camera source, the [I-24 MOTION I24V documentation](https://github.com/I24-MOTION/i24-video-dataset-utils#data-use-agreement)
explicitly allows academic and commercial use and derivative products while
prohibiting individual re-identification. It supplies fixed roadside video,
detections and manually corrected GPS trajectories for 270 vehicle passes, not
dense IDs for all visible vehicles. Its download endpoint returned a rejection
from this machine on 2026-10-29, and its large scale makes a small camera/time
subset essential. It remains an access/task-fit lead, not an admitted result.
