"""Read-only independent scalar audit of saved continuity-warning study records."""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
from pathlib import Path


def _bytes(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def _hash(value):
    return hashlib.sha256(_bytes(value)).hexdigest()


def _overlap(a, b):
    left, top = max(a[0], b[0]), max(a[1], b[1])
    right, bottom = min(a[2], b[2]), min(a[3], b[3])
    intersection = max(right - left, 0) * max(bottom - top, 0)
    area_a = (a[2] - a[0]) * (a[3] - a[1])
    area_b = (b[2] - b[0]) * (b[3] - b[1])
    return intersection / (area_a + area_b - intersection)


def _exhaustive_capacity(tracks, rows, adjacency):
    if len(tracks) > 8 or len(rows) > 8:
        raise ValueError("audit component larger than exhaustive bound")
    best = 0
    for length in range(1, min(len(tracks), len(rows)) + 1):
        for chosen_tracks in itertools.combinations(tracks, length):
            for chosen_rows in itertools.permutations(rows, length):
                if all(row in adjacency[track]
                       for track, row in zip(chosen_tracks, chosen_rows, strict=True)):
                    best = length
                    break
            if best == length:
                break
    return best


def audit_frame(frame, previous, detections, warning):
    if warning["frame"] != frame or warning["previous_count"] != len(previous):
        raise ValueError("frame or previous count mismatch")
    if warning["previous_fingerprint"] != _hash(previous):
        raise ValueError("previous public fingerprint mismatch")
    indexed = [dict(row_index=i, xyxy=item["xyxy"], score=item["score"],
                    class_id=item["class_id"]) for i, item in enumerate(detections)]
    if warning["detections_fingerprint"] != _hash(indexed):
        raise ValueError("detector fingerprint mismatch")
    eligible = [item for item in indexed if item["score"] >= 0.1]
    if warning["eligible_count"] != len(eligible):
        raise ValueError("eligible detector count mismatch")
    adjacency = {item["track_id"]: set() for item in previous}
    expected_edges = []
    for track in previous:
        for row in eligible:
            if track["class_id"] == row["class_id"]:
                iou = _overlap(track["xyxy"], row["xyxy"])
                if iou >= 0.3:
                    adjacency[track["track_id"]].add(row["row_index"])
                    expected_edges.append((track["track_id"], row["row_index"], iou))
    actual_edges = [(row["track_id"], row["row_index"], row["iou"])
                    for row in warning["edges"]]
    if [(a, b) for a, b, _ in actual_edges] != [(a, b) for a, b, _ in expected_edges]:
        raise ValueError("edge set/order mismatch")
    if any(not math.isclose(actual[2], expected[2], rel_tol=0, abs_tol=1e-12)
           for actual, expected in zip(actual_edges, expected_edges, strict=True)):
        raise ValueError("edge overlap mismatch")
    unsupported = sorted(track for track, rows in adjacency.items() if not rows)
    if warning["unsupported_track_ids"] != unsupported:
        raise ValueError("unsupported track mismatch")
    if warning["two_supported_previous_tracks"] != (
        sum(bool(rows) for rows in adjacency.values()) >= 2
    ) or warning["assessment_opportunity"] != bool(previous):
        raise ValueError("assessment opportunity mismatch")

    remaining = {track for track, rows in adjacency.items() if rows}
    expected_components = []
    while remaining:
        start = min(remaining)
        component_tracks, component_rows = {start}, set(adjacency[start])
        while True:
            expanded = {track for track in remaining if adjacency[track] & component_rows}
            next_tracks = component_tracks | expanded
            next_rows = set().union(*(adjacency[track] for track in next_tracks))
            if next_tracks == component_tracks and next_rows == component_rows:
                break
            component_tracks, component_rows = next_tracks, next_rows
        remaining -= component_tracks
        tracks, rows = sorted(component_tracks), sorted(component_rows)
        expected_components.append((tracks, rows, _exhaustive_capacity(tracks, rows, adjacency)))
    actual = warning["components"]
    if len(actual) != len(expected_components):
        raise ValueError("component count mismatch")
    expected_warned = []
    for component, (tracks, rows, capacity) in zip(actual, expected_components, strict=True):
        if (component["track_ids"] != tracks or component["row_indices"] != rows or
            component["maximum_matching_cardinality"] != capacity or
            component["deficit"] != len(tracks) - capacity):
            raise ValueError("independent component capacity mismatch")
        witness = component["matching_witness"]
        if (len(witness) != capacity or len({pair[0] for pair in witness}) != capacity or
            len({pair[1] for pair in witness}) != capacity or
            any(track not in tracks or row not in adjacency[track]
                for track, row in witness)):
            raise ValueError("invalid matching witness")
        if len(tracks) >= 2 and capacity < len(tracks):
            expected_warned.append(component)
    if warning["warnings"] != [dict(reason="insufficient_distinct_box_support", **item)
                               for item in expected_warned]:
        raise ValueError("warning component mismatch")


def audit_saved(directory: Path) -> dict:
    manifest = json.loads((directory / "manifest.json").read_text())
    actual_files = {str(path.relative_to(directory)) for path in directory.rglob("*")
                    if path.is_file()} - {"manifest.json"}
    if actual_files != set(manifest):
        raise ValueError("manifest coverage mismatch")
    for relative, record in manifest.items():
        data = (directory / relative).read_bytes()
        if len(data) != record["bytes"] or hashlib.sha256(data).hexdigest() != record["sha256"]:
            raise ValueError(f"saved file drift: {relative}")
    method = json.loads((directory / "method.json").read_text())
    summary = json.loads((directory / "summary.json").read_text())
    spec = method["recipe"]
    if (summary["tracker_passes"] != 108 or len(summary["cells"]) != 27 or
        method["grid"]["unique_detector_payloads"] != 16):
        raise ValueError("incomplete saved grid")
    frames_checked = components_checked = 0
    for cell in summary["cells"]:
        folder = directory / f'{cell["duration"]:02d}-{cell["family"]}'
        inputs = json.loads((folder / "inputs.json").read_text())
        outputs = json.loads((folder / "outputs-1.json").read_text())
        warnings = json.loads((folder / "warnings-1.json").read_text())
        scored = json.loads((folder / "scored.json").read_text())
        if len(inputs) != len(outputs) or len(inputs) != len(warnings):
            raise ValueError("saved cell frame count mismatch")
        if len(inputs) != spec["scene"]["frames"]:
            raise ValueError("incomplete saved cell")
        if (cell["metrics"] != scored["metrics"] or
            cell["warning_frames"] != scored["warning_frames"]):
            raise ValueError("cell scoring summary mismatch")
        for frame in range(len(inputs)):
            previous = sorted((outputs[frame - 1]["observations"] if frame else []),
                              key=lambda row: row["track_id"])
            audit_frame(frame, previous, inputs[frame]["detections"], warnings[frame])
            frames_checked += 1
            components_checked += len(warnings[frame]["components"])
    return dict(cells_checked=len(summary["cells"]), frames_checked=frames_checked,
                components_checked=components_checked, files_checked=len(manifest),
                independent_physical_validation=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    print(json.dumps(audit_saved(args.directory), sort_keys=True))


if __name__ == "__main__":
    main()
