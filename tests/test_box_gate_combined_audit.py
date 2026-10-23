"""Hand-worked tables and artifact doubles; never execute an experiment.

Arithmetic helper coverage remains in test_box_gate_audit. Record-plumbing tests
stub that helper explicitly; they are not synthetic or held-out measurements.
"""

import ast
import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from experiments import box_gate_combined_audit as audit
from experiments.box_gate_decision import ENDPOINTS, evaluate_rules

ROOT = Path(__file__).resolve().parents[1]


def registration():
    return tuple(
        json.loads((ROOT / "experiments" / name).read_bytes())
        for name in (
            "box_gate_protocol_v1.json",
            "traffic_protocol_v1.json",
        )
    )


def values():
    return {
        k: None if k.endswith(("mean_frames", "mean_world", "mean_distance_world")) else 0
        for k in ENDPOINTS
    }


@pytest.fixture
def table():
    spec, parent = registration()
    result = []
    for split in audit.SPLITS:
        for scenario, seed, condition in audit.grid(spec, parent, split):
            endpoints = {v: values() for v in audit.VARIANTS}
            if condition in spec["evaluation"]["error_conditions"]:
                objects = len(spec["scenarios"][scenario])
                endpoints["baseline"]["tracking.id_switches"] = 4 * objects
                endpoints["gate_off"]["tracking.id_switches"] = 3 * objects
            result.append(
                dict(
                    split=split,
                    scenario=scenario,
                    seed=seed,
                    condition=condition,
                    endpoints=endpoints,
                )
            )
    return result


@pytest.mark.parametrize(
    "change,verdict",
    [
        ("none", "pass"),
        ("safety", "failure"),
        ("no_effect", "no_effect"),
        ("secondary_only", "failure"),
        ("inadequate", "inconclusive"),
        ("missing_dev", "inconclusive"),
        ("missing_heldout", "inconclusive"),
        ("quarter_boundary_below", "failure"),
        ("half_boundary", "pass"),
        ("half_boundary_below", "inconclusive"),
        ("one_improved_heldout", "failure"),
    ],
)
def test_separate_rule_implementation_matches_hand_worked_priority(table, change, verdict):
    spec, parent = registration()
    if change in ("safety", "inadequate"):
        table[0]["endpoints"]["gate_off"]["tracking.false_positive_rows"] = 1
    if change in ("no_effect", "secondary_only"):
        for entry in table:
            entry["endpoints"]["gate_off"] = copy.deepcopy(entry["endpoints"]["baseline"])
        if change == "secondary_only":
            table[0]["endpoints"]["gate_off"]["crossing.box_centre.matched_x_abs_mean_world"] = 0.1
    if change == "inadequate":
        for entry in table:
            for variant in entry["endpoints"].values():
                variant["tracking.id_switches"] = 0
    if change.startswith("missing_"):
        missing = "development" if change == "missing_dev" else "heldout"
        table = [e for e in table if e["split"] != missing]
    if change.startswith("half_boundary"):
        for entry in table:
            for v in entry["endpoints"].values():
                v["tracking.id_switches"] = 0
            if entry["condition"] == "box_error_only":
                count = len(spec["scenarios"][entry["scenario"]])
                if change.endswith("below") and entry["seed"] in (2001, 4001):
                    count -= 1
                entry["endpoints"]["baseline"]["tracking.id_switches"] = count
    if change == "quarter_boundary_below":
        for entry in table:
            if entry["condition"] == "box_error_only" and entry["seed"] in (2001, 4001):
                entry["endpoints"]["gate_off"]["tracking.id_switches"] += 1
    if change == "one_improved_heldout":
        for entry in table:
            if entry["split"] == "heldout" and entry["scenario"] != "gate_test_solo":
                entry["endpoints"]["gate_off"] = copy.deepcopy(entry["endpoints"]["baseline"])
    before = copy.deepcopy(table)
    checked = audit.decision(table, spec, parent)
    assert checked["classification"] == verdict
    production = evaluate_rules(table)
    assert checked == {k: production[k] for k in ("classification", "splits")}
    assert before == table


@pytest.mark.parametrize("bad", [True, 1.0, None, -1, float("nan"), float("inf"), "1"])
def test_invalid_integer_refused_not_rounded_or_zeroed(table, bad):
    table[0]["endpoints"]["baseline"]["tracking.id_switches"] = bad
    with pytest.raises(ValueError):
        audit.decision(table, *registration())


