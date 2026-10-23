"""Hand-worked event diagrams and file doubles, not new tracker outcomes."""

import ast
import copy
import json
from pathlib import Path

import pytest

from experiments import box_gate_trace_audit as audit


def example(*, gate=True, distance=10.0, overlap=0.6, class_bad=False, stage=None):
    stage = stage or audit.STAGES[0]
    active = gate and stage != audit.STAGES[1]
    threshold = 0.5 if stage == audit.STAGES[1] else 0.3
    maximum = 1.0 - threshold
    bad = overlap < threshold or class_bad or (active and distance > 9.4877)
    cost = maximum + 1.0 if bad else 1.0 - overlap
    event = dict(
        frame=135, before=dict(stage=stage, gate_requested=stage != audit.STAGES[1],
                              iou_threshold=threshold, tracks=[dict(track_id=7)],
                              detection_ordinals=[0]),
        matrices=dict(ious=[[overlap]], class_mismatch=[[class_bad]], cost=[[cost]],
                      gating_d2=[[distance]] if active else None),
        gate_threshold=9.4877 if active else None, max_cost=maximum,
        matches=[] if bad else [[0, 0]], unmatched_tracks=[0] if bad else [],
        unmatched_detections=[0] if bad else [],
    )
    build = dict(forbidden=[[bad]], cost=[[cost]], max_cost=maximum)
    assignment = dict(proposed_rows=[0], proposed_columns=[0])
    return event, build, assignment


def test_gate_only_veto_is_not_confused_with_other_forbidden_pairs():
    event, build, assignment = example()
    result = audit.association(event, build, assignment, audit.STAGES[0], True)
    assert result == [dict(frame=135, stage=audit.STAGES[0], track_id=7,
                           detection_ordinal=0, iou=0.6, gating_d2=10.0, threshold=9.4877)]
    for kwargs in (dict(overlap=0.1), dict(class_bad=True), dict(gate=False),
                   dict(stage=audit.STAGES[1])):
        event, build, assignment = example(**kwargs)
        assert audit.association(event, build, assignment, event["before"]["stage"],
                                 kwargs.get("gate", True)) == []


@pytest.mark.parametrize("overlap,distance", [(0.3, 9.4877), (0.6, 0.0), (1.0, 9.4877)])
def test_inclusive_gate_boundary(overlap, distance):
    event, build, assignment = example(overlap=overlap, distance=distance)
    assert event["matches"] == [[0, 0]]
    assert audit.association(event, build, assignment, audit.STAGES[0], True) == []


@pytest.mark.parametrize("change", ["mask", "cost", "proposal", "accept", "unmatched",
                                     "threshold", "stage", "matrix", "class_type", "missing"])
def test_recorded_arithmetic_forgery_refused(change):
    event, build, assignment = example()
    if change == "mask":
        build["forbidden"] = [[False]]
    elif change == "cost":
        event["matrices"]["cost"][0][0] = 0.4
    elif change == "proposal":
        assignment["proposed_columns"] = [1]
    elif change == "accept":
        event["matches"] = [[0, 0]]
    elif change == "unmatched":
        event["unmatched_tracks"] = []
    elif change == "threshold":
        event["gate_threshold"] = 9.0
    elif change == "stage":
        event["before"]["stage"] = audit.STAGES[2]
    elif change == "matrix":
        event["matrices"]["gating_d2"] = [[float("inf")]]
    elif change == "class_type":
        event["matrices"]["class_mismatch"] = [[0]]
    else:
        assignment = None
    with pytest.raises(ValueError):
        audit.association(event, build, assignment, audit.STAGES[0], True)


