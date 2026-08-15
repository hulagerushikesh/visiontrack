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
    if args.dataset == "mot17":
        return _cmd_eval_mot17(args)
    scene = _scene_from_args(args)
    cfg = TrackerConfig()
    metrics, _, _ = _run_sequence(scene, cfg)
    if args.json:
        print(json.dumps(metrics.as_dict(), indent=2))
    else:
        for k, v in metrics.as_dict().items():
            print(f"{k:>10}: {v}")
    return 0


def _mot17_readers(args):
    """Return sequence readers for the requested detector, preferring the cache.

    Uses cached ``.npz`` files when present (so the raw frames can be gone),
    otherwise reads the raw dataset live from ``--data-root``.
    """
    from pathlib import Path

    from .datasets.cache import CachedSequence
    from .datasets.splits import load_split
    from .detection.mot_loader import MOT17Sequence, discover_sequences

    split = load_split(args.split_file)
    detector = args.detector
    cache_dir = Path(args.cache_dir)

    readers = []
    if cache_dir.exists():
        for vid in split.video_ids():
            npz = cache_dir / f"{vid}-{detector}.npz"
            if npz.exists():
                readers.append(CachedSequence(npz))
    if readers:
        return split, readers, "cache"

    if args.data_root:
        seq_dirs = discover_sequences(args.data_root, "train", detector)
        readers = [MOT17Sequence(d) for d in seq_dirs]
        if readers:
            return split, readers, "raw"

    raise SystemExit(
        "No MOT17 data found. Run data/cache/precompute.py first, or pass "
        "--data-root pointing at your MOT17 download."
    )


def _cmd_eval_mot17(args) -> int:
    from .eval.mot17 import evaluate_sequences

    split, readers, source = _mot17_readers(args)
    cfg = TrackerConfig()
    print(
        f"MOT17 {args.split}  |  detector={args.detector}  |  source={source}  |  "
        f"{len(readers)} sequences  |  split='{split.name}'"
    )
    overall, reports = evaluate_sequences(readers, cfg, split, args.split, per_sequence=True)

    headline = ["MOTA", "IDF1", "HOTA", "DetA", "AssA", "IDSW", "MOTP"]
    if reports:
        print(f"\n{'sequence':<18} " + " ".join(f"{k:>7}" for k in headline))
        print("-" * (19 + 8 * len(headline)))
        for r in reports:
            print(
                f"{r.name:<18} "
                + " ".join(f"{r.metrics.get(k, 0):>7.3f}" for k in headline)
            )
        print("-" * (19 + 8 * len(headline)))
    print(f"{'OVERALL':<18} " + " ".join(f"{overall.get(k, 0):>7.3f}" for k in headline))

    if args.json:
        print("\n" + json.dumps(overall, indent=2))
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


def cmd_track(args: argparse.Namespace) -> int:
    """Track a real video file with a YOLOX detector and write an annotated video."""
    from .detection.yolox_onnx import YoloxDetector
    from .tracking.config import TrackerConfig
    from .video import track_video

    class_filter = None if args.all_classes else {0}  # default: person only
    detector = YoloxDetector(
        args.model, input_size=args.input_size,
        conf_threshold=args.conf, class_filter=class_filter,
    )
    print(f"tracking {args.input} -> {args.output}  (model={args.model})")
    summary = track_video(
        args.input, args.output, detector,
        TrackerConfig(), class_filter=class_filter,
        max_frames=args.max_frames, progress=True,
    )
    print(f"done: {summary.frames} frames, {summary.unique_tracks} unique tracks "
          f"@ {summary.fps:.1f} fps -> {summary.output_path}")
    return 0


class _WebcamQuit(Exception):
    """Raised by the preview sink when the user asks to stop (q / Esc)."""


def _build_webcam_sink(args):
    """Return ``(on_frame, close)`` for the live preview, honouring ``--no-window``.

    The window uses OpenCV, imported lazily so it never becomes a hard dependency:
    headless runs (``--no-window``) and the test suite never touch it.
    """
    if args.no_window:
        return (lambda frame, obs: None), (lambda: None)

    try:
        import cv2
    except ImportError:
        print(
            "live preview needs OpenCV: pip install opencv-python "
            "(or re-run with --no-window)",
            file=sys.stderr,
        )
        raise SystemExit(2) from None

    import numpy as np

    win = "VisionTrack — webcam (q/Esc to quit)"
    cv2.namedWindow(win, cv2.WINDOW_NORMAL)

    def on_frame(frame_rgb, obs):
        cv2.imshow(win, np.ascontiguousarray(frame_rgb[:, :, ::-1]))  # RGB->BGR
        if (cv2.waitKey(1) & 0xFF) in (27, ord("q")):
            raise _WebcamQuit

    return on_frame, cv2.destroyAllWindows


