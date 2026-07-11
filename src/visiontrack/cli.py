"""Command-line interface for VisionTrack.

Subcommands
-----------
``demo``
    Simulate a scene, run the tracker, print MOT metrics and (optionally)
    write a trajectory plot / animated GIF.
``eval``
    Run the tracker over a synthetic sequence and print CLEAR-MOT metrics as a
    table or JSON — useful as a regression gate.
``ablate``
    Compare tracker variants (e.g. with/without the ByteTrack recovery stage
    and Mahalanobis gating) to quantify each component's contribution.

Everything runs on the built-in synthetic generator, so ``visiontrack demo``
works out of the box with no model or video downloads.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace

from .detection.synthetic import SyntheticScene, SyntheticSceneConfig
from .eval.mot import MotAccumulator
from .tracking.config import TrackerConfig
from .tracking.tracker import ByteTracker


def _run_sequence(
    scene: SyntheticScene, cfg: TrackerConfig, collect_history: bool = False
):
    """Run the tracker across a scene; return (metrics, per-frame renders)."""
    tracker = ByteTracker(cfg)
    acc = MotAccumulator(iou_threshold=0.5)
    renders = []
    trajectories: dict[int, list] = {}

    for frame in scene:
        observations = tracker.update(frame.detections)
        hyp_ids = [o.track_id for o in observations]
        hyp_boxes = [o.xyxy for o in observations]
        acc.update(frame.gt_ids, frame.gt_boxes, hyp_ids, hyp_boxes)

        if collect_history:
            from .viz.draw import FrameRender

            renders.append(
                FrameRender(
                    index=frame.index,
                    track_ids=hyp_ids,
                    track_boxes=hyp_boxes if hyp_boxes else [],
                    gt_boxes=frame.gt_boxes,
                )
            )
            for o in observations:
                trajectories.setdefault(o.track_id, []).append(o.xyxy)

    return acc.result(), renders, trajectories


def _scene_from_args(args) -> SyntheticScene:
    return SyntheticScene(
        SyntheticSceneConfig(
            num_objects=args.objects,
            num_frames=args.frames,
            miss_rate=args.miss_rate,
            false_positive_rate=args.fp_rate,
            seed=args.seed,
        )
    )


def cmd_demo(args) -> int:
    scene = _scene_from_args(args)
    cfg = TrackerConfig()
    metrics, renders, trajectories = _run_sequence(scene, cfg, collect_history=True)

    print(f"Simulated {scene.cfg.num_objects} objects over {scene.cfg.num_frames} frames")
    print(metrics)

    if args.plot:
        from .viz.draw import save_trajectory_plot

        save_trajectory_plot(
            args.plot, trajectories, scene.cfg.width, scene.cfg.height
        )
        print(f"Wrote trajectory plot -> {args.plot}")

    if args.gif:
        from .viz.draw import animate_scene

        animate_scene(
            args.gif, renders, scene.cfg.width, scene.cfg.height, fps=args.fps
        )
        print(f"Wrote animation -> {args.gif}")
    return 0


def cmd_eval(args) -> int:
    scene = _scene_from_args(args)
    cfg = TrackerConfig()
    metrics, _, _ = _run_sequence(scene, cfg)
    if args.json:
        print(json.dumps(metrics.as_dict(), indent=2))
    else:
        for k, v in metrics.as_dict().items():
            print(f"{k:>10}: {v}")
    return 0


def _ablate_scene(args) -> SyntheticSceneConfig:
    """A deliberately crowded, occlusion-heavy scene that stresses the
    tracker so component contributions become visible."""
    return SyntheticSceneConfig(
        width=900,
        height=600,
        num_objects=max(args.objects, 16),
        num_frames=max(args.frames, 150),
        occlusion_iou=0.3,
        false_positive_rate=1.0,
        seed=args.seed,
    )


def cmd_ablate(args) -> int:
    base = TrackerConfig()
    variants = {
        "full (bytetrack + gating)": base,
        "no low-score recovery": replace(base, low_score_thresh=base.high_score_thresh),
        "no Mahalanobis gating": replace(base, use_mahalanobis_gating=False),
        "class-agnostic": replace(base, class_aware=False),
    }

    scene_cfg = _ablate_scene(args)
    print(
        f"stress scene: {scene_cfg.num_objects} objects, {scene_cfg.num_frames} "
        f"frames, heavy occlusion + {scene_cfg.false_positive_rate} FP/frame\n"
    )
    print(f"{'variant':<28} {'MOTA':>7} {'MOTP':>7} {'IDSW':>6} {'FP':>6} {'FN':>6}")
    print("-" * 64)
    for name, cfg in variants.items():
        # Fresh scene per variant, identical seed -> a fair comparison.
        scene = SyntheticScene(scene_cfg)
        metrics, _, _ = _run_sequence(scene, cfg)
        d = metrics.as_dict()
        print(
            f"{name:<28} {d['MOTA']:>7.3f} {d['MOTP']:>7.3f} "
            f"{d['IDSW']:>6} {d['FP']:>6} {d['FN']:>6}"
        )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="visiontrack", description="Online multi-object tracking demo & evaluation"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    def add_scene_args(p: argparse.ArgumentParser) -> None:
        p.add_argument("--objects", type=int, default=6, help="number of GT objects")
        p.add_argument("--frames", type=int, default=120, help="sequence length")
        p.add_argument("--miss-rate", type=float, default=0.08, help="detector miss rate")
        p.add_argument("--fp-rate", type=float, default=0.3, help="false positives/frame")
        p.add_argument("--seed", type=int, default=0, help="RNG seed")

    p_demo = sub.add_parser("demo", help="run a full demo with optional outputs")
    add_scene_args(p_demo)
    p_demo.add_argument("--plot", type=str, default=None, help="trajectory PNG path")
    p_demo.add_argument("--gif", type=str, default=None, help="animation GIF path")
    p_demo.add_argument("--fps", type=int, default=15)
    p_demo.set_defaults(func=cmd_demo)

    p_eval = sub.add_parser("eval", help="print CLEAR-MOT metrics")
    add_scene_args(p_eval)
    p_eval.add_argument("--json", action="store_true", help="emit JSON")
    p_eval.set_defaults(func=cmd_eval)

    p_ab = sub.add_parser("ablate", help="compare tracker component variants")
    add_scene_args(p_ab)
    p_ab.set_defaults(func=cmd_ablate)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
