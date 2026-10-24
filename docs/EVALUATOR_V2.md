# Evaluator v2: corrected measurements, unchanged tracking

Checkpoint: **2026-10-24**. The [metric discrepancy](REAL_DATA_METRIC_CHECK.md) is
now corrected at the **same-preprocessed-input metric level**. All **45 checks**
against the pinned TrackEval implementation pass: integer counts exactly, floats
within the prospectively fixed **1e-10** tolerance. No tracker rerun or tuning.

## Outcome in plain language

We corrected the measuring instrument, not the tracker. The same saved boxes now
receive reference-aligned scores. This is necessary for trustworthy comparisons,
but it is **not improved tracking accuracy** or proof the labels are correct.

| Metric | Historical v1 | Corrected v2 / pinned reference |
| --- | --- | --- |
| TP / FN / FP | 25,732 / 21,825 / 49 | 25,732 / 21,825 / 49 |
| ID switches | 43 | **44** |
| Fragmentations | 148 interruptions | **108 resumed segments beyond the first** |
| HOTA | 0.5255496552414854 | **0.5237264889973016**, within numerical precision |
| IDF1 | 0.6132155226485587 | **0.6132155226485587** |

The largest absolute difference among checked scalar results is
**3.552713678800501e-15**. All 19 HOTA thresholds also pass. This corrects the
previous failing check; it does not overwrite it or turn it into a historical pass.

## What changed

- **HOTA:** normalize per-frame similarity contributions by competition for both
  boxes; combine global identity alignment with local similarity; assign once
  per frame and only then apply each alpha threshold. This replaces the v1
  alpha-dependent matching and unnormalised potential.
- **CLEAR:** separate previous-timestep priority from last-ever matched ID;
  optimize the thresholded weighted assignment rather than greedily preserving
  stale correspondences. MT is strictly **greater than** 80%, as in the reference.
- **Fragmentation:** emit/count it at the resumed match, not at a terminal miss.
  Its new event carries the current and previous hypotheses and matched boxes.
- **Evaluation geometry:** use a dedicated IoU routine without the tracker's
  small-area denominator floor. The tracking geometry and all tracking/input
  source fingerprints remain unchanged.
- **Empty identity input:** no reference or tracker detections gives IDF1/IDP/IDR
  zero, not an unsupported perfect score. Invalid HOTA thresholds are rejected.

Pinned-reference edge conventions are explicit: a timestep with an entirely
empty GT or tracker side carries CLEAR's priority map forward. The reference's
all-empty sequence early return leaves its `CLR_Frames` metadata at zero;
our accumulator still reports frames actually received. Empty-input tests make
that metadata distinction explicit rather than claiming universal field identity.
The current implementation retains our own NumPy/Hungarian core, not a new
production dependency on SciPy or TrackEval. Tests cover crowded inputs,
ambiguous assignments, deterministic ties, empty cases, small boxes and boundaries;
this is not a proof of identical tie-specific identities for every possible input.

## What changed in this actual case

All **1,050 saved scored frame pairs** were read unchanged from the sealed
MOT17-04-FRCNN baseline. No detections, public tracker boxes or preprocessing were
changed. A separate v2 failure stream and full-precision scores were produced.

The first switch remains reference **85**, **19 → 31** at source frame **54**
under v2. The previous actual association/lifecycle trace remains applicable;
the physical-person interpretation still needs independent visual review.

The changed switch history is specific:

| Source frame | Historical v1 | V2 |
| --- | --- | --- |
| 973, reference 68 | No switch event | **22 → 70** |
| 1006, reference 68 | **22 → 107** | **70 → 107** |

This accounts for the net **one additional switch**. These are scorer events,
not newly introduced tracker behavior. All old/new differences are retained:
**164 added** events (108 fragments, 54 misses, 2 switches), **203 removed**
(148 fragments, 54 misses, 1 switch). FP events are unchanged. Equal total FN
therefore does **not** imply the same missed reference objects per frame.
The old coverage partition remains a historical v1 finding until re-derived for
the corrected correspondence; do not reuse it as a v2 recoverability budget.

## Compatibility: old reports must not change silently

Metric artifacts now write **schema v2** with the content-addressed evaluator
identifier **`visiontrack.metrics/v2`**. Existing schema-v1 metric artifacts
implicitly mean **`visiontrack.metrics/v1`**. The generic report/experiment/run
schemas are not all renamed to v2; only the metric artifact is versioned here.

- Exact v1 evaluator source is retained in `_legacy_mot.py` / `_legacy_hota.py`
  from revision `121c755`, apart from a leading provenance comment.
- V1 artifacts retain old scores, interruption events, IDs and hashes. Legacy
  failure extraction uses the legacy accumulator; new extraction uses v2.
