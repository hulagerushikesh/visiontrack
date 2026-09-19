# VisionTrack Reliability Lab — first vertical slice

## Decision

The first Reliability Lab release is a **local, reproducible comparison of
tracking configurations over one fixed detection stream**. It answers:

> Given these exact detections, which tracker configuration is safer to ship,
> where does it fail, and can another person reproduce that conclusion?

This slice reuses the current NumPy tracker, experiment hashing, metrics,
benchmarking, and error taxonomy. It does not introduce a server, user account,
database, detector-training workflow, or persistent identity system.

## First user

A computer-vision engineer who already has detections—or can run a detector—on
a representative clip and needs to compare a baseline with controlled tracker
variants. The first supported input during implementation is a synthetic or
existing VisionTrack cache. MOT-format import follows through the same contract.

## Minimum workflow

1. Select a local detection source and optional ground truth.
2. Inspect the source fingerprint, frame range, dimensions, and detector label.
3. Choose one baseline and one or more variants. Every variant receives the
   same immutable detection stream.
4. Run the comparison and save an immutable experiment bundle.
5. Review leaderboard metrics and identity-switch failure events.
6. Export the manifest, accepted configuration, and local report.

The first UI should expose this workflow. It should not become a general video
management dashboard.

## Contract principles

- **Local first:** paths and derived artifacts stay on the user's machine.
- **Same evidence:** paired variants always consume the same detections.
- **Immutable runs:** changing an input or configuration creates a new run ID.
- **Inspectable records:** JSON metadata and JSON Lines event records remain
  readable without the UI.
- **Content addressed:** source files, configuration, and code revision are
  fingerprinted before results are trusted.
- **Explicit coordinates:** all boxes declare pixel-space `xyxy` coordinates.
- **No hidden identity claim:** v1 contains track IDs only. It does not claim
  that separated tracklets belong to the same person.

## Versioned schemas

Every top-level record includes `schema_version: 1`. Unknown schema versions
must be rejected rather than guessed.

### 1. Source manifest

Describes the immutable sequence supplied to every run.

| Field | Type | Rule |
|---|---|---|
| `schema_version` | integer | Must equal `1` |
| `source_id` | string | Stable content-derived identifier |
| `kind` | string | `synthetic`, `visiontrack_cache`, or `mot` |
| `name` | string | Human-readable sequence name |
| `detection_sha256` | string | Hash of the exact detection payload |
| `ground_truth_sha256` | string/null | Null when ground truth is absent |
| `video_sha256` | string/null | Recorded only when a local video is selected |
| `detector` | object | Name, version/model, thresholds, and optional fingerprint |
| `frame_count` | integer | Positive number of frames |
| `width`, `height` | integer | Pixel dimensions |
| `fps` | number/null | Positive when known |
| `coordinate_space` | string | Must be `pixel_xyxy` in v1 |
| `created_at` | string | UTC ISO-8601 timestamp |

Raw video is referenced by local path during a session but is not copied into
the experiment bundle by default. Portable exports omit the path and retain
only its optional hash and public metadata.

### 2. Detection record

One line per detection, stored as `detections.jsonl` for the first portable
contract. Existing compressed NumPy caches may remain the internal fast path.

| Field | Type | Rule |
|---|---|---|
| `frame_index` | integer | Zero-based, non-negative |
| `source_frame` | integer/null | Original dataset frame number when different |
| `detection_index` | integer | Zero-based within the frame |
| `xyxy` | array[4] | Finite numbers with `x2 >= x1`, `y2 >= y1` |
| `score` | number | In `[0, 1]` |
| `class_id` | integer | `-1` means class-agnostic |
| `feature_ref` | string/null | Reference to an optional local embedding payload |

Embeddings do not belong inline in JSON. They remain optional array data keyed
by `feature_ref`, allowing the baseline to stay detector- and model-agnostic.

### 3. Experiment manifest

Defines one paired comparison before execution.

| Field | Type | Rule |
|---|---|---|
| `schema_version` | integer | Must equal `1` |
| `experiment_id` | string | Hash of canonical manifest content |
| `source_id` | string | Must resolve to one source manifest |
| `baseline` | string | Must name one variant |
| `variants` | array | Named `TrackerConfig` override objects |
| `metrics` | array | Requested metrics; ground-truth metrics require GT |
| `frame_range` | object | Inclusive start, exclusive end |
| `visiontrack_version` | string | Installed package version |
| `git_revision` | string/null | Revision when running from a checkout |
| `environment` | object | Python, NumPy, platform, architecture |
| `config_sha256` | string | Full canonical configuration hash |
| `created_at` | string | UTC ISO-8601 timestamp |

The existing short `config_hash` remains useful for display, but the Lab bundle
stores a full SHA-256 so it can serve as an acceptance artifact.

### 4. Track observation record

This is the portable form of the existing `TrackObservation` public output.

| Field | Type | Rule |
|---|---|---|
| `frame_index` | integer | Zero-based |
| `track_id` | integer | Positive within one run |
| `xyxy` | array[4] | Pixel-space box |
| `score` | number | Most recent matched detection score |
| `class_id` | integer | Same convention as detections |
| `state` | string | `confirmed` in v1 exported observations |

`track_id` is run-local. It is not a person identifier and must never be merged
across clips, sessions, cameras, or runs.

### 5. Failure event

The explorer needs structured events rather than prose embedded in HTML.

