# Metric cross-check: discrepancies found, new comparisons on hold

Checkpoint: **2026-10-24**. **Not a pass.** The baseline is repeatable internally,
but several metrics differ from the installed TrackEval reference. Evaluator
alignment is now the first technical priority before a new accuracy comparison.

**Subsequent 2026-10-24 resolution:** [Evaluator v2](EVALUATOR_V2.md) corrects the
algorithms and passes all 45 reference checks on unchanged saved scored inputs.
This page preserves the original failed check and its receipts; do not rewrite
it as a pass. Independent preprocessing, v2 coverage and visual review remain open.

## Actual check and results

After the [first-switch trace](REAL_DATA_TRACE.md) showed correspondence-history
ambiguity, TrackEval computed its **own IoU, assignments and metrics** on all
**1,050 saved scored pairs**: 47,557 reference boxes, 25,781 preprocessed public
boxes, 83 reference IDs. Sparse IDs were consistently densely relabelled;
coordinates and frame order were unchanged. **No tracker ran.**

This checks an independent **metric implementation**, not independent MOT17
preprocessing, pixel/label correctness, an official submission or an improvement.
Both implementations consume our already-preprocessed pairs. No pixels, tuning,
downloads, installations or changes to the sealed baseline.

| Quantity | Sealed baseline implementation | Installed TrackEval |
| --- | --- | --- |
| TP / FN / FP | 25,732 / 21,825 / 49 | 25,732 / 21,825 / 49 |
| ID switches | **43** | **44** |
| Fragmentations | **148** | **108** |
| MOTA | 0.5391425026809933 | 0.5391214752822928 |
| MOTP | 0.8938097995896855 | 0.8940729768152884 |
| IDF1 | **0.6132155226485587** | **0.6132155226485587** |
| IDTP / IDFP / IDFN | 22,486 / 3,295 / 25,071 | 22,486 / 3,295 / 25,071 |
| HOTA | **0.5255496552414854** | **0.5237264889973016** |
| DetA | 0.48535697456421806 | 0.48207977771327476 |
| AssA | 0.5703012879198524 | 0.5702416630515427 |
| MT / PT / ML | 16 / 40 / 27 | 16 / 40 / 27 |

Precision/recall, identity precision/recall and frame counts also agree. All seven
reported HOTA component means and all **19 per-alpha values** differ. Mean HOTA
differs by **0.00182317**, or **0.1823 percentage points**. Small is not equivalent.

The pre-execution method fixed **exact integer equality** and **absolute float
tolerance 1e-10**. Of 45 checks, 15 agree and 30 disagree. No tolerance was relaxed.
Full reference outputs and signed differences are retained. Completing the
diagnostic is not a successful equivalence verdict.

The diagnostic CLI's zero exit status means it finished writing its receipt,
**not** that equivalence passed. The result's `all_reported_checks_agree` is
**false**; an automated approval gate must consume that verdict, not infer a pass
from process completion. Tighten this interface during the evaluator correction.

## Source differences and three authored counterexamples

These establish non-equivalence, not each mechanism's quantitative contribution
to the real-data deltas.

1. **HOTA is not merely a solver tie.** Ours accumulates raw IoU into global
   potential, then assigns separately per alpha using alignment × validity mask.
   The reference normalizes similarities by row/column competition, computes
   alignment, assigns with **alignment × local similarity**, then filters those
   same assigned pairs per alpha. Epsilon conventions also differ.

   A one-frame example uses reference x intervals `[0,10], [6.6,16.6]`, tracker
   intervals `[3.2,13.2], [-3.4,6.6]`, all y intervals `[0,10]`. At alpha 0.5 ours
   counts one TP, the reference zero: its uniquely preferred off-diagonal pairs
   both have IoU just below 0.5. **No Hungarian tie.** Maximizing TP is not a
   substitute for the intended HOTA definition. Do not reuse the old cross-check
   script's tie-breaking explanation/permissive tolerance to dismiss this.

2. **CLEAR preserves different history.** Ours greedily preserves any last stored
   pairing while IoU passes, even after a miss. TrackEval separates long-term
   history for switch counts from previous-timestep correspondence for assignment,
   solving a thresholded weighted assignment. An authored three-frame case lets
   one ID serve two references at different times: ours gives three TP/no switch,
   the reference four TP/one switch. This is not rounding. It does not locate the
   extra real-data switch; that requires a retained per-frame comparison.

