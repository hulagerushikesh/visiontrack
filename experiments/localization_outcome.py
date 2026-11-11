"""Offline, dataset-agnostic localization comparison; never changes tracking.

Call only after source rights, scene units, class mapping and independent box
review are recorded separately. The inputs here are already mapped classes and
explicitly eligible references. Synthetic tests exercise mechanics, not accuracy.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass

import numpy as np
from scipy.optimize import linear_sum_assignment

MIN_IOU = 0.5
COVERAGES = (0.10, 0.25, 0.50, 0.75, 1.0)
SPREAD_STATUSES = {
    "supported", "frame_truncated", "missing_winner", "incomplete_group",
    "singleton_group", "few_same_class", "invalid_geometry",
}


@dataclass(frozen=True)
class DetectionRow:
    class_id: str
    xyxy: tuple[float, float, float, float]
    score: float
    spread_status: str
    spread: float | None
    group_size: int | None = None  # Complete suppression group, when recorded.


@dataclass(frozen=True)
class ReferenceRow:
    class_id: str
    xyxy: tuple[float, float, float, float]
    eligible: bool = True
    visibility: str = "unknown"  # Dataset mapping is declared by the source adapter.


@dataclass(frozen=True)
class Frame:
    split: str  # "development" or "test"; never mix one scene across splits.
    scene: str
    key: str
    detections: tuple[DetectionRow, ...]
    references: tuple[ReferenceRow, ...]


@dataclass(frozen=True)
class MatchedRow:
    scene: str
    key: tuple[str, str, int]
    class_id: str
    width: float
    height: float
    score: float
    spread: float | None
    error: float
    pixel_error: float
    iou_error: float
    visibility: str = "unknown"
    group_size: int | None = None
    match_ambiguous: bool = False


def _box(box: tuple[float, ...]) -> None:
    if len(box) != 4 or not all(math.isfinite(v) for v in box):
        raise ValueError("box must have four finite coordinates")
    if box[2] <= box[0] or box[3] <= box[1]:
        raise ValueError("box must have positive width and height")


def _iou(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    x1, y1 = max(a[0], b[0]), max(a[1], b[1])
    x2, y2 = min(a[2], b[2]), min(a[3], b[3])
    intersection = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    area_a = (a[2] - a[0]) * (a[3] - a[1])
    area_b = (b[2] - b[0]) * (b[3] - b[1])
    return intersection / (area_a + area_b - intersection)


def _frame_rows(frame: Frame) -> tuple[list[MatchedRow], Counter[str]]:
    if frame.split not in {"development", "test"} or not frame.scene or not frame.key:
        raise ValueError("frame needs a declared split, scene and key")
    for det in frame.detections:
        _box(det.xyxy)
        if not det.class_id or not math.isfinite(det.score) or not 0 <= det.score <= 1:
            raise ValueError("invalid detection class or score")
        if det.spread_status not in SPREAD_STATUSES:
            raise ValueError("unknown proposal spread status")
        if det.spread_status == "supported":
            if det.spread is None or not math.isfinite(det.spread) or det.spread < 0:
                raise ValueError("supported spread must be finite and nonnegative")
        elif det.spread is not None:
            raise ValueError("unsupported spread must be absent")
        if det.group_size is not None and (type(det.group_size) is not int or det.group_size < 1):
            raise ValueError("group size must be a positive integer when declared")
        if det.spread_status == "supported" and det.group_size is not None and det.group_size < 3:
            raise ValueError("supported spread needs at least three group members")
    for ref in frame.references:
        _box(ref.xyxy)
        if not ref.class_id:
            raise ValueError("reference class is empty")
        if not ref.visibility or not isinstance(ref.visibility, str):
            raise ValueError("reference visibility must be a nonempty label")
    eligible = [ref for ref in frame.references if ref.eligible]
    n, m = len(frame.detections), len(eligible)
    totals: Counter[str] = Counter({
        "detections": n, "eligible_references": m,
        "excluded_references": len(frame.references) - m,
        "supported_detections": sum(d.spread_status == "supported" for d in frame.detections),
        "ambiguous_matches": 0, "ambiguous_frames": 0,
    })
    totals.update(f"spread_status_{d.spread_status}" for d in frame.detections)
    if not n or not m:
        totals["unmatched_detections"] = n
        totals["missed_references"] = m
        return [], totals
    overlaps = np.zeros((n, m), dtype=np.float64)
    for i, det in enumerate(frame.detections):
        for j, ref in enumerate(eligible):
            if det.class_id == ref.class_id:
                overlaps[i, j] = _iou(det.xyxy, ref.xyxy)
    # Dummy rows/columns allow unmatched items. Ineligible edges cost more than
    # unmatched; eligible pairs maximize total IoU, not tracker associations.
    cost = np.zeros((n + m, n + m), dtype=np.float64)
    cost[:n, :m] = np.where(overlaps >= MIN_IOU, -overlaps, 1.0)
    assigned_rows, assigned_cols = linear_sum_assignment(cost)
    optimum = float(cost[assigned_rows, assigned_cols].sum())
    # An equally good assignment may attach a detection to another reference
    # (or leave it unmatched). Keep the fixed solver result for the target, but
    # expose that ambiguity rather than implying its reference is certain.
    ambiguous_indices: set[int] = set()
    for i, j in zip(assigned_rows, assigned_cols, strict=True):
        if i >= n or j >= m or overlaps[i, j] < MIN_IOU:
            continue
        if np.count_nonzero(overlaps[i] >= MIN_IOU) == 1 and np.count_nonzero(
            overlaps[:, j] >= MIN_IOU) == 1:
            continue
        alternative = cost.copy()
        alternative[i, j] = 1.0
        other_rows, other_cols = linear_sum_assignment(alternative)
        if math.isclose(float(alternative[other_rows, other_cols].sum()),
                        optimum, rel_tol=0.0, abs_tol=1e-12):
            ambiguous_indices.add(int(i))
    totals["ambiguous_matches"] = len(ambiguous_indices)
    totals["ambiguous_frames"] = int(bool(ambiguous_indices))
    matched: list[MatchedRow] = []
    for i, j in zip(assigned_rows, assigned_cols, strict=True):
        if i >= n or j >= m or overlaps[i, j] < MIN_IOU:
            continue
        det, ref = frame.detections[i], eligible[j]
        dx = (det.xyxy[0] + det.xyxy[2] - ref.xyxy[0] - ref.xyxy[2]) / 2
        dy = det.xyxy[3] - ref.xyxy[3]
        pixel_error = math.hypot(dx, dy)
        matched.append(MatchedRow(
            frame.scene, (frame.scene, frame.key, int(i)), det.class_id,
            det.xyxy[2] - det.xyxy[0], det.xyxy[3] - det.xyxy[1],
            det.score, det.spread, pixel_error / (ref.xyxy[3] - ref.xyxy[1]),
            pixel_error, 1.0 - float(overlaps[i, j]), ref.visibility, det.group_size,
            int(i) in ambiguous_indices,
        ))
    totals["matched"] = len(matched)
    totals["unmatched_detections"] = n - len(matched)
    totals["missed_references"] = m - len(matched)
    totals["supported_matches"] = sum(row.spread is not None for row in matched)
    return matched, totals


def prepare(frames: list[Frame]) -> tuple[dict[str, list[MatchedRow]], dict[str, dict]]:
    """Check split isolation, then derive matched targets and coverage counts."""
    seen: set[tuple[str, str]] = set()
    scene_split: dict[str, str] = {}
    rows: dict[str, list[MatchedRow]] = {"development": [], "test": []}
    counts = {"development": Counter(), "test": Counter()}
    for frame in frames:
        key = (frame.scene, frame.key)
        if key in seen:
            raise ValueError("duplicate scene/frame key")
        seen.add(key)
        if frame.scene in scene_split and scene_split[frame.scene] != frame.split:
            raise ValueError("scene leaks across development and test")
        scene_split[frame.scene] = frame.split
        matched, inventory = _frame_rows(frame)
        rows[frame.split].extend(matched)
        counts[frame.split].update(inventory)
        counts[frame.split]["frames"] += 1
    if not rows["development"] or not rows["test"]:
        raise ValueError("both splits need matched boxes")
    for split in counts:
        counts[split]["scenes"] = sum(s == split for s in scene_split.values())
    return rows, {split: dict(count) for split, count in counts.items()}


def _features(rows: list[MatchedRow], classes: tuple[str, ...], level: int) -> np.ndarray:
    class_columns = [[float(row.class_id == name) for name in classes[1:]] for row in rows]
    numeric = [[math.log(row.width), math.log(row.height)] for row in rows]
    if level >= 2:
        for row, features in zip(rows, numeric, strict=True):
            features.append(row.score)
    if level >= 3:
        for row, features in zip(rows, numeric, strict=True):
            assert row.spread is not None
            features.append(row.spread)
    return np.asarray([cat + num for cat, num in zip(class_columns, numeric, strict=True)])


def _predict(train: list[MatchedRow], test: list[MatchedRow], level: int) -> np.ndarray:
    if level == 0:
        return np.full(len(test), np.mean([r.error for r in train]))
    classes = tuple(sorted({row.class_id for row in train}))
    x_train = _features(train, classes, level)
    x_test = _features(test, classes, level)
    # Only numeric columns are standardized. One-hot indicators remain 0/1.
    ncat = len(classes) - 1
    mean = x_train[:, ncat:].mean(axis=0)
    scale = x_train[:, ncat:].std(axis=0)
    scale[scale == 0] = 1.0
    x_train[:, ncat:] = (x_train[:, ncat:] - mean) / scale
    x_test[:, ncat:] = (x_test[:, ncat:] - mean) / scale
    target = np.log1p([row.error for row in train])
    # Center every feature when fitting so the intercept is truly unpenalized,
    # including the non-standardized class indicators.
    feature_mean = x_train.mean(axis=0)
    centered_x = x_train - feature_mean
    coef = np.linalg.solve(centered_x.T @ centered_x + np.eye(x_train.shape[1]),
                           centered_x.T @ (target - target.mean()))
    intercept = target.mean() - feature_mean @ coef
    return np.maximum(np.expm1(intercept + x_test @ coef), 0.0)


def _area(rows: list[MatchedRow], predictions: np.ndarray) -> tuple[float, dict[str, float]]:
    order = sorted(range(len(rows)), key=lambda i: (float(predictions[i]), rows[i].key))
    errors = np.asarray([rows[i].error for i in order])
    curve = np.cumsum(errors) / np.arange(1, len(errors) + 1)
    samples = {f"{int(fraction * 100)}%": float(curve[max(0, math.ceil(len(rows) * fraction) - 1)])
               for fraction in COVERAGES}
    return float(curve.mean()), samples


def _scene_contrast(
    rows: list[MatchedRow], b2: np.ndarray, b3: np.ndarray, resamples: int, seed: int,
) -> tuple[dict[str, float], float, list[float] | None]:
    deltas: dict[str, float] = {}
    for scene in sorted({row.scene for row in rows}):
        indices = [i for i, row in enumerate(rows) if row.scene == scene]
        group = [rows[i] for i in indices]
        a2, _ = _area(group, b2[indices])
        a3, _ = _area(group, b3[indices])
        deltas[scene] = a3 - a2
    values = np.asarray(list(deltas.values()))
    interval = None
    if len(deltas) >= 8 and len(rows) >= 50:
        rng = np.random.default_rng(seed)
        sampled = rng.integers(0, len(values), size=(resamples, len(values)))
        interval = [float(v) for v in np.quantile(values[sampled].mean(axis=1),
                                                 [0.025, 0.975])]
    return deltas, float(values.mean()), interval


def _group_size_bin(size: int | None) -> str:
    if size is None:
        return "undeclared"
    if size == 3:
        return "3"
    if size <= 7:
        return "4-7"
    return "8+"


def _ambiguity_sensitivity(
    train: list[MatchedRow], test: list[MatchedRow], resamples: int, seed: int,
) -> dict:
    """Refit and compare on the same unambiguous supported population."""
    clean_train = [row for row in train if not row.match_ambiguous]
    clean_classes = {row.class_id for row in clean_train}
    clean_test = [row for row in test if not row.match_ambiguous
                  and row.class_id in clean_classes]
    result: dict = {
        "development_matches": len(clean_train),
        "test_matches": len(clean_test),
        "test_scenes": len({row.scene for row in clean_test}),
        "excluded_ambiguous_development_matches": len(train) - len(clean_train),
        "excluded_ambiguous_test_matches": sum(row.match_ambiguous for row in test),
        "excluded_unseen_class_test_matches": sum(
            not row.match_ambiguous and row.class_id not in clean_classes for row in test
        ),
    }
    if not clean_train or not clean_test:
        result["status"] = "unavailable: no supported unambiguous matches in both splits"
        return result
    b2 = _predict(clean_train, clean_test, 2)
    b3 = _predict(clean_train, clean_test, 3)
    area2, _ = _area(clean_test, b2)
    area3, _ = _area(clean_test, b3)
    _, scene_mean, interval = _scene_contrast(clean_test, b2, b3, resamples, seed)
    result.update({
        "status": "scene-clustered" if interval is not None else "descriptive",
        "B2_area": area2,
        "B3_area": area3,
        "pooled_delta": area3 - area2,
        "scene_mean_delta": scene_mean,
        "scene_bootstrap_95pct": interval,
    })
    return result


def compare(frames: list[Frame], *, resamples: int = 10_000,
            seed: int = 20261104) -> dict:
    """Frozen B0-B3 comparison. Output is descriptive until source is admitted."""
    if resamples <= 0:
        raise ValueError("resamples must be positive")
    split_rows, counts = prepare(frames)
    train, test = split_rows["development"], split_rows["test"]
    trained_classes = {row.class_id for row in train}
    broad = [row for row in test if row.class_id in trained_classes]
    supported_train = [row for row in train if row.spread is not None]
    supported_classes = {row.class_id for row in supported_train}
    supported = [row for row in broad
                 if row.spread is not None and row.class_id in supported_classes]
    if not supported_train or not supported or not broad:
        raise ValueError("need supported matched boxes in both splits")
    # Preserve every declared test scene, including those with no detections or
    # matches. The paired cohort alone would silently drop those cameras.
    scene_coverage: dict[str, Counter[str]] = {}
    for frame in frames:
        if frame.split != "test":
            continue
        scene = scene_coverage.setdefault(frame.scene, Counter())
        scene["frames"] += 1
        scene["detections"] += len(frame.detections)
        scene["eligible_references"] += sum(ref.eligible for ref in frame.references)
        scene["supported_detections"] += sum(
            det.spread_status == "supported" for det in frame.detections
        )
    for row in test:
        scene_coverage[row.scene]["matched"] += 1
        scene_coverage[row.scene]["supported_matches"] += row.spread is not None
    for row in supported:
        scene_coverage[row.scene]["paired_matches"] += 1
    missing_paired_scenes = sorted(
        scene for scene, inventory in scene_coverage.items()
        if not inventory["paired_matches"]
    )
    scene_coverage_report = {
        scene: {
            **{name: inventory[name] for name in (
                "frames", "detections", "eligible_references", "supported_detections",
                "matched", "supported_matches", "paired_matches",
            )},
            "status": (
                "no_detections" if not inventory["detections"]
                else "no_paired_matches" if not inventory["paired_matches"]
                else "paired"
            ),
        }
        for scene, inventory in sorted(scene_coverage.items())
    }
    results: dict[str, dict] = {}
    for level in range(3):
        prediction = _predict(train, broad, level)
        area, points = _area(broad, prediction)
        results[f"B{level}_broad"] = {"matches": len(broad), "area": area,
                                     "risk_at_coverage": points}
    # For a fair paired comparison, B2 and B3 fit on the same development
    # subset and rank the identical supported test detections.
    b2 = _predict(supported_train, supported, 2)
    b3 = _predict(supported_train, supported, 3)
    for name, prediction in (("B2_paired", b2), ("B3_paired", b3)):
        area, points = _area(supported, prediction)
        results[name] = {"matches": len(supported), "area": area,
                         "risk_at_coverage": points}
    scene_deltas, scene_mean, interval = _scene_contrast(
        supported, b2, b3, resamples, seed)
    ambiguity_sensitivity = _ambiguity_sensitivity(
        supported_train, supported, resamples, seed)
    # Height boundaries are fitted on supported development detections only.
    # Duplicate boundaries may leave an empty bin; report the populated bins.
    height_cuts = np.quantile([row.height for row in supported_train], [.25, .5, .75])
    strata: dict[str, dict[str, dict]] = {}
    dimensions = {
        "class": [row.class_id for row in supported],
        "predicted_height_quartile": [
            f"Q{int(np.searchsorted(height_cuts, row.height, side='left')) + 1}"
            for row in supported
        ],
        "visibility": [row.visibility for row in supported],
        "group_size": [_group_size_bin(row.group_size) for row in supported],
    }
    for dimension, labels in dimensions.items():
        strata[dimension] = {}
        for label in sorted(set(labels)):
            indices = [i for i, value in enumerate(labels) if value == label]
            group = [supported[i] for i in indices]
            area2, _ = _area(group, b2[indices])
            area3, _ = _area(group, b3[indices])
            _, mean_delta, group_interval = _scene_contrast(
                group, b2[indices], b3[indices], resamples, seed)
            strata[dimension][label] = {
                "matches": len(group), "scenes": len({row.scene for row in group}),
                "B2_area": area2, "B3_area": area3,
                "pooled_delta": area3 - area2,
                "scene_mean_delta": mean_delta,
                "scene_bootstrap_95pct": group_interval,
                "status": "scene-clustered" if group_interval is not None else "descriptive",
            }
    descriptions = {}
    for name, cohort in (("broad", broad), ("paired", supported)):
        descriptions[name] = {
            "mean_pixel_error": float(np.mean([row.pixel_error for row in cohort])),
            "median_pixel_error": float(np.median([row.pixel_error for row in cohort])),
            "mean_one_minus_iou": float(np.mean([row.iou_error for row in cohort])),
        }
    return {
        "schema": "visiontrack.localization-outcome/v1",
        "matching": "same-class max total IoU, one-to-one, IoU >= 0.5; eligible refs only",
        "metric": "mean normalized bottom-anchor error versus retained coverage; lower is better",
        "counts": counts,
        "unseen_test_class_matches": len(test) - len(broad),
        "paired_coverage_of_all_test_detections": len(supported) / counts["test"]["detections"],
        "paired_scene_coverage": scene_coverage_report,
        "test_scenes_without_paired_matches": missing_paired_scenes,
        "results": results,
        "target_descriptions": descriptions,
        "per_scene_paired_delta": scene_deltas,
        "paired_scene_mean_delta": scene_mean,
        "paired_scene_bootstrap_95pct": interval,
        "unambiguous_paired_sensitivity": ambiguity_sensitivity,
        "interval_status": "descriptive" if interval is None else "scene-clustered",
        "predicted_height_development_quartile_cuts": [float(v) for v in height_cuts],
        "paired_strata": strata,
        "independent_truth_verified_by_this_code": False,
    }
