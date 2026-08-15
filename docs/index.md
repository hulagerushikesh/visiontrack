# VisionTrack

**A from-scratch multi-object tracker, used as a controlled study of *when* the field's standard tricks actually help.**

The tracker — an 8-state **Kalman filter**, an O(n³) **Hungarian** solver, and **ByteTrack** two-stage
association — is implemented from first principles on NumPy, with no ML framework in the core. On top of it
sits a reproducible experiment harness that measures, on **real MOT17** with seed variance and paired
significance tests, whether appearance and uncertainty-aware association actually improve tracking.
Several of the answers are honest negatives — which is the point.

[Live demo :material-open-in-new:](https://visiontrack.hulage.in){ .md-button .md-button--primary }
[Benchmark :material-open-in-new:](https://visiontrack.hulage.in/benchmark){ .md-button }

```bash
pip install visiontrack-mot
```

---

## Abstract

Most tracking repositories are a thin wrapper over a detector plus a vendored tracker; every reported number
is a single run on one configuration. VisionTrack inverts that: the estimation and association math *is* the
deliverable (independently tested against SciPy and `trackeval`), and it is used to run a **falsifiable
study**. We reproduce a from-scratch ByteTrack baseline on MOT17 public detections (HOTA/IDF1 verified against
`trackeval` to within `1.4e-3`), then ablate common enhancements under seed variance and Wilcoxon
significance.

## Research questions

| | Question | Answer |
|---|---|---|
| **RQ1** | Does an appearance (re-ID) association cost improve tracking? | **Yes** — deep re-ID significantly cuts ID switches on both MOT17 and DanceTrack (p<0.05), including under **real YOLOX detections**. The predicted "appearance hurts on near-identical dancers" sign-flip does **not** occur. |
| **RQ2** | Does a learned motion residual on top of constant-velocity help? | **Helps prediction only where motion is non-linear** (DanceTrack next-centre error −12.5%) — but that gain **hurts tracking** (train-on-GT / infer-on-noisy skew). An honest negative. |
| **RQ3** | Does folding *calibrated* Kalman uncertainty into the cost reduce switches under noise? | **No** — null as a soft cost; *calibrating* the filter is actively harmful under detector noise. The filter's apparent under-confidence is a robustness feature. |
| **RQ4** | Does global motion compensation help? | **Yes, iff the camera moves** — translation-only GMC recovers switches on moving-camera sequences, neutral otherwise. |

The value is the same whichever way each result falls: a controlled study that shows a trick *doesn't* help
is a contribution, not a failure.

---

## Where to go next

<div class="grid cards" markdown>

-   :material-flask: **The study**

    ---

    The four research questions, phase by phase — appearance, learned motion, uncertainty, GMC.

    [:octicons-arrow-right-24: RQ1 — Appearance](PHASE3.md)

-   :material-chart-box: **Results**

    ---

    Every leaderboard and error-taxonomy table the harness emits, checked into the repo.

    [:octicons-arrow-right-24: Benchmarks](results_benchmark_synth.md)

-   :material-api: **Public API**

    ---

    The stable surface: `Tracker`, `TrackerConfig`, presets, metrics.

    [:octicons-arrow-right-24: API reference](API.md)

-   :material-run-fast: **Reproduce**

    ---

    Run it on your own video, or reproduce every table from scratch.

    [:octicons-arrow-right-24: Run on video](VIDEO.md)

</div>