| Field | Type | Rule |
|---|---|---|
| `event_id` | string | Stable within the run |
| `run_id` | string | Variant run that produced the event |
| `frame_index` | integer | First frame where the failure is observed |
| `event_type` | string | `id_switch`, `fragmentation`, `miss`, or `false_positive` |
| `track_ids` | array[int] | Related predicted tracks |
| `ground_truth_ids` | array[int] | Empty when GT is unavailable |
| `context` | object | Occlusion, crowding, motion, confidence, and gate evidence |
| `evidence_frames` | object | Bounded before/after frame range for inspection |

Without ground truth, the Lab may show ambiguous association decisions but must
not label them as measured ID switches or fragments.

### 6. Comparison summary

The comparison contains:

- Per-variant metric summaries and paired deltas
- Statistical test and effect-size metadata where multiple paired units exist
- Failure-event counts by type and condition
- An explicit `insufficient_evidence` list
- The accepted variant, only when chosen by the user
- A reason recorded by the user or generated from declared acceptance rules

The system must distinguish “neutral” from “not enough evidence.”

## Immutable local bundle

```text
reliability-lab/<experiment_id>/
  manifest.json
  source.json
  inputs/
    detections.jsonl
    ground_truth.jsonl        # optional
    features.npz              # optional
  runs/
    <variant>/
      run.json
      tracks.jsonl
      metrics.json
      failures.jsonl
  comparison.json
  report/
    index.html
```

The bundle contains no raw video unless the user explicitly requests a
diagnostic export. A report may refer to a local video while it exists, but a
portable report must still work without that video.

## Validation rules for the first implementation

1. Reject non-finite coordinates, invalid boxes, invalid scores, duplicate
   detection indices, and frames outside the declared range.
2. Verify hashes before executing a saved manifest.
3. Require every paired variant to consume the same `source_id` and frame range.
4. Require ground truth for HOTA, IDF1, MOTA, ID-switch, and fragmentation claims.
5. Preserve deterministic ordering by frame, then record index or track ID.
6. Never overwrite an existing experiment directory with different content.
7. Record missing optional evidence explicitly rather than substituting zero.

## First implementation increment — complete

The next code change should implement only:

- Typed Python records for `SourceManifest`, `DetectionRecord`,
  `ExperimentManifest`, and `TrackObservationRecord`
- Canonical JSON serialization and SHA-256 calculation
- Validation and round-trip tests
- An adapter from the existing `Detection` and `TrackObservation` types

It should not yet implement the React explorer, file upload, video playback,
anonymous identity continuity, or a persistent database. Those depend on this
contract and will follow as separate reviewed increments.

Implemented in `src/visiontrack/lab/contracts.py`. The records reject unknown
fields and schema versions, serialize to canonical JSON, validate their v1
invariants, verify content-derived identifiers, and adapt the existing
`Detection` and `TrackObservation` public types without changing tracker
behavior.

## Second implementation increment — complete

The next code change should add only:

- Deterministically ordered JSON Lines readers and writers for detections and
  track observations
- Hash verification for a saved source manifest and its detection payload
- Creation of an immutable local bundle scaffold that refuses conflicting
  content at an existing experiment ID
- Focused tests for ordering, corruption, duplicate records, and overwrite
  protection

It should still avoid UI work, raw-video copying, a database, or execution of
tracker variants. Those will be connected only after the storage boundary is
portable and safe.

Implemented in `src/visiontrack/lab/storage.py`. Detection and track JSONL are
canonically ordered, duplicate and out-of-range records are rejected, exact
detection bytes are verified against the source hash, and bundle scaffolds are
created atomically. Repeating a write with identical content is safe; conflicting
content is never overwritten.

## Third implementation increment — complete

The next code change should connect this safe storage boundary to computation:

- Load and verify one bundle detection stream once
- Resolve declared baseline and variant overrides into existing `TrackerConfig`
  values without changing tracker behavior
- Replay the same in-memory detections and frame range through every variant
- Persist deterministic track observations beneath each variant's `runs/`
- Prove with tests that variants receive identical inputs and that a rerun never
  mutates accepted input evidence

It should not yet calculate benchmark claims, classify failure events, or add
the React explorer. Those become separate increments after repeatable paired
execution exists.

Implemented in `src/visiontrack/lab/runner.py`. The runner verifies and loads
the detection evidence once, resolves each declared variant onto the existing
tracker presets and `TrackerConfig`, creates fresh tracker state per variant,
replays the identical in-memory frame sequence, and atomically persists a
content-addressed `run.json` and `tracks.jsonl` for each result. Empty frames in
the declared range are replayed, and experiment inputs remain untouched.

Appearance features, learned motion residuals, and camera shifts are rejected
until those external inputs have their own bundle-backed contracts. This avoids
silently treating an unavailable signal as a valid ablation.

## Next implementation increment

The next code change should create an evidence-aware comparison summary:

- Record dataset-independent diagnostics such as observation count, unique
  run-local tracks, active frames, and paired deltas
- Mark HOTA, IDF1, MOTA, identity switches, and fragmentation as
  `insufficient_evidence` when ground truth is absent
- Persist one deterministic, immutable `comparison.json`
- Never select a winner automatically from track-count diagnostics
- Add corruption, rerun, and no-ground-truth honesty tests

Ground-truth import, measured failure events, acceptance decisions, and the
React explorer should remain later, separate increments.

## Acceptance criteria

This design increment is complete when:

- The first workflow has one unambiguous input, output, and user decision.
- Every persisted claim can be traced to an input hash and configuration hash.
- Existing tracker and benchmark APIs map into the schemas without behavior
  changes.
- Privacy and identity boundaries are explicit.
- The next implementation step is small enough to test without UI or datasets.
