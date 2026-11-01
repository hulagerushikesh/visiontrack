# VisionTrack 0.5.1 patch candidate

Scope status: **frozen on 2026-11-02**

Release status: **candidate; not published**

This candidate packages two already verified checkout corrections since public
0.5.0. It adds no tracker feature or diagnostic command. Public 0.5.0 files and
tags remain unchanged; preparing this candidate does not authorize publication.

## What changes

| Surface | Correction | Practical effect |
| --- | --- | --- |
| Persisted Lab JSON readers | Reject repeated object fields, including nested and escaped spellings, and nonstandard nonfinite constants | An evidence file cannot silently choose the last of two conflicting scores or metadata values |
| Read-only initiation and association replay | Stream saved JSONL inputs and hash complete replay output incrementally | Avoid retaining whole-recording input/output lists just to explain a selected frame |
| Current producer metadata | Project/import version 0.5.1 and a separate hand-built benchmark contract fixture | Fresh exports identify the executing candidate; historical evidence keeps its original identity |

An otherwise valid, rehashed file containing repeated fields can be accepted
by public 0.5.0 with the last value winning. This candidate refuses it. Correct
bundles do not need migration. If a file is refused, resolve its ambiguity from
the original evidence rather than delete one value arbitrarily or rewrite hashes
to force acceptance. This is an input interpretation correction, not a blanket
security audit or proof that labels are true.

Streaming still validates the entire source, including rows outside a selected
window; checks saved counts/ranges and input hashes; replays the full experiment;
and requires the exact saved public-output SHA. Errors emit no partial JSON and
read-only commands leave the sealed bundle untouched. See the
[JSON reader boundary](RELIABILITY_LAB.md#validation-rules-for-the-first-implementation)
and [streaming measurements and limits](DIAGNOSTIC_REPLAY_SCALING.md).

## Compatibility and limits

- Commands, initiation v1, association v1, tracker source/defaults and core
  dependencies are unchanged. Older valid reports and fixed teaching assets stay
  supported and are not regenerated or relabeled.
- New producer versions/source hashes change diagnostic content IDs. Preserve
  each exported record with its own metadata; do not compare IDs from different
  producers as if they were identical evidence.
- The repeated 6,000-frame synthetic probe on this candidate measures about 79%
  lower Python allocation peak for replay than public 0.5.0, with the same
  diagnostic content excluding producer metadata and dependent IDs. It is not a
  process-RSS, speed, accuracy or population-scale storage claim.
- The tracker still retains active-track history. Full replay time grows with
  recording length. Comparison/evaluation and browser import limits are unchanged.
- C++ 0.1.1 and its accepted Python oracle are unchanged. The verified public
  Python 0.5.0 pairing does not automatically establish a published 0.5.1 pairing.
- Website instructions continue to name released 0.5.0 until a separately
  authorized publication. Package preparation is not deployment or browser QA.
- Representative permitted traffic data, independently checked labels and
  practitioner usefulness remain open research gates. No accuracy gain is claimed.

## Candidate gates

- [x] Freeze these two existing corrections; preserve historical releases,
      fixtures, lesson assets and tracker behavior.
- [x] Prepare matching candidate version declarations and current-producer fixture.
- [x] Pass full Python/reference/regression, exact parity/reset, lint, web
      contracts/types/app and strict documentation checks.
- [x] Build and check wheel/source artifacts in separate clean core/Lab installs;
      verify source identities, CLI/API fingerprints, ambiguity refusals and both
      Python-to-TypeScript diagnostic import workflows.
- [ ] Pass all seven hosted CI jobs at the exact candidate commit, then exercise
      the matching-tag release guard read-only without creating a tag.
- [ ] Obtain separate publication approval for the verified commit; only then
      tag/publish and verify public artifact bytes and a fresh public installation.

Until the last gate is complete, use the checkout for these corrections. Do not
try to install 0.5.1 from PyPI or interpret this candidate as a released package.

## Local candidate receipt — 2026-11-02

- **1,369 Python tests passed**, three skipped and one slow test deselected;
  includes the pinned metric reference and historical regression gates.
- All thirteen web contracts/workflows, private-review control check, TypeScript,
  production build, Ruff and strict MkDocs pass. These are offline/build checks,
  not browser interaction or practitioner-comprehension validation.
- Frozen tracker v1 output/reset digest remains
  `c1914cb7a4730122058a0c61ef739d7eeb1e137f99ca2c12677c3044ede30153`.
  Core/tracking source bytes are identical to the published 0.5.0 Git tree.
- Both isolated artifacts pass metadata checks, core-first/Lab-extra installs,
  all installed Python source checks, CLI/API replay, read-only bundle snapshots,
  two invalid-selector refusals and two duplicate-field refusals per install,
  plus both actual Python-to-TypeScript diagnostic workflows.
- Wheel/source export identities agree: report
  `01b011a497a38ae8053e5f130a750089e311877286569d4baf045092932b31cb`,
  initiation `d0134c9ac150a4d99dbb3b23ebbd9a29934288c9f1bef9f433ca3b96b62b4fd4`,
  association `31d767f1b95fbfd75adc70d8baa1362188b46f416435fc5c7340f1aca41c63ab`.
- In the separate same-machine Python 3.12.9 / NumPy 2.5.4 synthetic replay
  check, initiation allocation falls from 13,995,462 to 2,951,495 bytes;
  association falls from 13,995,755 to 2,951,548 bytes. All four 600/6,000-frame
  diagnostic pairs retain exact non-producer content and unchanged input files.
  Single-run `tracemalloc` allocation is not a statistical speed/RSS benchmark.

The local build hashes remain in the retained install receipt. A release workflow
will rebuild at the separately approved tag and verify those exact distributions;
it must not assume a local build's archive bytes equal the final public files.
