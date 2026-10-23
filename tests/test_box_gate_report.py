"""Report/export fixtures use explicit doubles, never comparative tracker runs."""

import copy
import hashlib
import json

import pytest

from experiments import box_gate_report as report
from experiments import box_gate_runner as runner
from experiments.box_gate_protocol import load_registration
from experiments.box_gate_scene import generate_inputs
from experiments.traffic_protocol import load_frozen_protocol
from experiments.traffic_report import _sha
from experiments.traffic_runner import _json_bytes
from visiontrack.tracking.config import TrackerConfig


@pytest.fixture(autouse=True)
def no_actual_trackers(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("report tests must not execute actual trackers or old scenes")

    monkeypatch.setattr("visiontrack.tracking.tracker.ByteTracker.__init__", forbidden)
    monkeypatch.setattr("experiments.traffic_scene.generate_scene", forbidden)


class EmptyDouble:
    """No associations: supplies empty rows, not an experimental tracker."""

    def __init__(self, settings):
        self.cfg = TrackerConfig(**settings)
        self.frame_index = -1

    def update(self, detections):
        self.frame_index += 1
        return []

    def reset(self):
        self.frame_index = -1


@pytest.fixture(scope="module")
def pair_template():
    with pytest.MonkeyPatch.context() as patch:
        snapshot = runner._snapshot()
        snapshot["worktree_dirty"] = False  # Explicit provenance double, not a clean-repo claim.
        patch.setattr(runner, "_snapshot", lambda: copy.deepcopy(snapshot))
        patch.setattr(runner, "_construct", EmptyDouble)
        return runner.run_development(scenario="gate_dev_solo", seed=2001, condition="control")


def seal(record):
    record.pop("record_sha256", None)
    record["record_sha256"] = _sha(record)


def scoring_seal(scoring):
    scoring.pop("scoring_sha256", None)
    scoring["scoring_sha256"] = _sha(scoring)


def validate(pair):
    scene = generate_inputs(
        split="development", scenario="gate_dev_solo", seed=2001, condition="control"
    )
    report._validate_pair(
        pair, scene, {"replay_source": pair["source"]}, pair["baseline_source"], pair["environment"]
    )


def test_one_double_pair_is_fully_rescored_and_not_mutated(pair_template):
    before = copy.deepcopy(pair_template)
    validate(pair_template)
    assert pair_template == before
    parent, _ = load_frozen_protocol()
    assert pair_template["variants"][0]["config"] == parent["tracker_config"]


@pytest.mark.parametrize(
    "fault",
    [
        "record_hash",
        "input",
        "protocol",
        "dirty",
        "baseline",
        "environment",
        "heldout",
        "complete",
        "variant_order",
        "config",
        "bool_config",
        "config_hash",
        "output_hash",
        "reset",
        "bool_updates",
        "pass_order",
        "receipt",
        "contrast",
        "scoring_hash",
        "fabricated_endpoint",
        "fabricated_diagnostics",
    ],
)
def test_resealed_forgeries_do_not_establish_replay_evidence(pair_template, fault):
    pair = copy.deepcopy(pair_template)
    variant = pair["variants"][1]
    if fault == "record_hash":
        pair["record_sha256"] = "0" * 64
    elif fault == "input":
        pair["input"]["seed"] = 2002
    elif fault == "protocol":
        pair["protocol_id"] = "old"
    elif fault == "dirty":
        pair["source"]["worktree_dirty"] = True
    elif fault == "baseline":
        pair["baseline_source"]["revision"] = "0" * 40
    elif fault == "environment":
        pair["environment"]["numpy"] = "invented"
    elif fault == "heldout":
        pair["heldout_tracking_executed"] = True
    elif fault == "complete":
        pair["complete_study_report"] = True
    elif fault == "variant_order":
        pair["variants"].reverse()
    elif fault == "config":
        variant["config"]["max_age"] += 1
        variant["config_sha256"] = _sha(variant["config"])
    elif fault == "bool_config":
        variant["config"]["use_mahalanobis_gating"] = 0
    elif fault == "config_hash":
        variant["config_sha256"] = "0" * 64
    elif fault == "output_hash":
        variant["output_sha256"] = "0" * 64
    elif fault == "reset":
        variant["replay"]["reset_equal"] = False
    elif fault == "bool_updates":
        variant["replay"]["updates_per_pass"] = 300.0
    elif fault == "pass_order":
        variant["replay"]["pass_order"].reverse()
    elif fault == "receipt":
        variant["replay"]["detection_receipts"][1]["score"] = 0.8
    elif fault == "contrast":
        pair["candidate_minus_baseline"]["tracking.id_switches"] = 1
    elif fault == "scoring_hash":
        variant["scoring"]["scoring_sha256"] = "0" * 64
    elif fault == "fabricated_endpoint":
        variant["scoring"]["endpoints"]["tracking.id_switches"] = 123
        scoring_seal(variant["scoring"])
    else:
        variant["scoring"]["diagnostics"]["overall"]["missed_object_frames"] -= 1
        scoring_seal(variant["scoring"])
    if fault != "record_hash":
        seal(pair)
    scene = generate_inputs(
        split="development", scenario="gate_dev_solo", seed=2001, condition="control"
    )
    with pytest.raises(ValueError):
        report._validate_pair(
            pair,
            scene,
            {"replay_source": pair_template["source"]},
            pair_template["baseline_source"],
            pair_template["environment"],
        )


@pytest.fixture
def grid(pair_template):
    """Full selector/input grid with hand-assembled records; no measured outcomes."""
    spec, _ = load_registration()
    parent, _ = load_frozen_protocol()
    records = []
    for scenario, seed, condition in report.cases(spec, parent, "development"):
        scene = generate_inputs(
            split="development", scenario=scenario, seed=seed, condition=condition
        )
        # Minimal structural double: provenance validation is replaced ONLY in
        # exporter-plumbing tests. Full real scorer-record checks are above.
        record = {
            "input": scene.manifest(),
            "variants": [
                {
                    "id": v["id"],
                    "scoring": {
                        "endpoints": copy.deepcopy(v["scoring"]["endpoints"]),
                    },
                }
                for v in pair_template["variants"]
            ],
            "candidate_minus_baseline": copy.deepcopy(pair_template["candidate_minus_baseline"]),
        }
        seal(record)
        records.append(record)
    return records, [r["input"] for r in records], spec, parent


def test_full_grid_summary_preserves_37_endpoints_nulls_and_per_seed_differences(grid):
    records, planned, spec, parent = grid
    summary = report._summarize(records, planned, spec, parent)
    assert summary["paired_cases"] == 120 and summary["variant_runs"] == 240
    assert summary["replay_passes"] == 720
    assert summary["complete_development_grid"]
    assert summary["complete_study_report"] is summary["heldout_tracking_executed"] is False
    assert summary["numerical_rules"]["classification"] == "inconclusive"
    for scenario in summary["scenarios"]:
        assert len(scenario["seeds"]) == 10
        for condition in scenario["conditions"].values():
            for values in [*condition["absolute"].values(), condition["candidate_minus_baseline"]]:
                assert len(values) == 37
                missing = values["crossing.bottom_centre.matched_time_abs_mean_frames"]
                assert missing == {
                    "mean": None,
                    "min": None,
                    "max": None,
                    "defined_seeds": 0,
                    "undefined_seeds": 10,
                }
            assert condition["candidate_minus_baseline"]["tracking.id_switches"]["mean"] == 0
    assert "inconclusive" in report._markdown(summary)
    assert "No held-out tracking" in report._markdown(summary)


@pytest.mark.parametrize(
    "fault", ["missing", "duplicate", "order", "plan", "world", "random", "ideal"]
)
def test_summary_rejects_incomplete_duplicate_unplanned_or_unpaired_inputs(grid, fault):
    records, planned, spec, parent = grid
    if fault == "missing":
        records.pop()
    elif fault == "duplicate":
        records[-1] = records[0]
    elif fault == "order":
        records.reverse()
    elif fault == "plan":
        planned = copy.deepcopy(planned)
        planned[0]["seed"] = 2002
    else:
        key = {"world": "world_truth", "random": "random_draws", "ideal": "ideal_truth"}[fault]
        # Preserve record-plan equality to reach the cross-condition pairing guard.
        records[2]["input"]["sha256"][key] = "0" * 64
    with pytest.raises(ValueError):
        report._summarize(records, planned, spec, parent)


@pytest.fixture
def export_double(monkeypatch, pair_template, grid):
    records, _, _, _ = grid
    by_key = {
        (r["input"]["scenario"], r["input"]["seed"], r["input"]["condition"]): r for r in records
    }
    source = {
        "replay_source": pair_template["source"],
        "harness_sha256": {"explicit_test_double": "0" * 64},
    }
    monkeypatch.setattr(report, "_snapshot", lambda: copy.deepcopy(source))
    calls = []

    def fake_run(*, scenario, seed, condition, variant_sink):
        calls.append((scenario, seed, condition))
        pair = copy.deepcopy(by_key[(scenario, seed, condition)])
        for variant in pair["variants"]:
            variant_sink(variant["id"], _json_bytes(variant))
        return pair

    monkeypatch.setattr(report, "_run_development", fake_run)
    monkeypatch.setattr(report, "_validate_pair", lambda *args: None)  # Tested separately above.
    return calls, fake_run


def read(path):
    return json.loads(path.read_text())


def test_exclusive_complete_export_hashes_ledger_and_all_records(tmp_path, export_double):
    calls, _ = export_double
    progress = []
    output = tmp_path / "new-bundle"
    manifest = report.export_development(
        output, progress=lambda n, total: progress.append((n, total))
    )
    assert manifest["status"] == "complete" and manifest["successful_pairs"] == 120
    assert manifest["attempted_pairs"] == 120 and manifest["unattempted_pairs"] == 0
    assert len(calls) == 120 and progress == [(n, 120) for n in range(1, 121)]
    files = manifest["files_sha256"]
    assert len(files) == 364  # 120 pair + 240 partial variant + plan/ledger/two summaries.
    assert set(files) == {str(p.relative_to(output)) for p in output.rglob("*") if p.is_file()} - {
        "manifest.json"
    }
    for name, digest in files.items():
        assert hashlib.sha256((output / name).read_bytes()).hexdigest() == digest
    payload = dict(manifest)
    assert payload.pop("manifest_sha256") == _sha(payload)
    ledger = [json.loads(line) for line in (output / "attempts.jsonl").read_text().splitlines()]
    assert len(ledger) == 480
    assert [e["event"] for e in ledger[:4]] == [
        "start",
        "variant_retained",
        "variant_retained",
        "success",
    ]
    assert read(output / "plan.json")["heldout_tracking_authorized"] is False
    assert read(output / "summary.json")["numerical_rules"]["classification"] == "inconclusive"
    with pytest.raises(FileExistsError):
        report.export_development(output)
    assert len(calls) == 120  # No rerun or overwritten files.


def test_candidate_failure_retains_baseline_and_stops_without_retry(
    tmp_path, export_double, monkeypatch
):
    calls, original = export_double

    def fail_second(**kwargs):
        def sink(name, data):
            if name == "gate_off":
                raise ValueError("candidate failed after baseline")
            kwargs["variant_sink"](name, data)

        return original(**{**kwargs, "variant_sink": sink})

    monkeypatch.setattr(report, "_run_development", fail_second)
    output = tmp_path / "failed"
    manifest = report.export_development(output)
    assert manifest["status"] == "failed" and manifest["successful_pairs"] == 0
    assert manifest["attempted_pairs"] == 1 and manifest["unattempted_pairs"] == 119
    assert len(calls) == 1
    assert len(list(output.rglob("baseline.json"))) == 1
    assert not list(output.rglob("gate_off.json")) and not (output / "summary.json").exists()
    ledger = [json.loads(line) for line in (output / "attempts.jsonl").read_text().splitlines()]
    assert [e["event"] for e in ledger] == ["start", "variant_retained", "failed"]


def test_invalid_pair_bytes_are_retained_but_not_counted_success(
    tmp_path, export_double, monkeypatch
):
    calls, _ = export_double

    def reject(*args):
        raise ValueError("scoring does not match rows")

    monkeypatch.setattr(report, "_validate_pair", reject)
    output = tmp_path / "invalid"
    manifest = report.export_development(output)
    assert manifest["status"] == "failed" and manifest["successful_pairs"] == 0
    assert len(calls) == 1 and len(list(output.rglob("pair.json"))) == 1
    assert len(manifest["files_sha256"]) == 5  # plan + ledger + two variants + invalid pair.


@pytest.mark.parametrize("when", ["pair", "end"])
def test_snapshot_drift_is_failure_and_retains_attempts(tmp_path, export_double, monkeypatch, when):
    calls, _ = export_double
    original = report._snapshot

    def drift():
        snapshot = original()
        if (when == "pair" and calls) or (when == "end" and len(calls) == 120):
            snapshot["harness_sha256"]["drift"] = "1" * 64
        return snapshot

    monkeypatch.setattr(report, "_snapshot", drift)
    result = report.export_development(tmp_path / "drift")
    assert result["status"] == "failed"
    assert len(calls) == (1 if when == "pair" else 120)


def test_inside_repo_and_arbitrary_split_rejected_before_execution(export_double):
    calls, _ = export_double
    with pytest.raises(ValueError, match="outside"):
        report.export_development(report.ROOT / "must-not-be-created-box-gate")
    with pytest.raises(TypeError):
        report.export_development(report.ROOT, split="heldout")
    assert not calls


def test_dirty_harness_refused_before_inputs_or_output(tmp_path, monkeypatch):
    monkeypatch.setattr(report, "replay_snapshot", lambda: {"worktree_dirty": True})

    def forbidden(*args, **kwargs):
        pytest.fail("dirty export must fail before generating inputs")

    monkeypatch.setattr(report, "generate_inputs", forbidden)
    with pytest.raises(ValueError, match="commit all"):
        report.export_development(tmp_path / "not-created")
    assert not (tmp_path / "not-created").exists()


def test_snapshot_binds_sources_tests_settings_and_locks_to_committed_bytes(tmp_path, monkeypatch):
    names = {
        "experiments/traffic_a.py",
        "experiments/box_gate_a.py",
        "tests/test_traffic_a.py",
        "tests/test_box_gate_a.py",
        *report.ARTIFACTS,
        report.LOCK,
        "pyproject.toml",
        "experiments/__init__.py",
        "experiments/traffic_protocol_v1.json",
        "experiments/traffic_protocol_v1.sha256",
        "docs/TRAFFIC_RELIABILITY_PROTOCOL.md",
    }
    for name in names:
        path = tmp_path / name
        path.parent.mkdir(exist_ok=True, parents=True)
        path.write_bytes(name.encode())
    replay = {
        "worktree_dirty": False,
        "actual_revision": "1" * 40,
        "experiment_sha256": {
            n: hashlib.sha256(n.encode()).hexdigest()
            for n in names
            if n.startswith("experiments/") and n.endswith(".py")
        },
    }
    monkeypatch.setattr(report, "ROOT", tmp_path)
    monkeypatch.setattr(report, "replay_snapshot", lambda: replay)
    shown = []

    def git(root, command, target):
        assert root == tmp_path and command == "show" and target.startswith("1" * 40 + ":")
        name = target.partition(":")[2]
        shown.append(name)
        return name.encode()

    monkeypatch.setattr(report, "_git", git)
    result = report._snapshot()
    assert set(result["harness_sha256"]) == set(shown) == names
    (tmp_path / "tests/test_box_gate_a.py").write_bytes(b"drift")
    with pytest.raises(ValueError, match="committed HEAD"):
        report._snapshot()


def test_real_adapter_sink_preserves_baseline_before_candidate_construction_fails(monkeypatch):
    retained = []

    def construct(settings):
        if not settings["use_mahalanobis_gating"]:
            raise ValueError("candidate construction failed")
        return EmptyDouble(settings)

    monkeypatch.setattr(runner, "_construct", construct)
    with pytest.raises(ValueError, match="candidate construction"):
        runner._run_development(
            scenario="gate_dev_solo",
            seed=2001,
            condition="control",
            variant_sink=lambda name, data: retained.append((name, data)),
        )
    assert len(retained) == 1 and retained[0][0] == "baseline"
    assert type(retained[0][1]) is bytes
    baseline = json.loads(retained[0][1])
    assert baseline["replay"]["passes"] == 3
    assert baseline["output"] == []


def test_adapter_sink_receives_bytes_without_mutating_completed_pair(monkeypatch):
    retained = []
    monkeypatch.setattr(runner, "_construct", EmptyDouble)

    def sink(name, data):
        assert type(data) is bytes
        payload = json.loads(data)
        retained.append(payload["id"])
        payload["config"].clear()  # Detached JSON cannot mutate the adapter.

    pair = runner._run_development(
        scenario="gate_dev_solo",
        seed=2001,
        condition="control",
        variant_sink=sink,
    )
    assert retained == ["baseline", "gate_off"]
    parent, _ = load_frozen_protocol()
    assert pair["variants"][0]["config"] == parent["tracker_config"]
    assert pair["variants"][1]["config"] == {
        **parent["tracker_config"], "use_mahalanobis_gating": False,
    }


def test_summary_failure_preserves_complete_ledger_and_failed_manifest(
    tmp_path,
    export_double,
    monkeypatch,
):
    calls, _ = export_double

    def fail(*args):
        raise ValueError("summary failure")

    monkeypatch.setattr(report, "_summarize", fail)
    output = tmp_path / "summary-failed"
    manifest = report.export_development(output)
    assert manifest["status"] == "failed" and manifest["successful_pairs"] == 120
    assert len(calls) == 120
    assert manifest["error"]["message"] == "summary failure"
    assert (output / "attempts.jsonl").exists()
    assert not (output / "summary.json").exists()


def test_modified_saved_file_prevents_complete_manifest(tmp_path, export_double):
    output = tmp_path / "modified-file"

    def tamper(n, total):
        if n == total:
            (output / "plan.json").write_bytes(b"modified")

    manifest = report.export_development(output, progress=tamper)
    assert manifest["status"] == "failed" and manifest["successful_pairs"] == 120
    assert manifest["error"]["message"] == "saved evidence changed before sealing bundle"
