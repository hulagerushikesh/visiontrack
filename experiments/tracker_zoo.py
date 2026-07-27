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
from visiontrack.eval.stats import compare  # noqa: E402
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


def run_dancetrack(cache_dir: str, embedder: str):
    """Run every preset over the DanceTrack val caches → a tidy DataFrame.

    DanceTrack has no public detections, so the caches use oracle-perturbed GT
    (the same protocol as ``experiments/dancetrack_appearance.py``). Pairing is
    over sequences (the tracker is deterministic → one 'seed'). This is OC-SORT's
    intended regime: genuinely non-linear dance motion.
    """
    from dataclasses import replace

    import pandas as pd

    from visiontrack.datasets.cache import CachedSequence
    from visiontrack.eval.mot17 import evaluate_frames, run_sequence
    from visiontrack.tracking.config import TrackerConfig

    readers = []
    for det in sorted(Path(cache_dir).glob("dancetrack*.npz")):
        if det.name.endswith(".emb.npz"):
            continue
        emb = det.with_name(det.stem + f".{embedder}.emb.npz")
        readers.append(
            CachedSequence(det, emb_path=emb) if emb.exists() else CachedSequence(det)
        )
    if not readers:
        raise FileNotFoundError(
            f"no DanceTrack caches in {cache_dir} — run precompute_dancetrack.py"
        )

    rows = []
    total = len(PRESET_NAMES) * len(readers)
    i = 0
    for name in PRESET_NAMES:
        cfg = replace(TrackerConfig(), **preset_overrides(name))
        for r in readers:
            i += 1
            frames = run_sequence(r, cfg, 1, len(r))
            m = evaluate_frames(frames)
            rows.append({
                "experiment": "tracker_zoo_dancetrack", "config_hash": "-",
                "variant": name, "dataset": "dancetrack",
                "sequence": r.name, "seed": 0,
                **{k: m.get(k) for k in _METRICS},
            })
            print(f"[{i:>3}/{total}] {name:<14} {r.name}  "
                  + " ".join(f"{k}={m.get(k):.3f}" for k in _METRICS
                            if isinstance(m.get(k), (int, float))))
    return pd.DataFrame(rows)


def _focused_pair(df, variant: str, baseline: str) -> str:
    """A paired comparison of two named variants (e.g. oc_sort vs its fair
    single-stage baseline sort), over the shared sequences."""
    lines = [f"### Focused: `{variant}` vs `{baseline}` (paired over sequences)", ""]
    lines.append("| metric | " + " | ".join(_METRICS) + " |")
    lines.append("|" + "---|" * (len(_METRICS) + 1))
    cells = []
    for m in _METRICS:
        v = df[df.variant == variant].set_index("sequence")[m].sort_index()
        b = df[df.variant == baseline].set_index("sequence")[m].sort_index()
        idx = v.index.intersection(b.index)
        c = compare(v.loc[idx].to_numpy(float), b.loc[idx].to_numpy(float), seed=0)
        star = "*" if c.p_wilcoxon < 0.05 else ""
        cells.append(f"{c.delta:+.3f} (p={c.p_wilcoxon:.2f}{star})")
    lines.append("| Δ (p) | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the tracker-zoo comparison")
    parser.add_argument("--dataset", default="synthetic",
                        choices=["synthetic", "mot17", "dancetrack"])
    parser.add_argument("--detector", default="FRCNN", choices=["DPM", "FRCNN", "SDP"])
    parser.add_argument("--embedder", default="onnx", help="dancetrack embedding tag")
    parser.add_argument("--cache-dir", default="data/cache/dancetrack")
    parser.add_argument("--out-md", default=None, help="write the report to markdown")
    parser.add_argument("--out-fig", default=None, help="save an IDSW bar chart here")
    args = parser.parse_args(argv)

    if args.dataset == "dancetrack":
        print(f"tracker zoo  dataset=dancetrack  variants={PRESET_NAMES}\n")
        df = run_dancetrack(args.cache_dir, args.embedder)
    else:
        exp = zoo_config(args.dataset, args.detector)
        print(f"tracker zoo  dataset={exp.dataset}  variants={exp.variant_names()}")
        print(f"config_hash={exp.config_hash()}\n")
        df = run(exp)

    report = build_report(df, _BASELINE, _METRICS)
    # OC-SORT is single-stage; its fair baseline is `sort`, not two-stage bytetrack.
    if "oc_sort" in df["variant"].values and "sort" in df["variant"].values:
        report += "\n\n" + _focused_pair(df, "oc_sort", "sort")
    print("\n" + report)
    if args.out_md:
        Path(args.out_md).write_text(report + "\n")
        print(f"\nwrote report -> {args.out_md}")
    if args.out_fig:
        save_figure(df, _BASELINE, "IDSW", args.out_fig)
        print(f"wrote figure -> {args.out_fig}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
