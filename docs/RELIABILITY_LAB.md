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

### 2a. Ground-truth record

Ground truth is stored as `ground_truth.jsonl` and fingerprinted by
`ground_truth_sha256` in the source manifest. Ignore and distractor annotations
are preserved so evaluation policy can be applied later rather than discarded
during import.

| Field | Type | Rule |
|---|---|---|
| `frame_index` | integer | Zero-based, non-negative |
| `source_frame` | integer/null | Original dataset frame number |
| `object_id` | integer | Positive and unique within one frame |
| `xyxy` | array[4] | Finite pixel-space box with valid corners |
| `class_id` | integer | Original dataset class identifier |
| `visibility` | number/null | Finite and in `[0, 1]` when known |
| `ignored` | boolean | Preserves the dataset's consider/ignore flag |

The MOTChallenge importer accepts exactly the documented nine columns. It
converts only one-based frame numbering; spatial coordinates retain the same
convention already used by VisionTrack's MOT loader.

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
| `context` | object | Evidence hashes, correspondence boxes, and previous/current track IDs |
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

When verified ground truth and metrics are absent, `comparison.json` contains
only descriptive run diagnostics and marks quality claims as
`insufficient_evidence`. When they are present, the summary links measured
metrics and failure-event counts to their exact artifacts. Neither path selects
a winner automatically.

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

## Fourth implementation increment — complete

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

Implemented in `src/visiontrack/lab/comparison.py`. It revalidates every run's
identity, resolved configuration, detection hash, track hash, frame range, and
observation count before producing an immutable, content-addressed
`comparison.json`. It reports descriptive diagnostics and paired deltas but
leaves `accepted_variant` null. Ground-truth-dependent claims are recorded as
`insufficient_evidence`, with a machine-readable reason.

## Fifth implementation increment — complete

The next code change should establish ground truth as verified evidence:

- Define a strict portable ground-truth record with frame, object identity,
  pixel-space box, class, visibility, and ignore state
- Add deterministic JSONL storage and include its exact SHA-256 in the source
  manifest
- Import the supported MOTChallenge text fields with explicit one-based to
  zero-based frame conversion
- Reject duplicate identities per frame, invalid visibility, malformed boxes,
  unsupported coordinate assumptions, and hash mismatches
- Add a small dataset-free importer fixture and round-trip tests

It should not yet calculate HOTA/IDF1/MOTA or failure events. Metric integration
will follow only after the ground-truth evidence contract is independently
verified.

Implemented across `src/visiontrack/lab/contracts.py`, `storage.py`, and
`mot.py`. Ground-truth records preserve object identity, class, visibility, and
ignore state; serialize in deterministic frame/object order; and are verified
against the source manifest before a bundle is accepted. The strict importer
converts MOT's one-based frames to zero-based indices while retaining the
original frame number and all ignore/distractor rows.

## Sixth implementation increment — complete

The next code change should calculate quality metrics from only verified bundle
evidence:

- Group ground truth and track observations over the exact experiment frame
  range, including empty frames
- Apply the repository's existing MOT ignore/distractor policy rather than
  inventing a Lab-specific evaluator
- Calculate supported HOTA, IDF1, MOTA, MOTP, identity-switch, and
  fragmentation results for each variant
- Persist immutable `metrics.json` artifacts linked to run, track, and
  ground-truth hashes
- Update `comparison.json` to replace `insufficient_evidence` only for metrics
  that were actually computed from verified evidence
- Continue to leave `accepted_variant` null

Failure-event extraction, statistical claims across multiple sequences, human
acceptance decisions, and the React explorer remain separate later increments.

Implemented in `src/visiontrack/lab/metrics.py` using the existing
`visiontrack.eval.mot17.preprocess_frame` and `evaluate_frames` pipeline. Each
variant receives an immutable, content-addressed `metrics.json` linked to its
run, detection, track, and ground-truth hashes. Comparisons accept metric
artifacts only when every declared variant is present and verified, replace
only genuinely computed `insufficient_evidence` entries, and continue to leave
the accepted variant unset.