3. **Fragmentation means different events.** Ours counts matched → missed, even
   with no later recovery; the reference counts matched segments beyond the first.
   Two matches followed by a terminal miss give **1 versus 0**. Historical 148
   interruptions must not silently be relabelled as 108 reference fragmentations.

The tests intentionally characterize these differences while the baseline stays
sealed; passing them does not approve the old algorithms. Replace inequality
expectations with reference-parity regressions during the reviewed correction.
Do not preserve a known defect as a permanent contract.

## Next work, in order

- [x] Preserve the baseline, actual trace and historical protocols/results.
- [x] Retain the independent check and the three minimal counterexamples.
- [x] Put new accuracy comparisons **on hold**, despite a green regression suite.
- [ ] Align HOTA with the pinned reference: crowded/ambiguous, per-alpha,
      empty-input and deterministic-tie tests; revisit the old cross-check script.
- [ ] Align CLEAR matching/fragmentation, explicitly deciding compatibility for
      Lab failure records and old reports. Retain old evaluator revisions/results.
- [ ] Re-score **unchanged saved outputs** with a separate evaluator receipt;
      compare all components and changed per-frame correspondences. Do not rerun
      or tune the tracker to conceal a measurement change.
- [ ] Validate MOT17 preprocessing independently as a separate task.
- [ ] Complete lawful pixel/reference review from the trace brief, then freeze
      one justified intervention and fresh validation, or record a reasoned stop.

No production metric, tracker, report schema, default or C++ file changed here.
Evaluator correction does not require volunteer footage. C++ remains at the
accepted tracker contract; a changed score alone does not justify a port.
No new outreach or public claim is authorized.

The trace still establishes actual lifecycle: 31 born at 52/public at 54, 19
continuously updated. Its event selection and the miss partition are tied to our
**historical scorer**, not independently verified TrackEval correspondences.
Equal FN totals do not imply identical missed reference objects per frame.

## Reproduction and evidence

```bash
PYTHONPATH=src:. python -m experiments.mot17_metric_crosscheck \
  --baseline ../visiontrack-walkthrough/mot17-baseline-NvcCNo/bundle \
  --output /path/to/a/new/metric-check-directory
```

Actual output: `../visiontrack-walkthrough/mot17-metric-crosscheck-ixhjC8/check`.
Method precedes evaluation; this is a post-baseline check, not a tracker trial.
All baseline members are verified before/after. All **45 installed TrackEval
Python files plus this harness** are fingerprinted and checked. Results, method
and manifest remain outside Git; existing output is refused.

Installed reference: **TrackEval 1.0.dev1**, recorded Git source
[`12c8791b303e0a0b50f753af204249e622d0281a`](https://github.com/JonathonLuiten/TrackEval/tree/12c8791b303e0a0b50f753af204249e622d0281a),
Python 3.12.9, NumPy 2.3.1, SciPy 1.16.2. The isolated process restores NumPy's
removed `float`/`int` aliases as existing reference tests do, without source edits.
Import warns about an absent optional BURST `pycocotools` dependency; CLEAR,
Identity and HOTA complete. This is a pinned installed reference, not a claim
to have checked the latest upstream release or all official dataset rules.

| Artifact | SHA-256 |
| --- | --- |
| Harness | `0a2f3ef02ecc56c50719752de941dc0836dfe67468cfaef653cb6a52640a3a02` |
| Harness tests | `170ba94c563945d9b7838d0d9e042ae52d0a5b31b485031db5e6cb9b57afcb6a` |
| Three examples | `0ce6d6dc6fa9afdf515fefe18341172920721592826f588d6f047c63d0e24985` |
| Method | `4d5d9513f0d8a827386d7844b23c134af180fd79eceec56b346b01a97f9c9892` |
| Complete results | `feaed90155bb823b9f4e4d02327ef43b27a7519db80901a7e7b4ba28fadcb414` |
| Manifest | `106a63d932dce8dd59391692805c1790c8f31aa72eeee9379bb30caf8e55b3d8` |

Eight harness tests verify independent geometry/no tracker execution, dense IDs,
empty frames, fixed tolerances, retained disagreement and malformed inputs.
Together with the three characterization examples, they improve diagnostics;
they do not convert the failing real-data check into approval.

Session verification: **1,961 non-slow tests pass, one slow test deselected**;
Ruff, strict documentation build, original artifact fingerprints and unchanged
frozen protocol files pass. No CI run, push or deployment is inferred from these
local checks.
