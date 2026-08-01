#!/usr/bin/env python3
"""Render an annotated tracking demo over an arbitrary video with YOLOX + the
from-scratch tracker — the H2.1 pipeline exercised end-to-end on real footage.

    python scripts/render_video_demo.py INPUT.mp4 OUTPUT.mp4 \
        --model models/yolox_nano.onnx

Detects each frame with a YOLOX ONNX model, tracks with the NumPy ByteTracker,
and writes an H.264 video with per-track coloured boxes + stable ids. By default
it keeps the common street classes (person + vehicles) so the result is a lively
multi-object scene; pass ``--classes`` to override, or ``--all-classes`` to keep
everything.

Nothing here is committed as imagery — the model is gitignored (weight-clean) and
the input/output videos live wherever you point them. Obtain ``yolox_nano.onnx``
per docs/VIDEO.md; a license-clean source clip (e.g. a public-domain street video)
keeps the output redistributable.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))

# COCO ids for a street scene: person, bicycle, car, motorcycle, bus, truck.
STREET_CLASSES = (0, 1, 2, 3, 5, 7)
COCO_NAMES = {0: "person", 1: "bicycle", 2: "car", 3: "motorcycle",
              5: "bus", 7: "truck"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source")
    ap.add_argument("output")
    ap.add_argument("--model", default="models/yolox_nano.onnx")
    ap.add_argument("--input-size", type=int, default=416,
                    help="416 for nano/tiny, 640 for s/m/l")
    ap.add_argument("--conf", type=float, default=0.25,
                    help="detector confidence gate")
    ap.add_argument("--new-track-thresh", type=float, default=0.4,
                    help="min score to spawn a track (YOLOX-nano scores run low, "
                         "so this is below the MOT-detector default of 0.6)")
    ap.add_argument("--high-score-thresh", type=float, default=0.4,
                    help="first-stage association score band")
    ap.add_argument("--n-init", type=int, default=2,
                    help="hits before a track is confirmed/drawn")
    ap.add_argument("--max-frames", type=int, default=None)
    ap.add_argument("--classes", type=int, nargs="+", default=None,
                    help="COCO class ids to keep (default: person + vehicles)")
    ap.add_argument("--all-classes", action="store_true")
    args = ap.parse_args(argv)

    from visiontrack.detection.yolox_onnx import YoloxDetector
    from visiontrack.tracking.config import TrackerConfig
    from visiontrack.video import track_video

    # Defaults are tuned for MOT-style detectors; a COCO YOLOX-nano scores lower,
    # so relax the spawn/confirm gates a touch for sensible real-video coverage.
    config = TrackerConfig(new_track_thresh=args.new_track_thresh,
                           high_score_thresh=args.high_score_thresh,
                           n_init=args.n_init)

    if args.all_classes:
        class_filter = None
    elif args.classes is not None:
        class_filter = set(args.classes)
    else:
        class_filter = set(STREET_CLASSES)

    det = YoloxDetector(args.model, input_size=args.input_size,
                        conf_threshold=args.conf)
    summary = track_video(args.source, args.output, det, config,
                          class_filter=class_filter, max_frames=args.max_frames,
                          progress=True)
    kept = "all" if class_filter is None else ", ".join(
        COCO_NAMES.get(c, str(c)) for c in sorted(class_filter))
    print(f"\nclasses kept : {kept}")
    print(f"frames       : {summary.frames}")
    print(f"unique tracks: {summary.unique_tracks}")
    print(f"source fps   : {summary.fps:.1f}")
    print(f"wrote        : {summary.output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
