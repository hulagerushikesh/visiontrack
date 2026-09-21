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

### 7. Optional image-evidence manifest

Image evidence remains absent unless a user deliberately creates it. One
content-addressed manifest belongs to one stored failure event and links its
source, run, event ID, event frame, bounded evidence range, and zero or more
local PNG artifacts.

Each artifact records a safe relative path, frame index, exact byte length and
SHA-256, `image/png` media type, pixel dimensions, `full_frame` or `crop` view,
and one explicit privacy classification: `source_pixels`, `redacted`, or
`synthetic`. Producer-created artifacts additionally record the SHA-256 of the
caller-supplied source frame and the exact crop/full-frame and redaction
operation. Older manually created manifests remain readable without these
additive production fields. Schema v1 intentionally accepts PNG only so its
signature, chunk envelope, CRCs, and IHDR dimensions can be validated without
adding an imaging library to the core runtime.

Full-frame artifacts must match the source dimensions; crops may be smaller but
never larger. Every artifact frame must fall inside the failure's evidence
range. The manifest itself may contain no artifacts, preserving a portable way
to say that image evidence was considered but not retained.

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
      evidence/               # absent unless explicitly created
        <event_id>/
          manifest.json
          frame-*.png         # optional, locally retained
  comparison.json
  report/
    index.html
