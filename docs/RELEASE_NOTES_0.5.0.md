# VisionTrack 0.5.0 release notes

Scope status: **frozen on 2026-11-01**

Release status: **published on 2026-11-01**

Public package **0.5.0** was released from
`324c9135989537448b07244c982f246d39295399`, after
[exact-commit CI](https://github.com/hulagerushikesh/visiontrack/actions/runs/41325567170)
and the [publishing workflow](https://github.com/hulagerushikesh/visiontrack/actions/runs/41325995049)
passed. Public wheel/source bytes match the workflow artifacts; a fresh public
PyPI core/Lab installation passes both diagnostic and browser-import workflows.
[PyPI](https://pypi.org/project/visiontrack-mot/0.5.0/) ·
[GitHub release](https://github.com/hulagerushikesh/visiontrack/releases/tag/v0.5.0).
The comparison baseline is the immutable `v0.4.0` tag.

## What this release delivers

| Surface | Change since 0.4.0 | Boundary |
| --- | --- | --- |
| Local CLI | `visiontrack lab-association BUNDLE --variant NAME --frame F --track-id T --detection-index K [--json]` | One existing track and original detection key in one saved frame; no alternative tracker run |
| Python API | `visiontrack.lab.build_association_explanation` | Canonical `visiontrack.association-explanation/v1` record, full saved-run replay and exact public-output verification |
| Tracker observation | A private optional observation hook receives the actual production matrices and solver result | Ordinary calls retain the same computation and defaults; the source is not byte-identical to 0.4.0 |
| Installed delivery | Wheel/source CLI/API replay, producer/source identity, selector refusal and matching explanation fingerprints | Clean non-editable installs; no camera, detector model or data download |
| Current metadata | Project/import version 0.5.0 and a separate hand-built benchmark contract fixture | Historical releases, teaching exports, experiments and fixtures are preserved |

The diagnostic distinguishes an input pair never offered, hard gate failure,
cost rejection, eligible but unselected pairs, and a selected pair. It records
actual stage inputs, numeric limits and returned partners; it does not determine
physical identity or prove a counterfactual improvement. See the
[association walkthrough and limits](ASSOCIATION_DIAGNOSTIC.md).

This is a pre-1.0 **minor release** because it adds an optional public
diagnostic command/API. It is not an accuracy upgrade. Core dependencies remain
NumPy-only; the existing Lab extra and Python support are unchanged.

## Migration and compatibility

1. Existing 0.4.0 installations keep `lab-initiation` and the guided demo. They
   do **not** gain `lab-association` from a website update. Install the released
   tools with `python -m pip install --upgrade "visiontrack-mot[lab]==0.5.0"`.
2. Preserve existing bundles. The diagnostic reads a saved run and writes no
   files. Save `--json` output to a new file **outside** the sealed bundle.
3. Select a track that existed before the chosen frame's association and an
   original detection key, not an array position. Absent/newborn tracks and
   unknown detections are refused without partial JSON.
4. Initiation v1 and association v1 remain separate records. A newer diagnostic
   producer may inspect an older compatible run; input/configuration/output
   lineage still must match exactly. No historical record is relabeled 0.5.0.
5. Full replay and its input/output memory are required even though the export
   contains one selected frame/pair. Do not interpret a small JSON file as a
   constant-memory or bounded-runtime replay guarantee.

Python 3.10, 3.11 and 3.12 are the normal CI matrix. Schema validation and static
React checks are engineering gates, not browser interaction QA or practitioner
comprehension validation. C++ 0.1.1 retains its accepted Python 0.3.0 oracle;
the completed public Python 0.4.0 compatibility evidence is not silently
promoted to 0.5.0 acceptance. A new C++ release is outside this release scope.

## Website delivery is separate

The current site imports selected-pair explanations alongside checked local
initiation traces. Its optional no-install match-failure lesson uses original
synthetic exports and deliberately strict motion settings. The separate
confirmation demo retains its original published 0.4.0 exports. Both lessons
keep their honest producer metadata.

React, its prepared lesson assets and the deployed site are not bundled into
the Python wheel. Package publication does not prove website deployment or
close the outstanding browser/comprehension review. Imports remain in tab memory.

## Exclusions and research status

No tracker/default/threshold change, persistent person recognition, cross-camera
identity system, hosted upload service, new detector, C++ runtime port or new
dataset is included. Existing controlled negative findings remain negative.
No representative traffic accuracy gain, new research method, practitioner
adoption or commercial demand is claimed. The
[real-traffic evidence gate](REAL_TRAFFIC_EVIDENCE_GATE.md) stays open.

## Candidate and publication gates

- [x] Freeze the existing feature scope and migration; separate candidate,
      published package, website and research claims.
- [x] Prepare both 0.5.0 version declarations and a new current-producer contract
      fixture; preserve previous fixtures and prepared lesson exports.
- [x] Complete full Python/reference/regression, exact parity, web workflow,
      type/app, lint and strict documentation checks on this candidate.
- [x] Verify isolated wheel/source installs and retain matching report, trace
      and association IDs, artifact hashes and installed source identities.
- [x] Verify successful hosted main CI for candidate `a898b74`: all seven jobs
      pass in [run 41325219952](https://github.com/hulagerushikesh/visiontrack/actions/runs/41325219952).
      A read-only simulated-tag guard also passes; no tag was created.
- [x] With the owner's separate publication approval, create/push the matching release tag;
      verify public files, clean public installation and release provenance.

The release guard still refuses branch publication and mismatched tags, and
requires successful main CI at the exact tagged SHA. A green candidate is a
reviewable delivery result, not publication authorization or research acceptance.
If later documentation or source commits are selected for the tag, their own
exact-commit CI must pass; the checkpoint above does not substitute for it.
The published tag and files are now immutable. See the
[publication audit](RELEASE_READINESS.md) for exact file digests and limits.
