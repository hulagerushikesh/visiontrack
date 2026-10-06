# VisionTrack 0.3.0 release notes

Scope status: **frozen on 2026-10-06**

Release status: **published on 2026-10-06**

Public package version: **0.3.0**

Version `0.3.0` is the first Reliability Lab release. It turns VisionTrack's
research and evaluation machinery into a local, reproducible workflow for
comparing tracker configurations, inspecting failures, retaining deliberately
selected evidence, and recording a human decision. It does not turn track IDs
into persistent person identities and it does not add a hosted data service.

## Included in the PyPI package

### Reliability Lab v1

- Versioned, canonical records for sources, detections, ground truth, runs,
  comparisons, failure events, evidence, synchronized playback, and decisions.
- Immutable local bundle storage with content fingerprints and full lineage
  validation before derived artifacts are trusted.
- Paired tracker comparison over one detection stream, verified CLEAR-MOT,
  IDF1, and HOTA metrics when ground truth is present, and explicit
  `insufficient_evidence` results when it is not.
- Deterministic failure extraction for ID switches, fragmentation, false
  positives, false negatives, and localization errors.
- Standalone local HTML and canonical JSON reports.
- Privacy-aware, opt-in PNG evidence production with preview-first writes,
  bounded crops, deterministic redaction, and explicit full-frame consent.
- Fingerprinted human decisions with preview-first creation and strict import
  of browser-downloaded records.
- Content-addressed synchronized failure-playback metadata with exact lineage,
  privacy, frame availability, and missing-frame semantics.
- A dataset-free synthetic onboarding bundle.

The new CLI surface is:

```text
visiontrack lab-demo
visiontrack lab-evidence
visiontrack lab-decision
visiontrack lab-decision-import
visiontrack lab-playback
```

### Reproducibility and runtime parity

- `visiontrack parity-contract` verifies the canonical dataset-free
  `visiontrack.tracker-parity/v1` fixture, its SHA-256 identity, exact public
  tracker output, and deterministic reset behavior.
- The same fixture is enforced by the public `visiontrack-cpp` binding. Strict
  machine-readable evidence records both implementation revisions, successful
  CI runs, and the exact numerical/toolchain reproduction context.
- Structured benchmark reports carry dataset, protocol, configuration, metric,
  significance, and provenance fields instead of relying on rendered tables.

### Compatibility

- Existing `ByteTracker`, `TrackerConfig`, `Detection`, video, webcam, and
  evaluation entry points remain available; `0.3.0` does not deliberately
  break the `0.2.0` tracking API.
- Python 3.10–3.12 remain covered by normal CI.
- The core installation remains NumPy-only. Install `visiontrack-mot[lab]`
  only when local PNG evidence production is needed; that extra adds Pillow.
- Reliability Lab records use schema version 1. Unsupported or malformed
  schemas are rejected rather than partially interpreted.

## Included in the project website

These repository and website improvements ship with the project but are not
code embedded in the PyPI wheel:

- A unified light-first React product shell for the landing, live tracker,
  research, benchmark, learning, documentation, and Reliability Lab routes.
- A private-by-default `/lab` interface that imports explicitly selected local
  report, decision, playback, and PNG files into browser memory.
- A validated benchmark explorer and results hub.
- Synchronized playback controls with exact PNG verification, deliberate image
  reveal, missing-frame states, keyboard support, and reduced-motion behavior.
- Guided learning modules and dataset-free exercises.

## Explicitly not in 0.3.0

- Persistent recognition, face recognition, cross-camera identity, or claims
  that a returning person will retain the same ID.
- The proposed bounded anonymous identity-continuity gallery. It remains a
  Python-first research program requiring evaluation of abstention, expiry,
  eviction, privacy, and memory behavior.
- Accounts, a backend, cloud uploads, remote bundle storage, collaboration, or
  automatic directory scanning.
- Automatic raw-video ingestion into Reliability Lab bundles or automatic
  model/dataset downloads.
- A chosen market vertical or claims of practitioner validation. Interviews
  and design-partner validation remain the next product-discovery gate.
- New C++ tracker behavior. `visiontrack-cpp` remains a separately versioned
  package and consumes only accepted synchronization contracts.
- Compute-blocked SportsMOT and DanceTrack detector experiments.

## Known limitations

- Reliability Lab is a technical alpha intended for local research workflows,
  not a multi-user production service.
- Users must provide legal, local detections, optional ground truth, and any
  deliberately retained PNG evidence.
- The browser does not persist imported files or write into bundles. Pixel
  evidence is unavailable until the user explicitly selects matching files.
- Track IDs are temporary labels inside one tracking sequence. They are not
  identities and must not be presented as such.

## Remaining release gates

- [x] Freeze the exact `0.3.0` scope and user-facing notes.
- [x] Complete Python/C++ fixture parity and synchronization provenance.
- [x] Remove the setuptools license metadata deprecation.
- [x] Make repository source/evidence links explicit and pass MkDocs in strict mode.
- [x] Bump both package version declarations from `0.2.0` to `0.3.0`.
- [x] Re-run the complete Python, browser, documentation, and distribution gates.
- [x] Update CI and release workflows to Node 24-compatible official action majors.
- [x] Create and push `v0.3.0`, then verify the GitHub Release and public PyPI artifact.

Release verification: the tag points to `850e1b8`; GitHub Actions built and
published the wheel and sdist through trusted publishing; both artifacts are
visible in the public PyPI JSON API; and the GitHub Release record is public.