```

The bundle contains no raw video unless the user explicitly requests a
diagnostic export. A report may refer to a local video while it exists, but a
portable report must still work without that video.

### Image privacy boundary

- **Full frames** can expose faces, screens, license plates, locations, and
  bystanders. Retain them only with appropriate rights and a specific diagnostic
  need.
- **Crops** reduce unrelated context but are not anonymous; a crop can still be
  biometric or otherwise identifying data.
- **Redacted artifacts** must be labelled `redacted`. The label records intent,
  not proof that redaction is sufficient for a particular law or deployment.
- **Synthetic artifacts** contain no source pixels and are preferred for tests,
  documentation, and reproducible examples.
- Evidence stays local, is never created by default, and is not embedded in the
  report or uploaded by this increment.

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

## Ninth implementation increment — complete

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

Implemented at `/lab` in the existing React application. The screen defines a
typed schema-v1 report boundary with runtime checks, renders a clearly labelled
deterministic fixture, and presents paired metrics, failure counts, selected
failure rows, provenance, and limitations through the shared light product
shell. Loading, unsupported-schema, missing-evidence, and empty-failure states
are explicit. Variant selection is visibly disabled and track IDs remain
labelled as run-local rather than person identities.

The route is available from both React and standalone navigation, works at the
mobile breakpoint, respects reduced-motion preferences, and introduces no
network fetch, local-file access, backend, or second metric calculation.

## Tenth implementation increment — complete

The next code change should let a user inspect their own generated report while
preserving the same local-first boundary:

- Add an explicit `report.json` file picker on `/lab`
- Parse the selected file entirely in browser memory; never upload it
- Strengthen runtime validation for nested experiment, source, variant,
  failure, decision, and limitation fields
- Show the selected filename and report fingerprint so the active evidence is
  unambiguous
- Provide a deliberate “return to sample” action
- Test valid import, malformed JSON, unsupported schema, incomplete evidence,
  and repeat selection

Directory access, raw bundle import, video/frame rendering, failure filtering,
and acceptance recording remain separate later increments.

Implemented on `/lab` as an explicit browser file import. The selected
`report.json` is read directly with the browser File API, parsed only in memory,
and never uploaded or sent through a network request. The active filename and
content-addressed report fingerprint stay visible, and the user can deliberately
return to the checked-in illustrative sample.

Runtime validation now covers the nested experiment and source provenance,
frame and media bounds, consistent metric sets, variant and baseline lineage,
failure-set hashes and counts, event/run relationships, presentation totals,
human-decision boundary, and stated limitations. Malformed JSON, unsupported
schema versions, and incomplete or inconsistent evidence produce explicit
error states while leaving the importer available for retry.

## Eleventh implementation increment — complete

The next code change should make large verified failure sets easier to inspect
without changing evidence or adding a backend:

- Add client-side filters for variant and failure type
- Add frame search and a deliberate reset action
- Show the active subset and total event counts without recomputing metrics
- Add an accessible event-detail panel for context and lineage fields already
  present in `report.json`
- Keep filter state ephemeral and keep variant acceptance disabled
- Test empty results, combined filters, keyboard operation, and reset behavior

Video/frame rendering, directory or raw-bundle import, and acceptance recording
remain separate later increments.

Implemented as an ephemeral explorer over only the failure events carried by
the active, validated report. A user can combine variant and failure-type
filters with an exact frame lookup, see both the matching displayed subset and
the verified total, reset deliberately, and inspect the selected event's
context, run fingerprint, event fingerprint, and evidence-frame range.

The controls are native keyboard-operable form elements, filter changes clear
stale selection, empty results remain explicit, and importing or returning to a
different report resets the explorer through the report fingerprint. No metric
is recomputed, no filter is persisted, and the detail panel continues to label
track IDs as run-local rather than persistent person identities.

## Twelfth implementation increment — complete

Before displaying video or frames, the next code change should define the media
evidence boundary for local Reliability Lab bundles:

- Define a versioned, content-addressed evidence-manifest record linking an
  event ID and frame index to an optional local image artifact
- Validate artifact hashes, media type, dimensions, and source/run lineage
- Generate no media by default and preserve the current report-only workflow
- Document explicit privacy guidance for full frames, crops, and redaction
- Add deterministic contract and storage tests using synthetic image bytes

Browser directory access, image rendering in React, raw video playback, and
acceptance recording remain separate later increments.

Implemented with `EvidenceImageArtifact` and `EvidenceManifest` contracts plus
an atomic `write_evidence_manifest` storage boundary. Manifests are
content-addressed, canonically order their optional artifacts, and verify
source/run/event lineage and evidence-frame bounds against the stored source
and failure records. Image bytes are checked against their declared size,
SHA-256, PNG signature and chunk CRCs, and IHDR dimensions before any artifact
directory is committed.

The matching reader revalidates lineage and every declared payload and rejects
missing, extra, symlinked, or modified files rather than returning partial
evidence.

Evidence is stored only after an explicit API call beneath
`runs/<variant>/evidence/<event_id>/`; normal experiment, comparison, report,
and UI paths create nothing there. Repeated identical writes are safe,
conflicting writes are refused, and all tests use generated synthetic PNG bytes.

## Thirteenth implementation increment — complete

The next code change should surface optional media availability in the
deterministic report model without rendering or copying image bytes:

- Discover only stored evidence manifests linked to displayed failure events
- Revalidate each manifest, artifact hash, and lineage during report generation
- Add privacy classification and availability metadata to `report.json`
- Keep the standalone and React reports text-only in this increment
- Reject corrupt or orphaned evidence instead of silently omitting it

Browser directory access, image rendering, raw video playback, and acceptance
recording remain separate later increments.

Implemented in deterministic report generation by discovering evidence only
under the verified variant and failure-event lineage. Every stored manifest and
PNG artifact is re-read and revalidated before report creation; orphaned event
directories, unexpected entries, changed bytes, invalid PNG structure, and
lineage mismatches fail the report rather than disappearing from its evidence.

Each failure now carries a metadata-only media status (`not_declared`,
`declared_empty`, or `available`), content fingerprint, artifact count, frame
indices, views, and privacy classes. The report summary counts verified
manifests, images, and artifact privacy classifications across the complete
failure set before presentation truncation.

The standalone and React reports display only this availability and privacy
metadata. They do not copy image bytes into `report.json`, emit image elements,
create browser object URLs, or otherwise display source pixels. Existing
schema-v1 reports without the additive metadata remain readable, while reports
that declare the new summary must provide valid per-event metadata.

## Fourteenth implementation increment — complete

The next code change should provide an explicit, privacy-aware producer for the
optional evidence format before any UI attempts to display it:

- Accept caller-provided local PNG frames for one verified failure event
- Default to a bounded crop and require an explicit choice for full-frame
  source pixels
- Record `synthetic`, `redacted`, or `source_pixels` from the operation that
  produced the bytes rather than trusting a later UI label
- Refuse out-of-range frames, oversized output, ambiguous crop bounds, and
  overwrite conflicts
- Add deterministic synthetic tests; do not add video decoding, uploads, or
  browser rendering in the same increment

Browser directory access, image rendering, raw video playback, and acceptance
recording remain separate later increments.

Implemented as the opt-in `produce_failure_evidence` Python API, available with
the `visiontrack-mot[lab]` extra. The caller supplies a mapping of verified
failure-range frame indices to local full-frame PNG bytes. Nothing scans a
directory, decodes video, accesses a camera, or uploads data implicitly.

The default view is a crop. A caller may provide an integer `crop_bounds`
rectangle, or the producer derives one deterministically from the failure's
stored ground-truth and track boxes with bounded padding. Missing or malformed
boxes require explicit bounds rather than guessing. Every input PNG is checked
for size, structure, CRCs, source dimensions, frame range, and single-frame
decodability before the producer writes anything.

Privacy is derived by the producer operation: synthetic source manifests yield
`synthetic`; applying the built-in whole-image pixelation yields `redacted`;
otherwise non-synthetic pixels remain `source_pixels`. Unredacted full-frame
source pixels require `allow_full_frame_source_pixels=True`. Each artifact
records the input-frame hash and exact production operation, so the stored
privacy metadata is tied to immutable provenance instead of being editable UI
copy.

Artifacts are capped by frame count, input bytes, source pixels, output pixels,
and output bytes. Identical repeated production is idempotent, while a second
operation that would change an existing event directory is refused by the
immutable evidence writer.

Example:

```python
from visiontrack.lab import produce_failure_evidence

