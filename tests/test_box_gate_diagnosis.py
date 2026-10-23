"""Hand-worked symptom arithmetic and explicit record doubles, not measurements."""

import ast
import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from experiments import box_gate_diagnosis as diagnosis

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def example():
    parent = dict(
        frame_grid=dict(frames=4),
        diagnostics=dict(gt_match_iou=0.5),
        observation_error=dict(
            bottom_truncation=dict(start_frame=1, stop_frame_exclusive=2),
            top_truncation=dict(start_frame=3, stop_frame_exclusive=4),
        ),
    )
    error = {a: dict(distance=2.0) for a in ("bottom_centre", "box_centre")}
    # Frame 3 deliberately represents an eligible-but-unmatched saved label.
    # This double exercises categorization, not a claim about the real matcher.
    samples = [
        dict(
            frame=f,
            object_id=1,
            matched_track_id=12 if f == 2 else None,
            matched_track_error=copy.deepcopy(error) if f == 2 else None,
            id_switch=f == 2,
            phase=diagnosis.phase(f, parent),
        )
        for f in range(4)
    ]
    variant = dict(
        output=[dict(frame=f, track_id=10 + f, xyxy=[0, 0, 2, 2]) for f in (1, 2, 3)],
        scoring=dict(
            endpoints={
                "tracking.missed_object_frames": 3,
                "tracking.false_positive_rows": 2,
                "tracking.id_switches": 1,
            },
            diagnostics=dict(
                iou_threshold=0.5,
                samples=samples,
                failures=[
                    dict(
                        event_type="miss",
                        frame_index=f,
                        gt_id=1,
                        gt_box=[10, 10, 12, 12] if f == 1 else [0, 0, 2, 2],
                    )
                    for f in (0, 1, 3)
                ],
            ),
            crossing=dict(
                bottom_centre=dict(matches=[], summary=dict(matched_time_abs_mean_frames=None))
            ),
        ),
    )
    return variant, parent


def test_hand_worked_three_symptoms_and_phase_partition(example):
    variant, parent = example
    before = copy.deepcopy(variant)
    result = diagnosis.diagnose_variant(variant, [1], parent)
    assert variant == before
    assert [d["category"] for d in result["missed_reference_frames"]] == list(diagnosis.MISS_TYPES)
    assert [d["max_public_box_iou"] for d in result["missed_reference_frames"]] == [None, 0, 1]
    assert result["objects"] == [
        dict(
            object_id=1,
            matched_track_ids=[12],
            miss_frame_ranges_inclusive=[[0, 1], [3, 3]],
            id_switch_frames=[2],
        )
    ]
    totals = {k: sum(p[k] for p in result["by_phase"].values()) for k in diagnosis.COUNTS}
    assert totals == dict(
        reference_object_frames=4,
        misses=3,
        id_switches=1,
        false_positive_rows=2,
        no_public_output=1,
        all_public_boxes_below_iou=1,
        eligible_box_unmatched=1,
    )
    assert result["bottom_centre_crossing"]["summary"]["matched_time_abs_mean_frames"] is None


@pytest.mark.parametrize(
    "a,b,expected",
    [
        ([0, 0, 2, 2], [0, 0, 2, 2], 1),
        ([0, 0, 2, 2], [2, 0, 4, 2], 0),
        ([0, 0, 2, 2], [0, 0, 1, 2], 0.5),
    ],
)
def test_scalar_iou(a, b, expected):
    assert diagnosis.iou(a, b) == expected
    assert diagnosis.iou(b, a) == expected


@pytest.mark.parametrize(
    "bad",
    [[0, 0, 0, 1], [0, 0, 2], [0, False, 2, 2], [0, 0, float("nan"), 1], [0, 0, float("inf"), 1]],
)
def test_invalid_box_refused(bad):
    with pytest.raises(ValueError, match="box"):
        diagnosis.iou(bad, [0, 0, 1, 1])


def test_threshold_is_inclusive_and_overlap_ties_use_smaller_track_id(example):
    variant, parent = example
    variant["scoring"]["diagnostics"]["failures"][1]["gt_box"] = [0, 0, 1, 2]
    variant["output"].append(dict(frame=1, track_id=1, xyxy=[0, 0, 2, 2]))
    variant["scoring"]["endpoints"]["tracking.false_positive_rows"] += 1
    detail = diagnosis.diagnose_variant(variant, [1], parent)["missed_reference_frames"][1]
    assert detail["max_public_box_iou"] == 0.5
    assert detail["category"] == "eligible_box_unmatched"
    assert detail["best_overlap_track_id"] == 1


@pytest.mark.parametrize(
    "mutation",
    [
        "phase",
        "sample",
        "miss",
        "duplicate_miss",
        "duplicate_row",
        "correspondence",
        "endpoint",
        "threshold",
        "frame",
        "id",
    ],
)
def test_inconsistent_record_refused(example, mutation):
    variant, parent = example
    d = variant["scoring"]["diagnostics"]
    if mutation == "phase":
        d["samples"][0]["phase"] = "top_pulse_window"
    elif mutation == "sample":
        d["samples"].pop()
    elif mutation == "miss":
        d["failures"].pop()
    elif mutation == "duplicate_miss":
        d["failures"].append(d["failures"][0])
    elif mutation == "duplicate_row":
        variant["output"].append(variant["output"][0])
    elif mutation == "correspondence":
        d["samples"][2]["matched_track_id"] = 999
    elif mutation == "endpoint":
        variant["scoring"]["endpoints"]["tracking.false_positive_rows"] = 0
    elif mutation == "threshold":
        d["iou_threshold"] = 0.1
    elif mutation == "frame":
        variant["output"][0]["frame"] = True
    else:
        variant["output"][0]["track_id"] = False
    with pytest.raises(ValueError):
        diagnosis.diagnose_variant(variant, [1], parent)


