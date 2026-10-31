# VisionTrack 0.4.0 release scope

Scope status: **frozen on 2026-10-30**

Release status: **candidate prepared; not tagged or published**

Candidate package version: **0.4.0** in both source declarations. The public
package remains **0.3.0**; these local artifacts are not a PyPI publication.
The audit baseline is `v0.3.0`. The candidate must pass its own local and hosted
gates at its final revision.

This release makes tracking failures easier to explain and measurements more
trustworthy. Its audience is computer-vision developers comparing local,
fixed-camera detector/tracker configurations. It adds diagnosis and corrects
scoring; it does not introduce a more accurate tracker.

## Package scope

| Area | Included change | Compatibility consequence |
| --- | --- | --- |
| Tracking runtime | Existing Kalman, assignment, ByteTrack lifecycle/configuration and public output behavior | No algorithm/default change relative to `v0.3.0`; no persistent identity |
| Measurement | Corrected CLEAR, fragmentation and HOTA definitions, dedicated evaluation IoU, explicit evaluator v2 | Newly computed scores/events can differ for identical saved tracks |
| MOT17 filtering | Explicit versioned preprocessing; new Lab metrics use schema 3, evaluator v2 and preprocessing v2 | Old metric schemas retain their own filtering/formulas; compare only matching definitions |
| Local diagnostics | `visiontrack lab-initiation`, public `build_initiation_trace`, bounded canonical `visiontrack.initiation-trace/v1` export | Optional, read-only replay with original detection keys, full warm-up and exact saved-output verification |
| Guided demonstration | `visiontrack lab-demo OUTPUT --with-initiation --write` prepares matching report, trace and guide together | Existing demo invocation remains available; output must be a new directory |
| Report integrity | Report content fingerprints, policy/failure lineage checks and immutable metric conflict preflight | Malformed, mixed or inconsistent records are rejected |
| Research helpers | Event-level selective re-entry scoring and grouped uncertainty utilities | Scores recorded decisions; does not implement a deployed re-identification gallery |
| Delivery | Isolated wheel/sdist core and Lab-extra installation checks, plus exact-commit/tag release guard | Core remains NumPy-only; Lab extra adds Pillow; no dev dependency becomes a runtime requirement |

Details: [corrected evaluator](EVALUATOR_V2.md),
[evaluation-policy migration](LAB_EVALUATION_POLICY.md), and
[initiation diagnostic](INITIATION_DIAGNOSTIC.md).

## Migration from 0.3.0

1. Keep historical bundles and published results. Existing metric schemas 1/2
   select their historical evaluator/filtering; they are not silently rewritten.
2. Use a **new bundle/output directory** when computing current-policy metrics.
   Re-scoring is a measurement change, not evidence of better tracking.
3. Record both evaluator and preprocessing identifiers beside a score. Do not
   compare across definitions as though only the tracker changed.
4. Historical source-frozen experiments must use their recorded revision;
   source guards remain strict. An upgrade does not authorize a new held-out run.
5. The diagnostic is opt-in. Its trace must match the selected report/run and
   saved outputs. Older reports can still be viewed; not every historical report
   contains enough lineage metadata to admit a new trace.

Python 3.10–3.12 remain the normal CI matrix. Core imports, tracking APIs,
video/webcam entry points and the canonical Python/C++ parity fixture remain
available. The public evaluation functions now implement corrected definitions;
that numerical change is intentional and is why this is a **pre-1.0 minor
release**, rather than a patch presented as output-equivalent. This version
choice does not imply a new algorithm or stronger accuracy.

## Website scope: deployed separately

The React `/lab` can explain individual failures, compare whole reports, verify
selected local report/image/playback files, and inspect an initiation timeline.
The curated `/lab/crossings` route explains retained rain observations and the
synthetic threshold trade-off separately. Documentation and learning guides
support these workflows.

These features are repository/site assets, **not a React app bundled in the
Python wheel**. Publishing PyPI does not deploy the site. Imported report/trace
files stay in tab memory; tests of their contracts are not interactive browser
QA or practitioner usability validation. Hosted deployment is a separate check.

## Research evidence and limits

- The initiation-threshold study completed 54 paired synthetic cells and 324
  repeatability passes. Earlier births recovered true crossings and also
  confirmed false proposals. It failed the registered no-harm gate; all 36
  controls were exact. Defaults stay unchanged.
- The box-gate and continuity-warning studies retain negative findings and
  their frozen methods. No rejected candidate becomes a production feature.
- Public traffic review and MOT17 diagnosis remain bounded evidence. They do
  not establish representative traffic accuracy, independent physical-identity
  truth, a novel state-of-the-art method or practitioner adoption.
- Research scripts, retained result records and source audits live in the
  repository; local datasets, videos and private outreach are not wheel content.

## Explicit exclusions

Persistent person recognition, cross-camera identity, hosted uploads/accounts,
automatic model/dataset downloads, accepted re-entry/gallery behavior, a
threshold/default change, a new C++ runtime port, a partnership claim and a
public accuracy claim are outside this release. Track IDs remain local labels.

## Candidate and publication checklist

- [x] Audit changes since `v0.3.0`, select `0.4.0`, freeze this scope and migration.
- [x] Verify the earlier installed-delivery checkpoint; candidate delivery is
      checked again below rather than inheriting that checkpoint's CI result.
- [x] Implement a release guard requiring matching tag/project/import versions,
      version-specific notes and latest successful main-push CI for the exact SHA.
- [x] Prepare `0.4.0` metadata and refresh only the version-dependent current
      demo/contracts; preserve historical evidence and its recorded versions.
- [x] Run complete Python, reference/parity, TypeScript/workflow, production app,
      strict docs and isolated distribution gates at the candidate revision.
- [ ] Verify hosted CI at that exact revision; retain artifact verification receipts.
- [ ] Create/push the release tag as the publication action, then verify PyPI
      files/digests/version and the GitHub release record.

Freezing this scope does not publish anything. If implementation scope changes,
update these notes and repeat affected gates before tagging.
