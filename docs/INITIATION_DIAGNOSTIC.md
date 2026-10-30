# Why did this detection not become a public track?

The local `lab-initiation` command explains the actual score and lifecycle
decisions in an existing Lab run. This turns the mechanisms explored in the
[threshold study](INITIATION_THRESHOLD_FINDINGS.md) into a reusable diagnostic.
It does not change the tracker or recommend a new configuration.

## Try it without a camera or dataset

From the current VisionTrack source checkout, install the Lab extra and create
one synthetic demonstration. Use a new output folder name if you repeat it:

```bash
python -m pip install -e '.[lab]'
visiontrack lab-demo ./lab-initiation-demo --write
```

The command prints a **bundle** path ending in a long fingerprint and a separate
**report** path. Replace `BUNDLE` below with the printed bundle path, not the
report file or the GitHub repository URL:

```bash
visiontrack lab-initiation BUNDLE --variant bytetrack --start 0 --end 10
```

This is a terminal diagnostic. It prints frame-by-frame explanations and writes
nothing. You do not need to import anything into the website or make a human
acceptance decision to use it. The source command is not yet in the published
0.3.0 wheel. A completed local bundle using your own detection records works
the same way; choose a variant declared in that bundle's manifest.

## Read the stages

For a stationary detection arriving on every frame with score 0.9 and the
default three-hit confirmation setting, the output progresses as follows:

| Frame | What happened | Public output |
| --- | --- | --- |
| 0 | Track 1 was born tentative; one hit | None |
| 1 | Another detection matched the tentative track; two hits | None |
| 2 | Third hit confirmed the track | ID 1 |
| 3, if no detection arrives | ID 1 survives internally and coasts | None |

Confirmation is not retrospective: it does not create public boxes for frames
0 and 1. One missed tentative match deletes the provisional track. A confirmed
track is deleted when its missed-frame age exceeds `max_age`. If you select a
window beginning later, earlier frames are still replayed to preserve this
history. Reported frame indices are absolute source indices. With `n_init=1`,
the current implementation still creates a tentative birth and confirms on a
subsequent matched update; the trace records that actual behavior.

Each detection has its original `(frame_index, detection_index)` key, score,
class, box and actual disposition:

| Disposition | Meaning |
| --- | --- |
| `below_low_score` | Below the recovery score; not offered for association |
| `unmatched_low_score` | Offered to unmatched confirmed tracks for recovery; not matched and cannot start a track |
| `below_birth_score` | A high-score proposal remained unmatched, but its score prevents a new birth |
| `spawned_tentative` | An unmatched high-score proposal actually created a provisional track |
| `matched_confirmed_high` | Matched a confirmed track in the high-score stage |
| `matched_confirmed_low` | Recovered a confirmed track in the low-score stage |
| `matched_tentative_high` | Matched a tentative track; its post-update state shows whether it confirmed |

Matching precedes birth admission: a 0.55 detection can update an existing track
even when it cannot start one at the default 0.60 birth threshold. A low-score
detection cannot start a track even if a configured birth threshold is lower
than the high-score threshold. The rows record decisions, not inferred intent.

## Export and integrity

```bash
visiontrack lab-initiation BUNDLE --variant bytetrack --start 0 --end 10 --json
```

`--json` emits only canonical JSON to standard output; errors go to standard
error with exit code 2. Redirect it to a **new file outside the bundle** if you
want to retain it. This is a separate `visiontrack.initiation-trace/v1` diagnostic,
not `report.json`. The Lab can inspect it after you import its matching report.

The exported record includes experiment/source/run IDs, detection and output
hashes, exact configuration, full replay range, selected range, frame decisions,
package/Python/NumPy versions and package source hashes. `trace_id` hashes its
canonical content without the `trace_id` field. There are no timestamps,
absolute local paths or image bytes. Local scene coordinates remain data you
should review before sharing an export.

The command verifies the bundle and saved run, replays the entire experiment
from its original boundary, and compares the canonical public-output SHA-256
against the saved output. A mismatch emits no trace. It uses the production
tracker's actual association and lifecycle methods; it does not implement a
second matcher. Bounds are 1–200 selected frames and at most 20,000 combined
detection/track rows. They bound the retained trace, not full-run replay time.
Choose a smaller window if a crowded trace exceeds the row limit.

Existing manifests, tracks, metrics, reports and decisions remain unchanged.
Historical report imports require no migration. No optional trace is created
by ordinary tracking or Lab comparison execution.

## Inspect the trace in the Lab

1. Open `/lab` and import the bundle's `report/report.json`.
2. Follow **Inspect track initiation** near the report heading, then choose
   **Import initiation trace**. Select the separate JSON exported above.
3. Use **Previous**, **Next** or the labelled frame slider. The three columns
   distinguish detector proposals, internal track states and public IDs.
   A tentative birth has no public output; an internally coasting confirmed
   track also has no public box in that frame.
4. Open **Configuration and provenance** for exact run/trace hashes and settings.
   **Close trace**, a new selection, report replacement or returning to the
   sample clears the active inspection. A canceled file-picker dialog keeps
   the current trace; closing the trace cancels pending reads.

This is optional. No acceptance decision, camera, footage or upload is needed.
All selected content remains in tab memory. The illustrative sample cannot
import a trace because it is not an imported, fingerprint-checked local report.

The browser checks structure, unique JSON keys, bounds, contiguous frame and
track history, cross-links, content fingerprint, experiment/source/run IDs,
detection/output hashes and full replay range. It reconstructs the saved run ID
from the exact Python config bytes and the report's saved observation count;
it does not duplicate Python presets/defaults. Python's `1.0` and `0.0` tokens
are preserved for these hashes. Reports without that run/count metadata can
still be viewed normally but cannot establish trace lineage.

Browser checks are **content/lineage checks, not authentication or another
tracker replay**. The producer's saved-output parity and source hashes are
recorded declarations here. The browser cannot prove that arbitrary submitted
metadata describes real detections or that a physical object was correctly
tracked. It rejects unsupported/oversized/inconsistent files before displaying
their trace. Report contracts and tracker behavior are unchanged.

The shared Python/browser conformance vectors cover all seven dispositions,
all seven lifecycle events, a single-stage preset, actual `n_init=1` behavior,
sparse original detection keys and a warm-up window. The workflow check also
creates a fresh complete synthetic bundle and imports both production variants
without modifying any bundle files. Browser interaction/visual QA remains
unverified in this session because browser access was previously denied;
component rendering, contracts, type checks and the production build are checked.

## What this cannot tell you

- A score or confirmed ID does not prove that an object is real or identified
  correctly. False proposals can also confirm.
- An unmatched proposal does not establish whether an IoU, class, Kalman gate
  or competing assignment caused rejection. Pair-level gate explanations are
  not part of this first diagnostic.
- IDs are local to one run. Internal survival, public boxes and physical
  identity are different things.
- This metadata-only command does not open footage or run a detector. It
  supports the same bundle-backed configurations as the comparison runner;
  external appearance, camera-shift and motion-model payloads remain unsupported.
- This improves inspectability, not measured tracking accuracy. A traffic
  improvement and a C++ behavior port still need the separate evidence gate.