manifest_path = produce_failure_evidence(
    bundle,
    "baseline",
    event_id,
    {42: frame_png},
    crop_bounds=(120, 80, 420, 520),
)
```

## Fifteenth implementation increment — complete

The next code change should expose this producer through a deliberate local CLI
workflow without broadening its privacy boundary:

- Select one bundle, variant, failure event, and explicit `FRAME=PNG_PATH`
  inputs
- Preview the resolved crop, privacy class, and output limits before writing
- Require a confirmation flag for unredacted full-frame source pixels
- Return the content-addressed manifest path and a concise artifact summary
- Keep video decoding, directory scanning, browser rendering, and uploads out
  of the command

Browser directory access, image rendering, raw video playback, and acceptance
recording remain separate later increments.

Implemented as the `visiontrack lab-evidence` command. It requires one bundle,
variant, failure-event fingerprint, and one or more explicit
`--frame FRAME=PNG_PATH` arguments. It never searches directories or infers a
frame filename.

The default invocation is preview-only. It validates bundle and event lineage,
frame bounds, crop geometry, privacy classification, output dimensions, and
fixed resource limits, then exits without reading any PNG input or writing an
artifact. `--write` performs the previewed operation. Unredacted full-frame
non-synthetic pixels remain blocked unless the independent
`--allow-full-frame-source-pixels` confirmation is also present.

The write path rejects duplicate frame numbers, symbolic links, missing or
non-regular files, and inputs already over the byte limit before reading them.
The producer then performs the complete PNG and evidence validation described
above. Success prints the content-addressed evidence ID, artifact count, and
manifest path; errors return a non-zero status without a traceback or partial
evidence directory.

Example preview and deliberate write:

```bash
visiontrack lab-evidence "$BUNDLE" baseline "$EVENT_ID" \
  --frame 42=frame-42.png --crop 120,80,420,520

visiontrack lab-evidence "$BUNDLE" baseline "$EVENT_ID" \
  --frame 42=frame-42.png --crop 120,80,420,520 --write
```

## Next implementation increment

The next code change should let the React Reliability Lab inspect locally
selected evidence without weakening the validated boundary:

- Select one manifest and its explicitly declared PNG files; do not scan a
  directory or upload anything
- Verify manifest structure, event/report lineage, file names, SHA-256 hashes,
  PNG dimensions, and privacy metadata in browser memory
- Show metadata first and require a deliberate reveal action before creating an
  object URL for `source_pixels`
- Revoke every object URL when the evidence, report, or route changes
- Keep raw video playback, automatic bundle import, and remote storage out of
  the same increment

Acceptance recording and raw video playback remain separate later increments.

## Acceptance criteria

This design increment is complete when:

- The first workflow has one unambiguous input, output, and user decision.
- Every persisted claim can be traced to an input hash and configuration hash.
- Existing tracker and benchmark APIs map into the schemas without behavior
  changes.
- Privacy and identity boundaries are explicit.
- The next implementation step is small enough to test without UI or datasets.