def empty_diagram():
    events = [dict(frame=0, kind="frame_start", tracks=[], detections=[])]
    for stage in audit.STAGES:
        events.append(dict(frame=0, kind="association", before=dict(
            stage=stage, gate_requested=stage != audit.STAGES[1],
            iou_threshold=0.5 if stage == audit.STAGES[1] else 0.3,
            tracks=[], detection_ordinals=[]), matrices=dict(
                ious=None, class_mismatch=None, cost=None, gating_d2=None),
            matches=[], unmatched_tracks=[], unmatched_detections=[],
            gate_threshold=None, max_cost=None))
    events.append(dict(frame=0, kind="frame_end", tracks=[], public_output=[]))
    saved = dict(output=[], config=dict(use_mahalanobis_gating=True))
    diagnostic = dict(format="visiontrack.box-gate-internal-trace/v1", public_output=[],
                      settings=saved["config"], exact_public_output_parity=True,
                      selected_frames=[0], expected_output_sha256=audit.sha(b"[]"),
                      actual_output_sha256=audit.sha(b"[]"),
                      provenance_verified=False, interpretation_allowed=False,
                      validation_evidence=False, events=events)
    return diagnostic, saved


def test_empty_event_diagram_has_three_stages():
    diagnostic, saved = empty_diagram()
    assert audit.inspect_trace(diagnostic, saved, [0]) == dict(
        selected_frames=1, associations=3, gate_only_forbidden_candidate_pairs=[])


@pytest.mark.parametrize("change", ["frame_end", "stage", "public", "flag", "hash", "event"])
def test_trace_diagram_forgery_refused(change):
    diagnostic, saved = empty_diagram()
    if change == "frame_end":
        diagnostic["events"].pop()
    elif change == "stage":
        diagnostic["events"].pop(1)
    elif change == "public":
        diagnostic["events"][-1]["public_output"] = [dict(invented=True)]
    elif change == "flag":
        diagnostic["interpretation_allowed"] = True
    elif change == "hash":
        diagnostic["actual_output_sha256"] = "f" * 64
    else:
        diagnostic["events"][1]["kind"] = "new_solver"
    with pytest.raises(ValueError):
        audit.inspect_trace(diagnostic, saved, [0])


@pytest.mark.parametrize("raw", [b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":1e999}'])
def test_strict_json(raw):
    with pytest.raises(ValueError):
        audit.decode(raw)


def test_trace_read_set_refuses_changes_and_symlinks(tmp_path):
    path = tmp_path / "data.json"
    path.write_bytes(b"{}")
    files = audit.TraceFiles()
    assert files.load(path) == {}
    path.write_bytes(b'{"changed":true}')
    with pytest.raises(ValueError, match="changed"):
        files.unchanged()
    link = tmp_path / "link"
    link.symlink_to(path)
    with pytest.raises(ValueError, match="regular"):
        files.raw(link)


def test_bounded_read(tmp_path, monkeypatch):
    path = tmp_path / "large.json"
    path.write_bytes(b"{}")
    monkeypatch.setattr(audit, "MAX_BYTES", 1)
    with pytest.raises(ValueError, match="oversized"):
        audit.TraceFiles().load(path)


def test_fixed_selection_and_budget():
    frames = audit.frames_for([127.29480328576642, 149.5])
    assert set(range(126, 130)) <= set(frames)
    assert set(range(133, 168)) <= set(frames)
    assert set(range(208, 243)) <= set(frames)
    for times in ([True], [float("inf")], [300], list(range(300))):
        with pytest.raises(ValueError):
            audit.frames_for(times)


def test_auditor_has_no_tracking_generator_or_scorer_import():
    tree = ast.parse(Path(audit.__file__).read_text())
    imports = [n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
    assert not any(name and any(token in name for token in
                   ("runner", "scoring", "scene", "execution", "trace_replay", "visiontrack"))
                   for name in imports)


def test_input_diagrams_are_not_mutated():
    event, build, assignment = example()
    original = copy.deepcopy((event, build, assignment))
    audit.association(event, build, assignment, audit.STAGES[0], True)
    assert (event, build, assignment) == original
    assert json.dumps(event, allow_nan=False)
