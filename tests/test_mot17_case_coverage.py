"""Small authored counterexamples for descriptive coverage, not quality claims."""
import itertools
import json
from dataclasses import asdict

import numpy as np
import pytest

from experiments import mot17_case_coverage as coverage
from experiments.mot17_case_baseline import encoded, run_once
from visiontrack.detection.mot_loader import FrameData
from visiontrack.eval.mot import MotAccumulator
from visiontrack.eval.mot17 import preprocess_frame
from visiontrack.tracking.config import TrackerConfig

CFG = asdict(TrackerConfig())
BOX = [0., 0., 10., 10.]


def raw(detections, scores, gt=None, classes=None, output=None):
    gt = [BOX] if gt is None else gt
    output = [] if output is None else output
    return dict(source_frame=1, detections_xyxy=detections, detection_scores=scores,
                gt_ids=list(range(1, len(gt) + 1)), gt_xyxy=gt,
                gt_classes=classes if classes is not None else [1] * len(gt),
                gt_consider=[1.] * len(gt), gt_visibility=[1.] * len(gt),
                track_ids=list(range(1, len(output) + 1)), track_xyxy=output)


def diagnose(row):
    pairs = preprocess_frame(np.array(row["gt_xyxy"]).reshape(-1, 4),
                             np.array(row["gt_ids"], dtype=np.int64),
                             np.array(row["gt_classes"]), np.array(row["gt_consider"]),
                             np.array(row["track_xyxy"]).reshape(-1, 4),
                             np.array(row["track_ids"], dtype=np.int64))
    scored = dict(source_frame=1, **dict(zip(
        ("gt_ids", "gt_xyxy", "track_ids", "track_xyxy"),
        (p.tolist() for p in pairs), strict=True)))
    failures = [dict(source_frame=1, **asdict(f)) for f in MotAccumulator().update(*pairs)]
    return coverage.frame_diagnosis(row, scored, failures, CFG)


@pytest.mark.parametrize("shape", [(0, 2), (2, 0), (1, 3), (2, 3), (3, 3)])
def test_cardinality_matches_exhaustive_disjoint_edges(shape):
    n, m = shape
    for bits in itertools.product([0., 1.], repeat=n * m):
        matrix = np.array(bits).reshape(shape)
        expected = 0
        for size in range(min(n, m) + 1):
            for rows in itertools.combinations(range(n), size):
                for cols in itertools.permutations(range(m), size):
                    if all(matrix[r, c] for r, c in zip(rows, cols, strict=True)):
                        expected = max(expected, size)
        assert coverage.maximum_cardinality(matrix) == expected


def test_max_sum_iou_then_threshold_would_undercount():
    assert coverage.maximum_cardinality(np.array([[1., 0.5], [0.5, 0.49]])) == 2


@pytest.mark.parametrize("matrix", [np.array([1.]), np.array([[np.nan]]),
                                   np.array([[-0.1]]), np.array([[1.1]])])
def test_invalid_iou_rejected(matrix):
    with pytest.raises(ValueError):
        coverage.maximum_cardinality(matrix)


@pytest.mark.parametrize("detections,scores,group", [
    ([], [], "no_raw_geometric_neighbor"),
    ([[20., 0, 30, 10]], [1.], "no_raw_geometric_neighbor"),
    ([BOX], [0.099], "only_subthreshold_neighbors"),
    ([BOX], [0.1], "eligible_neighbor_without_scored_match"),
])
def test_fn_partition_and_inclusive_low_threshold(detections, scores, group):
    result = diagnose(raw(detections, scores))
    assert [r["group"] for r in result["misses"]] == [group]


def test_ignored_geometric_neighbor_is_not_claimed_available():
    row = raw([BOX], [1.], gt=[[0., 0, 5, 10], BOX], classes=[1, 7])
    result = diagnose(row)
    assert result["scoring_boxes"] == 1  # ignore is NOT an extra miss
    assert result["misses"][0]["group"] == "eligible_neighbors_removed_by_ignore"
    assert result["misses"][0]["best_raw_iou"] == 0.5
    assert result["pools"]["eligible"]["ignore_removed"] == 1
    assert result["pools"]["eligible"]["unique_gt_capacity"] == 0


def test_one_detection_cannot_cover_two_people_simultaneously():
    result = diagnose(raw([BOX], [1.], gt=[BOX, BOX]))
    pool = result["pools"]["eligible"]
    assert pool["pointwise_fn_neighbors"] == 2
    assert pool["fn_only_unique_capacity"] == pool["unique_gt_capacity"] == 1