The shared CLEAR-MOT accumulator now also reports standard fragmentation
transitions as `Frag`, keeping this definition in the canonical evaluator rather
than creating a Lab-only calculation.

## Seventh implementation increment — complete

The next code change should make failures inspectable at frame level:

- Extract identity switches, fragmentations, misses, and false positives from
  the same preprocessed frame pairs used for metrics
- Assign deterministic event IDs and include bounded before/after evidence
  frame ranges
- Link every event set to its run ID, metric ID, track hash, and ground-truth
  hash
- Persist immutable `failures.jsonl` per variant
- Add verified failure counts to `comparison.json` without using those counts
  to select a winner
- Test crossings, ignored distractors, occlusion gaps, corruption, ordering,
  and rerun behavior with dataset-free fixtures

Multi-sequence statistics, video/frame rendering, human acceptance decisions,
and the React explorer remain later increments.

Implemented across `visiontrack.eval.mot` and `visiontrack.lab`. The canonical
CLEAR-MOT accumulator now emits identity switches, fragmentations, misses, and
false positives from the same correspondence used to calculate the published
metrics. The Lab converts those results into content-addressed `FailureEvent`
records with bounded evidence windows, persists immutable `failures.jsonl`
files, verifies their run/metric/input lineage, and reports per-variant counts
without changing the explicit human-decision boundary. Ignored MOT distractors
are filtered by the shared preprocessing path and therefore cannot become Lab
failures accidentally.

## Eighth implementation increment — complete

The next code change should make the verified bundle understandable without
introducing application state or a backend:

- Build a deterministic, read-only report model from `comparison.json`,
  `metrics.json`, and `failures.jsonl`
- Generate a local report entry point beneath the existing `report/` directory
- Show source/run fingerprints, paired metrics, deltas, and failure counts with
  links from a failure row to its bounded frame range
- Keep raw video optional and clearly label evidence that cannot be rendered
- Refuse incomplete, corrupt, or mismatched artifacts rather than displaying
  partially trusted results
- Add dataset-free snapshot and accessibility-oriented structure tests

The first report remains static and local. Interactive filtering, video/frame
rendering, human acceptance recording, and the React explorer follow only after
this presentation boundary is deterministic and tested.

Implemented in `src/visiontrack/lab/report.py`. Report generation first
revalidates the sealed comparison and every upstream run, metric, and failure
artifact. It then creates a content-addressed `report.json` view model and a
standalone `report/index.html` with experiment provenance, paired metrics and
deltas, failure counts, frame-level failure rows, bounded inspection ranges,
and explicit privacy and identity limitations. Both outputs are immutable and
contain no external scripts, fonts, images, or network dependencies.

The HTML displays at most 500 deterministically ordered failure events and
states when it has truncated that presentation. The canonical
`failures.jsonl` artifacts remain complete. Raw video and frames are not copied
or embedded, and variant acceptance remains unset.

## Next implementation increment

The next code change should establish the first product-facing Reliability Lab
screen without changing the verified Python pipeline:

- Define TypeScript types for the versioned `report.json` model
- Add a read-only React route using the existing Tailwind/shadcn design system
- Present the overview, paired metrics, failure taxonomy, provenance, and
  limitations from a checked-in deterministic fixture
- Include loading, unsupported-schema, missing-evidence, and empty-failure
  states
- Preserve keyboard access, semantic tables, mobile layout, and reduced-motion
  behavior
- Keep decisions disabled and clearly explain that track IDs are not person IDs

Local directory/file import, video rendering, event filtering, and acceptance
recording remain later increments. This first React slice proves the report
contract can drive a clear product screen without adding a backend or creating
a second source of truth.

## Acceptance criteria

This design increment is complete when:

- The first workflow has one unambiguous input, output, and user decision.
- Every persisted claim can be traced to an input hash and configuration hash.
- Existing tracker and benchmark APIs map into the schemas without behavior
  changes.
- Privacy and identity boundaries are explicit.
- The next implementation step is small enough to test without UI or datasets.
