"""Tracker zoo — a significance-tested comparison of the tracker lineage.

Runs the named presets in :mod:`visiontrack.tracking.presets` (single-stage
"SORT", DeepSORT-style, ByteTrack, ByteTrack+ReID, GIoU) over the same scenes
and seeds, then prints a mean±std leaderboard and a paired comparison of each
variant against the ByteTrack baseline (Wilcoxon p + Cohen's d). Because every
variant sees identical detections, the deltas isolate the association strategy —
single-stage vs two-stage vs +appearance — not luck.

Defaults to a synthetic occlusion-heavy scene (needs no dataset; the occluded
true objects emit low-score detections, so the two-stage recovery has something
to do, and the appearance channel is enabled so the Re-ID presets are live).

    python -m experiments.tracker_zoo                 # synthetic
    python -m experiments.tracker_zoo --dataset mot17 --detector FRCNN

The MOT17 path reuses the precomputed detection cache (appearance presets also
need the Re-ID embedding cache); see data/cache/.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(_ROOT), str(_ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from experiments.analyze import build_report, save_figure  # noqa: E402
from experiments.config import ExperimentConfig, VariantSpec  # noqa: E402
from experiments.run_matrix import run  # noqa: E402
from visiontrack.tracking.presets import PRESET_NAMES, preset_overrides  # noqa: E402

_BASELINE = "bytetrack"
_METRICS = ["MOTA", "IDF1", "HOTA", "IDSW"]

# A deliberately *hard* synthetic scene, so the trackers actually separate:
#  - high localisation noise -> motion is ambiguous (Kalman alone isn't enough),
#    which is the only regime where appearance re-ID can help (cf. the crossover
#    probe) and where ID switches occur at all;
#  - dense + occluded -> occluded true objects emit low-score detections, so the
#    two-stage recovery has something to recover;
#  - appearance channel on (distinct-ish objects) -> the Re-ID presets are live.
_ZOO_SCENE = {
    "num_objects": 12,
    "num_frames": 100,
    "loc_noise_std": 8.0,
    "occlusion_iou": 0.30,
    "false_positive_rate": 0.6,
    "appearance_dim": 32,
    "appearance_diversity": 0.7,
}


def zoo_config(dataset: str = "synthetic", detector: str = "FRCNN") -> ExperimentConfig:
    """Build the zoo sweep: one variant per preset, ByteTrack as the baseline."""
    variants = [VariantSpec(name, preset_overrides(name)) for name in PRESET_NAMES]
    if dataset == "synthetic":
        return ExperimentConfig(
            name="tracker_zoo_synth",
            dataset="synthetic",
            sequences=[1, 2, 3],
            seeds=[0, 1, 2, 3, 4],
            baseline=_BASELINE,
            metrics=_METRICS,
            scene=_ZOO_SCENE,
            variants=variants,
        )
    if dataset == "mot17":
        return ExperimentConfig(
            name="tracker_zoo_mot17",
            dataset="mot17",
            sequences=["MOT17-02", "MOT17-04", "MOT17-05", "MOT17-09",
                       "MOT17-10", "MOT17-11", "MOT17-13"],
            seeds=[0],  # MOT17 tracker is deterministic
            baseline=_BASELINE,
            metrics=_METRICS,
            detector=detector,
            variants=variants,
        )
    raise ValueError(f"unknown dataset {dataset!r}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the tracker-zoo comparison")
    parser.add_argument("--dataset", default="synthetic", choices=["synthetic", "mot17"])
    parser.add_argument("--detector", default="FRCNN", choices=["DPM", "FRCNN", "SDP"])
    parser.add_argument("--out-md", default=None, help="write the report to markdown")
    parser.add_argument("--out-fig", default=None, help="save an IDSW bar chart here")
    args = parser.parse_args(argv)

    exp = zoo_config(args.dataset, args.detector)
    print(f"tracker zoo  dataset={exp.dataset}  variants={exp.variant_names()}")
    print(f"config_hash={exp.config_hash()}\n")
    df = run(exp)
    print("\n" + build_report(df, _BASELINE, _METRICS))
    if args.out_md:
        Path(args.out_md).write_text(build_report(df, _BASELINE, _METRICS) + "\n")
        print(f"\nwrote report -> {args.out_md}")
    if args.out_fig:
        save_figure(df, _BASELINE, "IDSW", args.out_fig)
        print(f"wrote figure -> {args.out_fig}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