- New failures include the evaluator in their hashed context. Mixed definitions,
  unknown evaluators and mismatched failure lineage are rejected.
- Comparisons cannot mix v1 and v2 metrics. Re-scoring needs a **new artifact**;
  existing metric files are never overwritten or silently upgraded.
- New reports carry the evaluator and an explicit limitation. The browser keeps
  v1 wording for v1 events and explains v2 fragmentation as a **resumed match**.
  Unsupported/mixed evaluator tags are rejected on import.

The actual earlier onboarding report remains byte-identical, with report ID
`b8b8760c1c6616856577082bcb2e3e96cf3d3ee961ab3dc3c00f3b4dfb109f96`
and JSON SHA-256
`184445099c301764a2f87fcd7793973beb975898e3e88d632105836be6c35837`.
Its stored v1 metrics are rechecked with the retained legacy evaluator, not
recomputed under new definitions.

### Historical studies stay frozen

Their production-tree guards correctly refuse this changed checkout. They have
**not** been relaxed to accept v2 under a v1 seal. The 22 historical test files
(traffic/box-gate suites and original case-baseline tests) execute in a local,
isolated clone of **`121c755c7bc587c4484d535760c61259664b0333`**: **1,099 pass**.
No network, user-branch checkout, new held-out study or old-result rewrite.
The current test suite invokes this historical run rather than dropping it;
a separate test confirms the guards still reject changed current source.
CI already fetches full history and now installs the pinned dev-only reference.

## Reproduction and receipts

```bash
PYTHONPATH=src:. python -m experiments.mot17_metric_rescore \
  --baseline ../visiontrack-walkthrough/mot17-baseline-NvcCNo/bundle \
  --output /path/to/a/new/v2-rescore-directory
```

Actual output: `../visiontrack-walkthrough/mot17-metric-v2-IV6rTC/rescore`.
The method was written before scoring, with v2/reference source fingerprints,
unchanged tracker/input fingerprints and fixed tolerances. Every original
baseline member is verified before/after; no old file is changed. All results,
full event differences and a manifest remain outside Git. The CLI returns
**nonzero on disagreement**, not merely success because a receipt was written.

| Artifact | SHA-256 |
| --- | --- |
| Pre-score method | `e16dd768952f92e1192f465bfb5213b8252aef2401f13681363a1c49ecf4ad79` |
| Full-precision v2 score | `2660db69eb21bfc0c67823b248edfd777510e21dd1516e2d9ce0600d251eb3f8` |
| V2 failure stream | `0536a5c7fa41ba4ccf2dff655bf2cc32e134b6c3e05c502d6b07da1d14a43607` |
| All event differences | `f7fe3925274ee5607abf4d3b389e95ceb4b572c70c251729647a124ed66c22be` |
| All 45 reference checks | `4af5fa71016a15a1b6c8368cf996fd3afcf657b82c862abaa768087b1d4c7251` |
| Output manifest | `87403372f0a9158da83b4b8dddacb2c6b244db0a08ea7cc92bfb9ac5084a8e4a` |

The pinned reference remains TrackEval source
`12c8791b303e0a0b50f753af204249e622d0281a`; its source hashes are in the method.
This is same-input metric equivalence on this case and authored regression
examples, **not complete official MOT17 pipeline validation**.

Local verification: **901 tests passed, one slow test deselected**, including
the bootstrap that executes all **1,099 historical tests** in their original
checkout. All eight browser contract/workflow scripts, TypeScript, the production
app build, Ruff and strict documentation pass. These are local results, not an
inferred remote CI/deployment result.

## Done and still open

- [x] Correct HOTA/CLEAR, retain legacy semantics and add parity/edge regressions.
- [x] Re-score unchanged saved outputs and pass all 45 reference checks.
- [x] Retain changed event correspondence and verify original report compatibility.
- [x] Tighten the older end-to-end cross-check: unrounded metric comparisons,
      exact counts/float tolerance ≤1e-10, full-precision MOT export and one tracker
      pass. Its full dataset-dependent check was **not** run in this step.
- [ ] Independently verify MOT17 preprocessing on raw predictions/reference rows.
- [ ] Re-derive coverage for v2 before using the missed-object partition in a new trial.
- [ ] Complete lawful pixel/reference review; metadata/metric parity is not that review.
- [ ] Freeze one justified intervention and fresh validation, or stop for a reason.

No tracker/default/C++ change, footage collection, outreach, release or accuracy
improvement claim. C++ still awaits useful accepted tracking behavior. The next
annotation-only task needs no volunteer footage: independent preprocessing and
the corrected failure partition come before a new intervention.