def cmd_webcam(args: argparse.Namespace) -> int:
    """Track a live camera stream in real time with a YOLOX detector + preview."""
    from .detection.yolox_onnx import YoloxDetector
    from .tracking.config import TrackerConfig
    from .video import track_webcam

    class_filter = None if args.all_classes else {0}  # default: person only
    detector = YoloxDetector(
        args.model, input_size=args.input_size,
        conf_threshold=args.conf, class_filter=class_filter,
    )
    on_frame, close = _build_webcam_sink(args)
    print(f"webcam: device={args.device}  model={args.model}"
          + ("" if args.no_window else "  (press q or Esc to quit)"))
    try:
        summary = track_webcam(
            detector, TrackerConfig(), on_frame=on_frame,
            class_filter=class_filter, device=args.device,
            mirror=args.mirror, record=args.record, record_fps=args.record_fps,
            max_frames=args.max_frames,
        )
        dest = f" -> {summary.output_path}" if args.record else ""
        print(f"done: {summary.frames} frames @ {summary.fps:.1f} fps, "
              f"{summary.unique_tracks} unique tracks{dest}")
    except _WebcamQuit:
        print("webcam stopped by user")
    finally:
        close()
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

    p_eval = sub.add_parser("eval", help="print tracking metrics (synthetic or MOT17)")
    add_scene_args(p_eval)
    p_eval.add_argument("--json", action="store_true", help="emit JSON")
    p_eval.add_argument(
        "--dataset",
        default="synthetic",
        choices=["synthetic", "mot17"],
        help="evaluate the synthetic scene (default) or real MOT17",
    )
    p_eval.add_argument(
        "--split",
        default="val",
        choices=["train", "val", "all"],
        help="MOT17 subset to evaluate (default: val)",
    )
    p_eval.add_argument(
        "--split-file", default="mot17_val_half", help="frozen split name in data/splits/"
    )
    p_eval.add_argument("--detector", default="FRCNN", choices=["DPM", "FRCNN", "SDP"])
    p_eval.add_argument(
        "--cache-dir", default="data/cache/mot17", help="MOT17 npz cache directory"
    )
    p_eval.add_argument(
        "--data-root", default=None, help="raw MOT17 root (used only if cache is absent)"
    )
    p_eval.set_defaults(func=cmd_eval)

    p_ab = sub.add_parser("ablate", help="compare tracker component variants")
    add_scene_args(p_ab)
    p_ab.set_defaults(func=cmd_ablate)

    p_track = sub.add_parser("track", help="track a real video (needs [video] extra + YOLOX)")
    p_track.add_argument("input", help="input video path (e.g. clip.mp4)")
    p_track.add_argument("output", help="annotated output video path")
    p_track.add_argument("--model", required=True, help="YOLOX .onnx model path")
    p_track.add_argument("--input-size", type=int, default=416, help="YOLOX square input side")
    p_track.add_argument("--conf", type=float, default=0.25, help="detector confidence threshold")
    p_track.add_argument("--all-classes", action="store_true",
                         help="track all COCO classes (default: person only)")
    p_track.add_argument("--max-frames", type=int, default=None, help="stop after N frames")
    p_track.set_defaults(func=cmd_track)

    p_cam = sub.add_parser("webcam", help="track a live camera in real time (needs [video])")
    p_cam.add_argument("--model", required=True, help="YOLOX .onnx model path")
    p_cam.add_argument("--device", default="<video0>", help="imageio camera spec (def: <video0>)")
    p_cam.add_argument("--input-size", type=int, default=416, help="YOLOX square input side")
    p_cam.add_argument("--conf", type=float, default=0.25, help="detector confidence threshold")
    p_cam.add_argument("--all-classes", action="store_true",
                       help="track all COCO classes (default: person only)")
    p_cam.add_argument("--mirror", action="store_true", help="flip horizontally (selfie view)")
    p_cam.add_argument("--no-window", action="store_true",
                       help="process headlessly without a preview window")
    p_cam.add_argument("--record", default=None, metavar="PATH",
                       help="also save the annotated session to this .mp4")
    p_cam.add_argument("--record-fps", type=float, default=30.0,
                       help="frame rate for the recorded mp4 (default: 30)")
    p_cam.add_argument("--max-frames", type=int, default=None, help="stop after N frames")
    p_cam.set_defaults(func=cmd_webcam)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
