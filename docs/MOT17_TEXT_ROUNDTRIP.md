# MOT17 file-to-score verification

Checkpoint: **2026-10-25 — passed on the existing saved baseline.**

## What this finishes

Previously, our independent checks supplied arrays directly to TrackEval.
Those checks did not test its real text-file loader. We have now checked the
chain **saved boxes → standard MOT result file → TrackEval's real loader →
its preprocessing → its sequence metrics**, using the original official GT
file bytes. No tracker ran and no settings changed.

Think of this as checking that the measuring instrument still reads correctly
when we use actual files, not just when we hand it numbers in memory. It is
**not** evidence that the tracker became more accurate.

| Check on MOT17-04-FRCNN | Result |
| --- | --- |
| Complete saved sequence | All 1,050 frames, including frames without outputs |
| Raw public predictions loaded | All 27,842, exact original IDs and derived XYWH coordinates |
| Loaded GT | Exact source-verified boxes, IDs, classes and consider flags |
| Predictions after reference preprocessing | Same 25,781, exact frame-by-frame correspondence |
| Scoring reference boxes | Same 47,557 |
| Corrected metric comparisons | All 45 pass; integer counts exact, floats within the fixed `1e-10` |
| Largest absolute metric difference | `3.552713678800501e-15` (MOTP) |

Corrected values remain **FN 21,825; FP 49; ID switches 44; fragmentations 108;
HOTA 0.5237264889973016; IDF1 0.6132155226485587**. These are the existing
[evaluator-v2](EVALUATOR_V2.md) results, not a new performance improvement.
Historical v1 outputs and receipts remain unchanged.

## Exact boundary

- The actual reference `MotChallenge2DBox.get_raw_seq_data` reads real GT and
  prediction files. Its own IoUs, preprocessing and CLEAR/Identity/HOTA sequence
  implementations run afterwards. No replacement loader or supplied similarity
  matrix is used. Multi-sequence aggregation, the outer Evaluator CLI and official
  benchmark submission are **not** tested by this check.
- The official GT is copied byte-for-byte from the already pinned annotations.
  The cache/source correspondence and every raw frame's GT are verified first.
- Saved float64 XYXY predictions are converted to XYWH and written with 17
  significant digits. The loaded XYWH values must match exactly. We do not
  round boxes for presentation or replace reference geometry with our own IoUs.
- The saved output does not contain confidence. Column seven is therefore an
  explicit constant **1 placeholder**, not a reconstructed confidence. The
  remaining three standard MOT fields are `-1` placeholders. No extra confidence
  filter is introduced; exact raw and processed counts/correspondence are checked.
- Processed IDs are checked against the expected dense relabelling of the saved
  scoring IDs, along with exact selected XYWH boxes. Matching counts alone is not
  sufficient. All 19 HOTA thresholds are among the 45 metric checks.
- TrackEval is the same pinned dev-only revision
  `12c8791b303e0a0b50f753af204249e622d0281a`. Its installed Git origin is checked,
  Python sources are hashed before/after, and Python/NumPy/SciPy versions are
  recorded. This does not cryptographically verify dependency binaries.

There is no new download, image access, model inference, tracker replay, label
edit, tolerance relaxation, historical rewrite or C++ port. Repeatedly checking
this development sequence does not make it untouched validation. Correct source
file correspondence is still not independent physical-label verification.

## Reproduce privately

Offline method preview, without reading input files or creating output:

```bash
PYTHONPATH=src:. python -m experiments.mot17_text_roundtrip
```

With the already admitted inputs and an existing private parent directory:

```bash
PYTHONPATH=src:. python -m experiments.mot17_text_roundtrip \
  --baseline ../visiontrack-walkthrough/mot17-baseline-NvcCNo/bundle \
  --rescore ../visiontrack-walkthrough/mot17-metric-v2-IV6rTC/rescore \
  --cache data/cache/mot17/MOT17-04-FRCNN.npz \
  --labels ../visiontrack-walkthrough/mot17-label-audit-NQQO7d/MOT17Labels.zip \
  --output /absolute/private/new-text-check --write
```

The output must be new, outside the repository and outside either sealed input
packet. The method is written before reference loading/evaluation. The output
retains the exact GT, sequence-info and prediction files, comparison and hashes.
Exceptions retain a failure receipt without a completion manifest; metric
disagreement is retained and exits nonzero. No original input is overwritten.
The isolated optional BURST/`pycocotools` import warning is unrelated to MOT17.

The finalized packet is outside Git at
`../visiontrack-walkthrough/mot17-text-roundtrip-8d10Se/final-check/`.
The earlier `check/` pass is also retained: output-location guards and explicit
policy metadata were then tightened and the same fixed check was rerun. Both
passes agree; this was harness hardening, not selection among tracker trials.
No GT, images or generated result packet is included in the commit.

| Final receipt | SHA-256 |
| --- | --- |
| Pre-execution method | `38ac89cdf81bf9d751a2c90c571f31c56505d7176f3b20afc36e33d91ec425cd` |
| All comparisons | `faaaf4366cb3c76eb458089c99c3b699d83cfe5407d1a80cc6dc373bb8990a18` |
| Complete packet manifest | `2704b82673e5a996f228a9d336ff1431cf501d99f439f411bf1a3e566d082718` |

## What remains

The measurement chain is now checked through real file loading. The next
research gate is **a separate person's review of the already prepared 36–57
scene/reference window**, preserving uncertainty and disagreement. See the
[private review handoff](MOT17_VISUAL_REVIEW.md#local-reviewer-handoff-no-installation-or-recording).
No new volunteer recording or installation is needed for that step.

After review, justify one prospectively fixed comparison and fresh validation,
or retain a reasoned non-intervention. We have not yet accepted a tracker fix,
finished the independent visual case study or validated practitioner usefulness.
C++ remains at its accepted NumPy parity contract.

The 23 new authored tests exercise actual small-file loading, empty frames,
float serialization, ignore/zero-mark rules, all metric comparisons, altered
IDs/geometry/policy/confidence, malformed export, preview/exit behavior and
output-location guards. They are regression tests, not scene annotations or a
real-world accuracy study.

Local validation at this checkpoint: **1,045 tests pass, one slow test
deselected**. This includes the isolated regression bootstrap that executes
1,099 historical tests at their frozen revision, not 1,099 additional tests
against today's source. All eight web contract/workflow scripts, the offline
staged-review check, TypeScript, production app build, Ruff and strict docs pass.
Remote CI/deployment are separate post-push checks. None of these completes
independent human review or actual-browser visual QA of the private page.