def test_raw_box_capacity_is_not_smoothed_tracker_recall_ceiling():
    result = diagnose(raw([[20., 0, 30, 10]], [1.], output=[BOX]))
    assert result["misses"] == []
    assert result["matched_without_raw_neighbor"] == 1
    assert result["pools"]["eligible"]["unique_gt_capacity"] == 0


def test_existing_output_neighbor_can_be_consumed_by_another_reference():
    result = diagnose(raw([BOX], [1.], gt=[BOX, BOX], output=[BOX]))
    assert len(result["misses"]) == 1
    assert result["fn_with_scored_output_neighbor"] == 1
    assert result["misses"][0]["best_scored_output_iou"] == 1


def test_pools_apply_score_filter_before_ignore_assignment():
    row = raw([[2., 0, 12, 10], BOX], [0.9, 0.01],
              gt=[BOX, [5., 0, 15, 10]], classes=[1, 7])
    pools = diagnose(row)["pools"]
    assert pools["all_scores"]["ignore_removed"] == 1
    assert pools["eligible"]["ignore_removed"] == 0
    # The removed ordinal changes; one must not assume nested kept pools.
    assert pools["all_scores"]["kept_boxes"] == pools["eligible"]["kept_boxes"] == 1


def test_score_pools_are_not_claimed_actual_spawn_or_recovery():
    row = raw([BOX, BOX, BOX, BOX], [0.099, 0.1, 0.5, 0.6])
    pools = diagnose(row)["pools"]
    assert [pools[k]["input_boxes"] for k in
            ("all_scores", "eligible", "high", "spawn_score")] == [4, 3, 2, 1]


def test_rechecks_saved_canonical_failures_and_metrics(tmp_path):
    class Sequence:
        length = 5

        def iter_range(self, first, last):
            for frame in range(first, last + 1):
                yield FrameData(frame=frame, det_xyxy=np.array([BOX]), det_scores=np.array([1.]),
                                gt_xyxy=np.array([BOX]), gt_ids=np.array([1]),
                                gt_classes=np.array([1]), gt_conf=np.array([1.]),
                                gt_vis=np.array([1.]))
    run_once(Sequence(), tmp_path / "run")
    contents = {f"run-1/{name}": (tmp_path / "run" / name).read_bytes()
                for name in coverage.RUN_FILES}
    contents["plan.json"] = encoded(dict(tracker_config=CFG, scope=dict(source_frames=[1, 5])))
    emitted = []
    result = coverage.analyze(contents, emitted.append)
    assert result["fn_groups"]["eligible_neighbor_without_scored_match"] == 2
    assert len(emitted) == result["metrics"]["FN"] == 2
    assert result["other_checks"]["scoring_boxes"] == 5
    assert result["tracker_executed"] is False
    contents["run-1/failures.jsonl"] = b""
    with pytest.raises(ValueError, match="canonical failures mismatch"):
        coverage.analyze(contents, lambda row: None)


def tiny_bundle(path):
    (path / "run-1").mkdir()
    (path / "run-2").mkdir()
    names = [f"run-{i}/{n}" for i in (1, 2) for n in coverage.RUN_FILES]
    names += ["plan.json", "repeatability.json", "first-switch.json"]
    for name in names:
        (path / name).write_bytes(b"{}\n")
    manifest = {"files": {name: dict(bytes=(path / name).stat().st_size,
                                    sha256=coverage.sha(path / name)) for name in names}}
    (path / "manifest.json").write_text(json.dumps(manifest))
    return coverage.sha(path / "manifest.json")


def test_pinned_manifest_and_all_member_bytes_required(tmp_path):
    digest = tiny_bundle(tmp_path)
    assert len(coverage.read_bundle(tmp_path, digest)) == 11
    with pytest.raises(ValueError, match="manifest fingerprint"):
        coverage.read_bundle(tmp_path)
    member = tmp_path / "run-2/raw.jsonl"
    member.write_bytes(b"changed")
    with pytest.raises(ValueError, match="member changed"):
        coverage.read_bundle(tmp_path, digest)


def test_symlink_member_refused(tmp_path):
    digest = tiny_bundle(tmp_path)
    member = tmp_path / "run-1/raw.jsonl"
    member.unlink()
    member.symlink_to(tmp_path / "run-2/raw.jsonl")
    with pytest.raises(ValueError, match="invalid baseline member"):
        coverage.read_bundle(tmp_path, digest)
