"""Development-only replay adapter for the frozen traffic mechanism protocol.

No tuning, held-out tracking, result files or changes to the production tracker.
The returned record is a partial harness check, not the final study report.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
from dataclasses import asdict, fields
from numbers import Integral, Real
from pathlib import Path

import numpy as np

from experiments.traffic_crossing import AnchorSample, extract_crossings, score_crossings
from experiments.traffic_protocol import ROOT, load_frozen_protocol
from experiments.traffic_scene import (
    GroundProjection,
    _digest_arrays,
    generate_scene,
    validate_boxes,
)


def _json_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _git(root: Path, *args: str) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        timeout=10,
        check=True,
    )
    if len(result.stdout) > 1024 * 1024:
        raise ValueError("Git provenance exceeds limit")
    return result.stdout


def _verify_tree(root: Path, revision: str) -> dict:
    """Compare every package source byte with the locally available pinned tree.

    Git blob IDs detect checkout drift (including staged changes); SHA-256
    records the accepted bytes. No fetch, checkout, index edit or trust in a
    mutable branch/default configuration. Not a malicious-runtime sandbox.
    """
    listing = _git(root, "ls-tree", "-r", "-z", revision, "--", "src/visiontrack")
    entries = listing.rstrip(b"\0").split(b"\0")
    if not listing or len(entries) > 4096:
        raise ValueError("missing or oversized baseline source tree")
    digests = {}
    for entry in entries:
        metadata, name = entry.decode("utf-8").split("\t", 1)
        mode, kind, expected = metadata.split()
        relative = Path(name)
        if (
            mode not in {"100644", "100755"}
            or kind != "blob"
            or len(expected) != 40
            or relative.parts[:2] != ("src", "visiontrack")
            or ".." in relative.parts
        ):
            raise ValueError("unexpected baseline source entry")
        path = root / relative
        if path.is_symlink():
            raise ValueError("baseline source must not be a symlink")
        with path.open("rb") as stream:
            data = stream.read(1024 * 1024 + 1)
        if len(data) > 1024 * 1024:
            raise ValueError("baseline source file exceeds limit")
        blob = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
        if blob != expected:
            raise ValueError(f"baseline source drift: {name}")
        digests[name] = hashlib.sha256(data).hexdigest()
    actual_python = {
        str(path.relative_to(root)) for path in (root / "src/visiontrack").rglob("*.py")
    }
    expected_python = {name for name in digests if name.endswith(".py")}
    if actual_python != expected_python:
        raise ValueError("unexpected or missing package Python source")
    return {
        "revision": revision,
        "files": digests,
        "sha256": hashlib.sha256(_json_bytes(digests)).hexdigest(),
    }


def _check_import_origins() -> None:
    """Reject an installed wheel/other checkout shadowing this source tree."""
    package = (ROOT / "src/visiontrack").resolve()
    for name, module in tuple(sys.modules.items()):
        if name == "visiontrack" or name.startswith("visiontrack."):
            origin = getattr(module, "__file__", None)
            if origin is None or not Path(origin).resolve().is_relative_to(package):
                raise ValueError("VisionTrack import is not from the verified checkout")


def _replay(tracker, scene, spec: dict) -> list[dict]:
    from visiontrack.detection.base import Detection

    if tracker.frame_index != -1:
        raise ValueError("tracker must start at frame -1")
    grid = spec["frame_grid"]
    rows = []
    for frame, boxes in enumerate(scene.observed_boxes):
        # Truth IDs/contacts never enter Detection; writable copies isolate inputs.
        detections = [
            Detection(
                xyxy=box.copy(),
                score=spec["ideal_box"]["score"],
                class_id=spec["ideal_box"]["class_id"],
                feature=None,
            )
            for box in boxes
        ]
        observations = tracker.update(detections)
        if tracker.frame_index != frame:
            raise ValueError("tracker did not advance exactly one frame")
        seen = set()
        for observation in observations:
            identity = observation.track_id
            if (
                isinstance(identity, bool)
                or not isinstance(identity, Integral)
                or identity < 1
                or identity in seen
            ):
                raise ValueError("invalid or duplicate public track ID")
            seen.add(identity)
            if (
                isinstance(observation.frame, bool)
                or not isinstance(observation.frame, Integral)
                or observation.frame != frame
            ):
                raise ValueError("public observation frame mismatch")
            box = validate_boxes(observation.xyxy, width=grid["width"], height=grid["height"])
            if box.shape != (4,):
                raise ValueError("public observation must contain one box")
            if (
                isinstance(observation.score, bool)
                or not isinstance(observation.score, Real)
                or not np.isfinite(observation.score)
                or not 0 <= observation.score <= 1
                or isinstance(observation.class_id, bool)
                or not isinstance(observation.class_id, Integral)
                or observation.class_id != spec["ideal_box"]["class_id"]
            ):
                raise ValueError("invalid public observation metadata")
            rows.append(
                {
                    "frame": frame,
                    "track_id": int(identity),
                    "xyxy": box.tolist(),
                    "score": float(observation.score),
                    "class_id": int(observation.class_id),
                }
            )
        if len(rows) > 100_000:
            raise ValueError("public output row limit exceeded")
    if tracker.frame_index != grid["frames"] - 1:
        raise ValueError("incomplete tracker replay")
    return rows


def _anchor_samples(rows: list[dict], projection: GroundProjection, anchor: str) -> list:
    if anchor not in {"bottom_centre", "box_centre"}:
        raise ValueError("unknown reported anchor")
    samples = []
    for row in rows:
        x1, y1, x2, y2 = row["xyxy"]
        pixel = np.array([(x1 + x2) / 2, y2 if anchor == "bottom_centre" else (y1 + y2) / 2])
        x, y = projection.unproject(pixel)
        samples.append(AnchorSample(row["frame"], row["track_id"], x, y))
    return samples


def run_development(*, scenario: str, seed: int, condition: str) -> dict:
    """Run one registered development case, with reset and fresh-instance replay.

    Deliberately no split/config override or held-out entry point. Three passes
    check identical public bytes; both anchors consume the same first pass.
    """
    spec, hashes = load_frozen_protocol()
    # Validate selectors before imports or tracker construction, never infer a split.
    scene = generate_scene(split="development", scenario=scenario, seed=seed, condition=condition)
    baseline = _verify_tree(ROOT, spec["baseline_revision"])
    from visiontrack.tracking.config import TrackerConfig
    from visiontrack.tracking.tracker import ByteTracker

    _check_import_origins()
    frozen = spec["tracker_config"]
    if {field.name for field in fields(TrackerConfig)} != set(frozen):
        raise ValueError("TrackerConfig fields differ from frozen baseline")
    config = TrackerConfig(**frozen)
    if asdict(config) != frozen:
        raise ValueError("constructed configuration differs from frozen baseline")
    tracker = ByteTracker(config)
    rows = _replay(tracker, scene, spec)
    tracker.reset()
    reset_rows = _replay(tracker, scene, spec)
    fresh_rows = _replay(ByteTracker(TrackerConfig(**frozen)), scene, spec)
    payload = _json_bytes(rows)
    if payload != _json_bytes(reset_rows) or payload != _json_bytes(fresh_rows):
        raise ValueError("baseline reset/fresh replay mismatch")
    _check_import_origins()
    if _verify_tree(ROOT, spec["baseline_revision"]) != baseline:
        raise ValueError("baseline source changed during replay")
    projection_name = next(c["projection"] for c in spec["conditions"] if c["id"] == condition)
    projection = GroundProjection(np.array(spec["projection"][projection_name]))
    truth = extract_crossings(
        [
            AnchorSample(frame, identity, *scene.world_contacts[frame, index])
            for frame in range(len(scene.frames))
            for index, identity in enumerate(scene.object_ids)
        ]
    )
    anchors = {
        anchor: score_crossings(truth, extract_crossings(_anchor_samples(rows, projection, anchor)))
        for anchor in spec["anchors"]
    }
    experiment_sources = {
        str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted((ROOT / "experiments").glob("traffic_*.py"))
    }
    result = {
        "format": "visiontrack.traffic-development-replay/v1",
        "protocol_id": spec["protocol_id"],
        "protocol_hashes": hashes,
        "input": scene.manifest(),
        "detection_sha256": _digest_arrays(
            {
                "frames": scene.frames,
                "xyxy": scene.observed_boxes,
                "score": np.full(scene.observed_boxes.shape[:2], spec["ideal_box"]["score"]),
                "class_id": np.full(scene.observed_boxes.shape[:2], spec["ideal_box"]["class_id"]),
            }
        ),
        "detection_features": None,
        "config": frozen,
        "config_sha256": hashlib.sha256(_json_bytes(frozen)).hexdigest(),
        "source": {
            "actual_revision": _git(ROOT, "rev-parse", "HEAD").decode().strip(),
            "tracked_worktree_dirty": bool(_git(ROOT, "status", "--porcelain", "-uno")),
            "baseline": baseline,
            "experiment_sha256": experiment_sources,
        },
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "system": platform.system(),
            "machine": platform.machine(),
            "byteorder": sys.byteorder,
        },
        "replay": {
            "passes": 3,
            "reset_equal": True,
            "fresh_equal": True,
            "updates_per_pass": len(scene.frames),
        },
        "output": rows,
        "output_sha256": hashlib.sha256(payload).hexdigest(),
        "crossing": anchors,
        "heldout_tracking_executed": False,
        "complete_study_report": False,
        "limitations": [
            "Development synthetic mechanism check, not measured traffic accuracy or improvement.",
            "Tracking/completeness/localization strata and paired study summaries remain pending.",
            "Dependency versions recorded, not a cross-environment bit-parity guarantee.",
            "Input manifest describes generator inputs; tracker execution is recorded separately.",
        ],
    }
    result["record_sha256"] = hashlib.sha256(_json_bytes(result)).hexdigest()
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--condition", required=True)
    args = parser.parse_args()
    try:
        record = run_development(scenario=args.scenario, seed=args.seed, condition=args.condition)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"Development replay failed: {exc}", file=sys.stderr)
        return 2
    print(
        json.dumps(
            {
                "format": record["format"],
                "scenario": args.scenario,
                "seed": args.seed,
                "condition": args.condition,
                "output_rows": len(record["output"]),
                "output_sha256": record["output_sha256"],
                "replay": record["replay"],
                "crossing": {name: score["summary"] for name, score in record["crossing"].items()},
                "complete_study_report": False,
                "heldout_tracking_executed": False,
            },
            indent=2,
            allow_nan=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
