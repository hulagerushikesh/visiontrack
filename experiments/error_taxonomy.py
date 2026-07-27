"""ID-switch error taxonomy — *why* does the tracker swap identities?

An IDSW count says how often the tracker fails; it doesn't say *when*. This tool
classifies each identity switch by the local scene condition at the frame it
happens — **occlusion**, **crowding**, and **fast motion** — and compares the
rate of each condition among switches against its base rate across all matched
ground-truth observations. The ratio (a "lift") tells you which conditions
switches are *over-represented* in: that is the failure mode to attack next.

It reuses the exact CLEAR-MOT switch detection (via an on_switch hook on the
accumulator), so the classified switches are precisely the ones counted in IDSW.

    python -m experiments.error_taxonomy --dataset dancetrack
    python -m experiments.error_taxonomy --dataset synthetic --preset bytetrack

Context features (per ground-truth box at a frame):
* occlusion  = max IoU with any *other* GT box (boxes overlapping => occluding).
* crowding   = number of other GT boxes overlapping it (IoU > 0.05).
* motion     = centre displacement from the previous frame, in box-heights.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(_ROOT), str(_ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import numpy as np  # noqa: E402

from visiontrack.core.geometry import iou_matrix  # noqa: E402
from visiontrack.eval.mot import MotAccumulator  # noqa: E402
from visiontrack.tracking.presets import preset  # noqa: E402
from visiontrack.tracking.tracker import ByteTracker  # noqa: E402

# Condition thresholds (documented, not tuned): a switch/observation "counts" as
# occluded / crowded / fast when its feature exceeds these.
_OCC_THRESH = 0.10   # max IoU with another GT
_CROWD_THRESH = 2    # >= this many other GT overlapping
_FAST_THRESH = 0.15  # centre move per frame, in box-heights


def _centres(boxes: np.ndarray) -> np.ndarray:
    return np.stack([(boxes[:, 0] + boxes[:, 2]) / 2.0,
                     (boxes[:, 1] + boxes[:, 3]) / 2.0], axis=1)


def context_features(gi: int, gt_ids, gt_boxes, prev_centres: dict) -> dict:
    """Occlusion / crowding / motion for GT row ``gi`` at one frame."""
    gt_boxes = np.asarray(gt_boxes, dtype=np.float64).reshape(-1, 4)
    n = len(gt_boxes)
    box = gt_boxes[gi]
    if n > 1:
        ious = iou_matrix(box[None], gt_boxes)[0]
        ious[gi] = 0.0
        occlusion = float(ious.max())
        crowding = int((ious > 0.05).sum())
    else:
        occlusion, crowding = 0.0, 0

    height = max(box[3] - box[1], 1e-6)
    gid = int(gt_ids[gi])
    if gid in prev_centres:
        c_now = np.array([(box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0])
        motion = float(np.linalg.norm(c_now - prev_centres[gid]) / height)
    else:
        motion = 0.0
    return {"occlusion": occlusion, "crowding": crowding, "motion": motion}


def _run_frames(frames, preset_name: str):
    """Feed pre-computed (gt_ids, gt_boxes, tr_ids, tr_boxes) frames through the
    accumulator, collecting switch contexts and the background population."""
    switches: list[dict] = []
    background: list[dict] = []
    prev_centres: dict[int, np.ndarray] = {}

    def on_switch(frame, gt_id, prev_h, new_h, gi, gt_ids, gt_boxes):
        switches.append(context_features(gi, gt_ids, gt_boxes, prev_centres))

    acc = MotAccumulator(on_switch=on_switch)
    for gt_ids, gt_boxes, tr_ids, tr_boxes in frames:
        gt_ids = np.asarray(gt_ids).reshape(-1)
        gt_boxes = np.asarray(gt_boxes, dtype=np.float64).reshape(-1, 4)
        # Background: features for every GT this frame (the base population).
        for gi in range(len(gt_ids)):
            background.append(context_features(gi, gt_ids, gt_boxes, prev_centres))
        acc.update(gt_ids, gt_boxes, tr_ids, tr_boxes)
        # Advance previous centres for the motion feature.
        if len(gt_boxes):
            cs = _centres(gt_boxes)
            for k, gid in enumerate(gt_ids):
                prev_centres[int(gid)] = cs[k]
    return switches, background, acc.result().as_dict()["IDSW"]


def _rate(rows: list[dict], key: str, thresh) -> float:
    if not rows:
        return 0.0
    if key == "crowding":
        return float(np.mean([r[key] >= thresh for r in rows]))
    return float(np.mean([r[key] > thresh for r in rows]))


def taxonomy_report(switches, background, idsw: int) -> str:
    conds = [("occlusion", _OCC_THRESH), ("crowding", _CROWD_THRESH),
             ("motion", _FAST_THRESH)]
    lines = ["# ID-switch error taxonomy", ""]
    lines.append(f"- identity switches classified: {len(switches)} (IDSW={int(idsw)})")
    lines.append(f"- background GT observations: {len(background)}")
    lines.append("")
    lines.append("| condition | % of switches | % of all GT (base) | lift |")
    lines.append("|---|---|---|---|")
    for key, thr in conds:
        p_sw = _rate(switches, key, thr)
        p_bg = _rate(background, key, thr)
        lift = (p_sw / p_bg) if p_bg > 0 else float("nan")
        lines.append(f"| {key} | {p_sw:.1%} | {p_bg:.1%} | {lift:.2f}× |")
    lines.append("")
    lines.append("Lift = P(condition | switch) / P(condition | any GT). "
                 ">1 means switches are over-represented in that condition — "
                 "the failure mode to attack.")
    return "\n".join(lines)


def _synthetic_frames(preset_name: str, sequences, seeds, scene):
    from visiontrack.detection.synthetic import SyntheticScene, SyntheticSceneConfig
    frames = []
    for seq in sequences:
        for seed in seeds:
            scene = SyntheticScene(SyntheticSceneConfig(seed=seq * 1000 + seed, **scene))
            tracker = ByteTracker(preset(preset_name))
            for f in scene:
                obs = tracker.update(f.detections)
                if obs:
                    ti = np.array([o.track_id for o in obs], dtype=np.int64)
                    tb = np.stack([o.xyxy for o in obs])
                else:
                    ti, tb = np.empty(0, np.int64), np.empty((0, 4))
                frames.append((f.gt_ids, f.gt_boxes, ti, tb))
    return frames


def _dancetrack_frames(preset_name: str, cache_dir: str, embedder: str):
    from visiontrack.datasets.cache import CachedSequence
    from visiontrack.eval.mot17 import run_sequence
    frames = []
    for det in sorted(Path(cache_dir).glob("dancetrack*.npz")):
        if det.name.endswith(".emb.npz"):
            continue
        emb = det.with_name(det.stem + f".{embedder}.emb.npz")
        reader = CachedSequence(det, emb_path=emb) if emb.exists() else CachedSequence(det)
        cfg = preset(preset_name)
        seq_frames = run_sequence(reader, cfg, 1, len(reader))
        frames.extend(seq_frames)
    return frames


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ID-switch error taxonomy")
    parser.add_argument("--dataset", default="synthetic", choices=["synthetic", "dancetrack"])
    parser.add_argument("--preset", default="bytetrack")
    parser.add_argument("--cache-dir", default="data/cache/dancetrack")
    parser.add_argument("--embedder", default="onnx")
    parser.add_argument("--out-md", default=None)
    args = parser.parse_args(argv)

    print(f"error taxonomy | dataset={args.dataset} | preset={args.preset}\n")
    if args.dataset == "synthetic":
        frames = _synthetic_frames(
            args.preset, [1, 2, 3, 4], [0, 1, 2],
            {"num_objects": 12, "num_frames": 100, "loc_noise_std": 6.0,
             "occlusion_iou": 0.30, "false_positive_rate": 0.5},
        )
    else:
        frames = _dancetrack_frames(args.preset, args.cache_dir, args.embedder)

    switches, background, idsw = _run_frames(frames, args.preset)
    report = taxonomy_report(switches, background, idsw)
    print(report)
    if args.out_md:
        Path(args.out_md).write_text(report + "\n")
        print(f"\nwrote report -> {args.out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