@pytest.mark.parametrize(
    "change", ["duplicate", "unknown", "bool_seed", "missing_endpoint", "variant"]
)
def test_malformed_entries_refuse(table, change):
    if change == "duplicate":
        table[-1] = copy.deepcopy(table[0])
    elif change == "unknown":
        table[0]["scenario"] = "unregistered"
    elif change == "bool_seed":
        table[0]["seed"] = True
    elif change == "missing_endpoint":
        table[0]["endpoints"]["baseline"].pop("tracking.id_switches")
    else:
        table[0]["endpoints"].pop("gate_off")
    with pytest.raises(ValueError):
        audit.decision(table, *registration())


@pytest.mark.parametrize(
    "data", [b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":Infinity}', b'{"a":1e999}']
)
def test_strict_json(data):
    with pytest.raises(ValueError):
        audit.decode(data)


def test_read_set_refuses_mutation_symlink_oversize_and_coverage(tmp_path, monkeypatch):
    path = tmp_path / "item.json"
    path.write_text('{"x":null}')
    evidence = audit.Evidence()
    assert evidence.load(path) == {"x": None}
    evidence.unchanged()
    path.write_text('{"x":0}')
    with pytest.raises(ValueError, match="changed"):
        evidence.unchanged()
    link = tmp_path / "link"
    link.symlink_to(path)
    with pytest.raises(ValueError, match="regular"):
        audit.read(link)
    link.unlink()
    with pytest.raises(ValueError, match="coverage"):
        evidence.coverage(tmp_path, set())
    monkeypatch.setattr(audit, "MAX_BYTES", 1)
    with pytest.raises(ValueError, match="oversized"):
        audit.read(path)


def test_reviewed_index_must_match_historical_git_bytes(tmp_path, monkeypatch):
    path = tmp_path / "experiments" / "box_gate_heldout_v1_evidence.json"
    path.parent.mkdir()
    path.write_text('{"value":1}')
    monkeypatch.setattr(audit, "git", lambda *a: b'{"value":1}')
    assert audit.Evidence().index(tmp_path, "heldout") == {"value": 1}
    path.write_text('{"value":2}')
    with pytest.raises(ValueError, match="snapshot"):
        audit.Evidence().index(tmp_path, "heldout")


@pytest.fixture
def bundle_double(tmp_path):
    """365 tiny artifact files; hashes test structure, not any measured result."""
    spec, parent = registration()
    paths = {"plan.json", "summary.json", "summary.md", "attempts.jsonl"}
    for scenario, seed, condition in audit.grid(spec, parent, "heldout"):
        paths.update(
            f"pairs/{scenario}/{seed}/{condition}/{v}.json" for v in (*audit.VARIANTS, "pair")
        )
    plan = dict(
        registration=spec,
        protocol_id=spec["protocol_id"],
        protocol_hashes={},
        source={"replay_source": {"actual_revision": "fixture", "worktree_dirty": False}},
        baseline_source={},
        environment={},
        heldout_tracking_authorized=True,
    )
    for name in paths:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(audit.canonical(plan) if name == "plan.json" else b"{}")
    manifest = {
        k: plan[k]
        for k in ("protocol_id", "protocol_hashes", "source", "baseline_source", "environment")
    }
    manifest.update(
        planned_pairs=120,
        attempted_pairs=120,
        successful_pairs=120,
        unattempted_pairs=0,
        status="complete",
        error=None,
        heldout_tracking_executed=True,
        complete_study_report=False,
        files_sha256={name: audit.sha((tmp_path / name).read_bytes()) for name in paths},
    )
    seal(manifest, "manifest_sha256")
    raw = audit.canonical(manifest)
    (tmp_path / "manifest.json").write_bytes(raw)
    index = dict(
        bundle_manifest_sha256=manifest["manifest_sha256"],
        artifact_sha256={"manifest.json": audit.sha(raw)},
        protocol_hashes={},
        source_revision="fixture",
        environment={},
    )
    return tmp_path, index, spec, parent


def test_complete_bundle_hash_coverage_double(bundle_double):
    path, index, spec, parent = bundle_double
    evidence = audit.Evidence()
    evidence.bundle(path, index, spec, parent, "heldout")
    assert len(evidence.hashes) == 365
    evidence.unchanged()


@pytest.mark.parametrize("change", ["modified", "missing", "extra", "symlink", "manifest", "index"])
def test_bundle_changes_refuse_before_arithmetic(bundle_double, change):
    path, index, spec, parent = bundle_double
    item = path / "summary.md"
    if change == "missing":
        item.unlink()
    elif change == "extra":
        (path / "extra.json").write_bytes(b"{}")
    elif change == "symlink":
        item.unlink()
        item.symlink_to(path / "summary.json")
    elif change == "index":
        index["source_revision"] = "different"
    elif change == "manifest":
        (path / "manifest.json").write_bytes(b"{}")
    else:
        item.write_bytes(b"changed")
    with pytest.raises((ValueError, KeyError)):
        audit.Evidence().bundle(path, index, spec, parent, "heldout")


def seal(value, key):
    value[key] = audit.sha(audit.canonical({k: v for k, v in value.items() if k != key}))


@pytest.fixture
def record_double(table, monkeypatch):
    """In-memory 120-pair plumbing fixture, NOT output from a tracker/scorer."""
    spec, parent = registration()
    selected = [e for e in table if e["split"] == "heldout"]
    data, inputs, ledger, hashes = {}, [], [], {}
    plan = dict(
        source={"replay_source": {}},
        baseline_source={},
        environment={},
        protocol_id=spec["protocol_id"],
        protocol_hashes={},
        inputs=inputs,
    )
    for entry in selected:
        selector = {k: entry[k] for k in ("scenario", "seed", "condition")}
        prefix = "pairs/{scenario}/{seed}/{condition}".format(**selector)
        inp = dict(
            **selector,
            split="heldout",
            object_ids=[o["object_id"] for o in spec["scenarios"][entry["scenario"]]],
            detections={},
        )
        seal(inp["detections"], "detection_stream_sha256")
        seal(inp, "input_sha256")
        inputs.append(inp)
        pair = dict(
            input=inp,
            source={},
            baseline_source={},
            environment={},
            protocol_id=plan["protocol_id"],
            protocol_hashes={},
            heldout_tracking_executed=True,
            complete_study_report=False,
            variants=[],
        )
        ledger.append(dict(event="start", **selector))
        for recipe in spec["variants"]:
            v = recipe["id"]
            settings = {**parent["tracker_config"], **recipe["config_patch"]}
            variant = dict(
                id=v,
                config=settings,
                config_sha256=audit.sha(audit.canonical(settings)),
                output=[],
                output_sha256=audit.sha(audit.canonical([])),
                replay=dict(
                    passes=3,
                    pass_order=["fresh", "reset", "independent_fresh"],
                    updates_per_pass=300,
                    reset_equal=True,
                    fresh_equal=True,
                    detection_receipts=[inp["detections"]] * 3,
                ),
            )
            scoring = dict(
                input=inp,
                source={},
                public_rows_sha256=variant["output_sha256"],
                protocol_id=plan["protocol_id"],
                protocol_hashes={},
                crossing={
                    a: {"rules": parent["crossing"]} for a in ("bottom_centre", "box_centre")
                },
                endpoints=entry["endpoints"][v],
            )
            seal(scoring, "scoring_sha256")
            variant["scoring"] = scoring
            pair["variants"].append(variant)
            name = f"{prefix}/{v}.json"
            data[name] = variant
            hashes[name] = "fixture digest"
            ledger.append(
                dict(
                    event="variant_retained",
                    **selector,
                    variant=v,
                    path=name,
                    sha256=hashes[name],
                    validated_pair=False,
                )
            )
        a, b = (entry["endpoints"][v] for v in audit.VARIANTS)
        pair["candidate_minus_baseline"] = {
            k: None if a[k] is None or b[k] is None else b[k] - a[k] for k in a
        }
        seal(pair, "record_sha256")
        name = f"{prefix}/pair.json"
        data[name] = pair
        hashes[name] = "pair fixture digest"
        ledger.append(dict(event="success", **selector, path=name, sha256=hashes[name]))
    scenarios = []
    for scenario in spec["splits"]["heldout"]["scenarios"]:
        grouped = {}
        seed_values = []
        for seed in spec["splits"]["heldout"]["seeds"]:
            conditions = {}
            for condition in [c["id"] for c in parent["conditions"]]:
                pair = data[f"pairs/{scenario}/{seed}/{condition}/pair.json"]
                conditions[condition] = dict(
                    absolute={v["id"]: v["scoring"]["endpoints"] for v in pair["variants"]},
                    candidate_minus_baseline=pair["candidate_minus_baseline"],
                )
            seed_values.append(dict(seed=seed, conditions=conditions))
        for condition in seed_values[0]["conditions"]:
            rows = [s["conditions"][condition] for s in seed_values]
            grouped[condition] = dict(
                absolute={
                    v: audit.descriptive([r["absolute"][v] for r in rows]) for v in audit.VARIANTS
                },
                candidate_minus_baseline=audit.descriptive(
                    [r["candidate_minus_baseline"] for r in rows]
                ),
            )
        scenarios.append(dict(scenario=scenario, seeds=seed_values, conditions=grouped))
    rules = dict(audit.decision(selected, spec, parent), invalid_evidence=None)
    seal(rules, "rules_sha256")
    data["summary.json"] = dict(scenarios=scenarios, numerical_rules=rules)

    class Memory:
        def load(self, path):
            return copy.deepcopy(data[str(path)])

        def bytes(self, path):
            assert str(path) == "attempts.jsonl"
            return b"\n".join(audit.canonical(e) for e in ledger)

    monkeypatch.setattr(audit, "reconstruct_endpoints", lambda v, *a: v["scoring"]["endpoints"])
    return Memory(), data, ledger, dict(files_sha256=hashes), plan, spec, parent


def test_record_plumbing_checks_all_pairs_without_mutation(record_double):
    memory, data, _, manifest, plan, spec, parent = record_double
    before = copy.deepcopy(data)
    result = audit.audit_records(memory, Path(), manifest, plan, spec, parent, "heldout")
    assert len(result) == 120
    assert data == before


@pytest.mark.parametrize(
    "change", ["ledger", "receipt", "setting", "contrast", "null_count", "margin", "variant_seal"]
)
def test_record_plumbing_refuses_resealed_contradictions(record_double, change):
    memory, data, ledger, manifest, plan, spec, parent = record_double
    key = "pairs/gate_test_solo/4001/control"
    pair = data[f"{key}/pair.json"]
    if change == "ledger":
        ledger[0]["event"] = "success"
    elif change == "contrast":
        pair["candidate_minus_baseline"]["tracking.false_positive_rows"] = 1
    elif change in ("null_count", "margin"):
        summary = data["summary.json"]
        if change == "null_count":
            summary["scenarios"][0]["conditions"]["control"]["absolute"]["baseline"][
                "crossing.bottom_centre.matched_time_abs_mean_frames"
            ]["undefined_seeds"] = 0
        else:
            summary["numerical_rules"]["splits"][1]["scenarios"][0]["absolute_reduction"] = 100
            seal(summary["numerical_rules"], "rules_sha256")
    else:
        variant = data[f"{key}/baseline.json"]
        if change == "receipt":
            variant["replay"]["detection_receipts"][0] = {"forged": True}
        elif change == "setting":
            variant["config"]["max_age"] = 100
            variant["config_sha256"] = audit.sha(audit.canonical(variant["config"]))
        else:
            variant["scoring"]["endpoints"]["tracking.id_switches"] = 99
        # Both copies agree: rejection must not depend on mere copy mismatch.
        pair["variants"][0] = variant
    seal(pair, "record_sha256")
    with pytest.raises(ValueError):
        audit.audit_records(memory, Path(), manifest, plan, spec, parent, "heldout")


def test_auditor_imports_no_tracker_generator_scorer_or_numpy():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; import experiments.box_gate_combined_audit; "
                "assert not any(n.startswith(('numpy', 'visiontrack')) for n in sys.modules); "
                "assert 'experiments.box_gate_decision' not in sys.modules"
            ),
        ],
        cwd=ROOT,
        capture_output=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr.decode()
    tree = ast.parse(Path(audit.__file__).read_text())
    modules = [n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
    assert {n for n in modules if n.startswith("experiments")} == {"experiments.box_gate_audit"}


def test_cli_missing_evidence_refuses_without_output(tmp_path):
    command = [
        sys.executable,
        "-m",
        "experiments.box_gate_combined_audit",
        "--development",
        str(tmp_path / "dev"),
        "--heldout",
        str(tmp_path / "held"),
        "--freeze",
        str(tmp_path / "freeze.json"),
        "--root",
        str(tmp_path),
    ]
    before = list(tmp_path.iterdir())
    result = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=10)
    assert result.returncode == 2 and result.stdout == b""
    assert b"Audit refused" in result.stderr
    assert list(tmp_path.iterdir()) == before


def test_optional_output_is_new_external_only_and_never_overwrites(tmp_path):
    protected = tmp_path / "input"
    protected.mkdir()
    with pytest.raises(ValueError, match="outside"):
        audit.write_output(protected / "audit.json", {}, [protected])
    path = tmp_path / "audit.json"
    digest = audit.write_output(path, {"classification": "failure"}, [protected])
    raw = path.read_bytes()
    assert digest == audit.sha(raw)
    with pytest.raises(ValueError, match="exists"):
        audit.write_output(path, {}, [protected])
    assert path.read_bytes() == raw
    link = tmp_path / "dangling.json"
    link.symlink_to(tmp_path / "missing")
    with pytest.raises(ValueError, match="exists"):
        audit.write_output(link, {}, [protected])
