"""Run the pinned detector replay and offline localization comparison together.

The output is a descriptive research artifact. This command cannot establish
media rights, independent labels, camera separation, or a tracker improvement.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from experiments.localization_detector_replay import verify_replay
from experiments.localization_input import load_frames
from experiments.localization_outcome import compare


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_study(
    manifest_path: Path,
    model_path: Path,
    model_sha256: str,
    class_map: dict[int, str],
    *,
    input_size: int,
    conf_threshold: float = 0.25,
    iou_threshold: float = 0.45,
    max_proposals: int | None = None,
    resamples: int = 10_000,
    seed: int = 20261104,
) -> dict:
    """Verify declared detector rows, then score the same frozen manifest."""
    replay = verify_replay(
        manifest_path, model_path, model_sha256, class_map,
        input_size=input_size, conf_threshold=conf_threshold,
        iou_threshold=iou_threshold, max_proposals=max_proposals,
    )
    frames, inputs = load_frames(manifest_path)
    if inputs["manifest_sha256"] != replay["manifest_sha256"]:
        raise ValueError("manifest changed between detector replay and comparison")
    outcome = compare(frames, resamples=resamples, seed=seed, require_image_hashes=True)
    if _sha256(manifest_path) != inputs["manifest_sha256"]:
        raise ValueError("manifest changed during comparison")
    if _sha256(model_path) != model_sha256:
        raise ValueError("model changed during comparison")
    return {
        "schema": "visiontrack.localization-study/v1",
        "status": "descriptive; source admission and independent labels not verified",
        "input_receipt": inputs,
        "detector_replay": replay,
        "outcome": outcome,
        "source_admitted_by_this_command": False,
        "independent_labels_verified_by_this_command": False,
        "camera_units_verified_by_this_command": False,
    }


def _class_map(value: str) -> dict[int, str]:
    pairs = [part.split(":", 1) for part in value.split(",")]
    if any(len(pair) != 2 for pair in pairs):
        raise ValueError("expected comma-separated ID:label pairs")
    result = {int(cid): label for cid, label in pairs}
    if len(result) != len(pairs):
        raise ValueError("duplicate detector class ID")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--model-sha256", required=True)
    parser.add_argument("--class-map", required=True)
    parser.add_argument("--input-size", required=True, type=int)
    parser.add_argument("--conf-threshold", type=float, default=0.25)
    parser.add_argument("--iou-threshold", type=float, default=0.45)
    parser.add_argument("--max-proposals", type=int)
    parser.add_argument("--resamples", type=int, default=10_000)
    parser.add_argument("--seed", type=int, default=20261104)
    parser.add_argument("--output", required=True, type=Path,
                        help="new local JSON file; never overwrites an existing report")
    args = parser.parse_args()
    try:
        class_map = _class_map(args.class_map)
    except ValueError as exc:
        parser.error(f"invalid --class-map: {exc}")
    output = args.output.resolve()
    if output.exists():
        parser.error("output already exists")
    result = run_study(
        args.manifest, args.model, args.model_sha256, class_map,
        input_size=args.input_size, conf_threshold=args.conf_threshold,
        iou_threshold=args.iou_threshold, max_proposals=args.max_proposals,
        resamples=args.resamples, seed=args.seed,
    )
    payload = (json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()
    with output.open("xb") as stream:
        stream.write(payload)
    print(json.dumps({"output": str(output), "sha256": hashlib.sha256(payload).hexdigest(),
                      "status": result["status"]}, sort_keys=True))


if __name__ == "__main__":
    main()
