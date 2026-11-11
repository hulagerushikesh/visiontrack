"""Compare two pinned UVH-26 validation consensus files, without image scoring.

MV and ST derive from the same crowdsourced annotations. Their agreement is a
label-stability diagnostic, never independent accuracy or detector truth.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import scipy
from scipy.optimize import linear_sum_assignment

EXPECTED_SHA256 = {
    "MV": "9d279f48589e653d7749b9636c945a8763b457c067f23ea79def3fa70c8e8ab4",
    "ST": "ced5798e3f4d8babf95f463a1490b0b6251d634c37400c250edf2d656f26b811",
}
MIN_IOU = 0.5
COCO_COMPARABLE = {
    1: "car", 2: "car", 3: "car", 4: "car", 13: "car",
    5: "bus", 10: "bus", 6: "truck",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load(path: Path, consensus: str) -> tuple[dict, dict[str, list[dict]]]:
    if _sha256(path) != EXPECTED_SHA256[consensus]:
        raise ValueError(f"{consensus} validation JSON fingerprint mismatch")
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("licenses") != [{
        "id": 1, "name": "CC BY 4.0", "url": "https://creativecommons.org/licenses/by/4.0/"
    }]:
        raise ValueError("unexpected annotation license")
    images = {row["id"]: row for row in data["images"]}
    if len(images) != len(data["images"]):
        raise ValueError("duplicate image ID")
    names = {row["file_name"] for row in data["images"]}
    if len(names) != len(images):
        raise ValueError("duplicate image filename")
    categories = {row["id"]: row["name"] for row in data["categories"]}
    if len(categories) != len(data["categories"]):
        raise ValueError("duplicate category ID")
    by_name: dict[str, list[dict]] = defaultdict(list)
    ids = set()
    for ann in data["annotations"]:
        if ann["id"] in ids or ann["image_id"] not in images:
            raise ValueError("duplicate annotation ID or unknown image")
        ids.add(ann["id"])
        if ann["category_id"] not in categories:
            raise ValueError("unknown category")
        x, y, w, h = ann["bbox"]
        image = images[ann["image_id"]]
        if (not all(math.isfinite(v) for v in (x, y, w, h))
                or x < 0 or y < 0 or w <= 0 or h <= 0
                or x + w > image["width"] + 1e-6
                or y + h > image["height"] + 1e-6):
            raise ValueError("invalid annotation geometry")
        by_name[image["file_name"]].append(ann)
    for rows in by_name.values():
        rows.sort(key=lambda row: row["id"])
    return {"images": {r["file_name"]: r for r in data["images"]},
            "categories": categories, "annotation_count": len(ids)}, by_name


def _iou(left: list[dict], right: list[dict]) -> np.ndarray:
    a = np.asarray([r["bbox"] for r in left], dtype=np.float64)
    b = np.asarray([r["bbox"] for r in right], dtype=np.float64)
    if not len(a) or not len(b):
        return np.zeros((len(a), len(b)), dtype=np.float64)
    a2, b2 = a[:, :2] + a[:, 2:], b[:, :2] + b[:, 2:]
    tl = np.maximum(a[:, None, :2], b[None, :, :2])
    br = np.minimum(a2[:, None, :], b2[None, :, :])
    inter = np.prod(np.maximum(br - tl, 0), axis=2)
    union = np.prod(a[:, 2:], axis=1)[:, None] + np.prod(b[:, 2:], axis=1)[None, :] - inter
    return inter / union


def _pairs(left: list[dict], right: list[dict]) -> list[tuple[int, int, float]]:
    """Maximize eligible pair count, then IoU; class is deliberately ignored."""
    n, m = len(left), len(right)
    if not n or not m:
        return []
    overlaps = _iou(left, right)
    # A valid pair is worth more than any IoU gain from replacing one match.
    benefit = np.where(overlaps >= MIN_IOU, min(n, m) + 1.0 + overlaps, -1e6)
    padded = np.zeros((n + m, n + m), dtype=np.float64)
    padded[:n, :m] = -benefit
    rows, cols = linear_sum_assignment(padded)
    return [(int(i), int(j), float(overlaps[i, j]))
            for i, j in zip(rows, cols, strict=True)
            if i < n and j < m and overlaps[i, j] >= MIN_IOU]


def _quantiles(values: list[float]) -> dict[str, float] | None:
    if not values:
        return None
    return {key: round(float(np.quantile(values, q)), 6)
            for key, q in (("p10", .1), ("median", .5), ("p90", .9))}


def audit(mv_path: Path, st_path: Path) -> dict:
    mv, mv_rows = _load(mv_path, "MV")
    st, st_rows = _load(st_path, "ST")
    if mv["categories"] != st["categories"]:
        raise ValueError("consensus category definitions differ")
    mv_names, st_names = set(mv["images"]), set(st["images"])
    shared = sorted(mv_names & st_names)
    if any((mv["images"][name]["width"], mv["images"][name]["height"])
           != (st["images"][name]["width"], st["images"][name]["height"])
           for name in shared):
        raise ValueError("shared image dimensions differ")
    totals: Counter[str] = Counter()
    ious: list[float] = []
    anchor_gaps: list[float] = []
    class_disagreements: Counter[str] = Counter()
    for name in shared:
        a, b = mv_rows[name], st_rows[name]
        pairs = _pairs(a, b)
        totals["mv_boxes_shared"] += len(a)
        totals["st_boxes_shared"] += len(b)
        totals["matched_boxes"] += len(pairs)
        totals["mv_boxes_unmatched"] += len(a) - len(pairs)
        totals["st_boxes_unmatched"] += len(b) - len(pairs)
        totals["images_with_box_count_difference"] += len(a) != len(b)
        totals["images_with_unmatched_box"] += len(pairs) != max(len(a), len(b))
        for i, j, overlap in pairs:
            ious.append(overlap)
            totals["matched_identical_boxes"] += a[i]["bbox"] == b[j]["bbox"]
            totals["matched_iou_below_0_9"] += overlap < .9
            ax, ay, aw, ah = a[i]["bbox"]
            bx, by, bw, bh = b[j]["bbox"]
            gap = math.hypot((ax + aw / 2) - (bx + bw / 2),
                             (ay + ah) - (by + bh)) / ah
            anchor_gaps.append(gap)
            totals["matched_anchor_gap_nonzero"] += gap > 1e-9
            left_coarse = COCO_COMPARABLE.get(a[i]["category_id"])
            right_coarse = COCO_COMPARABLE.get(b[j]["category_id"])
            if left_coarse is not None and right_coarse is not None:
                totals["both_coco_comparable"] += 1
                totals["coco_coarse_class_disagreement"] += left_coarse != right_coarse
            if a[i]["category_id"] != b[j]["category_id"]:
                totals["matched_class_disagreement"] += 1
                class_disagreements[f"{a[i]['category_id']}->{b[j]['category_id']}"] += 1
    return {
        "schema": "visiontrack.uvh26-consensus-audit/v1",
        "source": "iisc-aim/UVH-26@v1.0, validation MV and ST consensus",
        "scope": "annotation-only stability diagnostic; neither consensus is independent truth",
        "input_sha256": {"MV": EXPECTED_SHA256["MV"], "ST": EXPECTED_SHA256["ST"]},
        "dependencies": {"numpy": np.__version__, "scipy": scipy.__version__},
        "matching": (
            "per shared image, maximum eligible pair count then total IoU; "
            "class blind; IoU >= 0.5"
        ),
        "mv_images": len(mv_names), "st_images": len(st_names),
        "shared_images": len(shared), "mv_only_images": len(mv_names - st_names),
        "st_only_images": len(st_names - mv_names),
        "mv_annotations": mv["annotation_count"], "st_annotations": st["annotation_count"],
        "mv_boxes_on_mv_only_images": sum(len(mv_rows[n]) for n in mv_names - st_names),
        "shared_image_comparison": dict(totals),
        "matched_iou_quantiles": _quantiles(ious),
        "matched_anchor_gap_over_mv_height_quantiles": _quantiles(anchor_gaps),
        "top_class_disagreement_pairs_by_id": dict(class_disagreements.most_common(10)),
        "accuracy_claim": False, "detector_ran": False, "image_pixels_opened": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mv", type=Path, required=True)
    parser.add_argument("--st", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.mv, args.st)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