def test_common_frame_localization_does_not_substitute_zero_or_compare_different_frames(example):
    a, _ = example
    b = copy.deepcopy(a)
    matched_error = b["scoring"]["diagnostics"]["samples"][2]["matched_track_error"]
    matched_error["bottom_centre"]["distance"] = 5
    result = diagnosis.common_localization(a, b)
    assert result["common_matched_object_frames"] == 1
    assert result["bottom_centre"]["candidate_minus_baseline"] == 3
    b["scoring"]["diagnostics"]["samples"][2]["matched_track_id"] = None
    result = diagnosis.common_localization(a, b)
    assert result["common_matched_object_frames"] == 0
    assert set(result["bottom_centre"].values()) == {None}


def test_intervals_keep_gaps():
    assert diagnosis.intervals([4, 0, 1, 6, 7]) == [[0, 1], [4, 4], [6, 7]]
    assert diagnosis.intervals([]) == []


def test_fixed_half_open_phase_boundaries():
    parent = json.loads((ROOT / "experiments/traffic_protocol_v1.json").read_bytes())
    assert [diagnosis.phase(f, parent) for f in (134, 135, 164, 165, 209, 210, 239, 240)] == [
        "outside_pulse_windows",
        "bottom_pulse_window",
        "bottom_pulse_window",
        "outside_pulse_windows",
        "outside_pulse_windows",
        "top_pulse_window",
        "top_pulse_window",
        "outside_pulse_windows",
    ]


def test_no_execution_or_heldout_entrypoint_imports():
    tree = ast.parse(Path(diagnosis.__file__).read_text())
    modules = [n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
    assert all(
        not any(
            term in (m or "")
            for term in (
                "visiontrack",
                "runner",
                "scoring",
                "scene",
                "holdout",
                "execution",
                "numpy",
            )
        )
        for m in modules
    )
    result = subprocess.run(
        [sys.executable, "-m", "experiments.box_gate_diagnosis", "--heldout", "not-opened"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 2
    assert "usage:" in result.stderr


def test_output_refuses_overwrite_symlink_and_evidence_directory(tmp_path):
    original = tmp_path / "audit.json"
    original.write_text("unchanged")
    link = tmp_path / "link.json"
    link.symlink_to(tmp_path / "missing.json")
    for path in (original, link, tmp_path / "inside.json"):
        with pytest.raises(ValueError):
            diagnosis.write_output(path, {}, [tmp_path])
    assert original.read_text() == "unchanged"


@pytest.mark.parametrize("fault", [None, "helper", "audit_hash", "audit_result", "changed"])
def test_development_only_wrapper_and_final_read_set_check(example, tmp_path, monkeypatch, fault):
    """Explicit plumbing double: not the real audit, bundle or experiment."""
    variant, parent = example
    bundle = tmp_path / "bundle"
    spec = dict(
        scenarios=dict(toy=[dict(object_id=1)]),
        splits=dict(development=dict(scenarios=["toy"], seeds=[2001])),
    )
    parent["conditions"] = [dict(id="control")]
    audit_bytes, helper_bytes = b"{}", b"helper"
    index = dict(
        protocol_hashes={},
        source_revision="double-not-an-execution",
        audit=dict(
            script="helper.py",
            script_sha256=diagnosis.sha(helper_bytes),
            output_sha256=diagnosis.sha(audit_bytes),
        ),
    )
    paths = {
        ROOT / "experiments/box_gate_protocol_v1.json": spec,
        ROOT / "experiments/traffic_protocol_v1.json": parent,
        bundle.parent / "audit.json": {},
        **{bundle / f"pairs/toy/2001/control/{v}.json": variant for v in ("baseline", "gate_off")},
    }
    called = []

    class ExplicitEvidenceDouble:
        def bytes(self, path):
            if path == Path(diagnosis.__file__).resolve():
                return b"script-double"
            if path == ROOT / "helper.py":
                return b"changed" if fault == "helper" else helper_bytes
            assert path == bundle.parent / "audit.json"
            return b"changed" if fault == "audit_hash" else audit_bytes

        def index(self, root, split):
            assert root == ROOT and split == "development"
            called.append("index")
            return index

        def load(self, path):
            assert path in paths, "unexpected evidence read (including held-out evidence)"
            return copy.deepcopy(paths[path])

        def bundle(self, path, idx, registry, protocol, split):
            assert split == "development" and path == bundle and idx == index
            assert registry == spec and protocol == parent
            called.append("bundle")
            return dict(manifest_sha256="double-manifest"), {}

        def unchanged(self):
            called.append("unchanged")
            if fault == "changed":
                raise ValueError("evidence changed")

    def audit_double(path, root):
        assert path == bundle and root == ROOT
        called.append("audit")
        return {"changed": True} if fault == "audit_result" else {}

    monkeypatch.setattr(diagnosis, "Evidence", ExplicitEvidenceDouble)
    monkeypatch.setattr(diagnosis, "development_audit", audit_double)
    if fault:
        with pytest.raises(ValueError):
            diagnosis.diagnose(bundle, ROOT)
    else:
        result = diagnosis.diagnose(bundle, ROOT)
        assert result["paired_cases"] == 1 and result["variant_records"] == 2
        assert result["new_tracker_runs"] == 0 and result["heldout_files_read"] is False
        assert result["internal_gate_cause_established"] is False
        assert result["production_change_authorized"] is False
        assert len(result["groups"]) == 2
        assert called == ["index", "bundle", "audit", "unchanged"]
