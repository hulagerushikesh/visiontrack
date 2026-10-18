"""Owner-local RQ5 preflight must never turn metadata into an accuracy claim."""

import json
from dataclasses import asdict, replace
from pathlib import Path

import pytest

from experiments.reentry_capture_ledger import (
    CaptureEvent,
    IndependentReview,
    validate_capture_ledger,
)
from experiments.reentry_capture_manifest import SCENARIOS, CaptureManifest, PlannedTake
from experiments.reentry_pilot_preflight import (
    load_inventory,
    load_ledger,
    load_manifest,
    main,
    parse_event,
    parse_inventory,
    parse_manifest,
    summarize,
)
from experiments.reentry_take_inventory import validate_take_inventory


def _manifest() -> CaptureManifest:
    return CaptureManifest(
        study_id="synthetic-example",
        frozen_on="2026-10-15",
        camera_setup="one fixed camera",
        scene_exit_rule="fully outside frame boundary",
        frame_rate=30,
        width=1280,
        height=720,
        short_absence_seconds=5,
        long_absence_seconds=20,
        gallery_ttl_seconds=60,
        expired_return_seconds=90,
        gallery_capacity=100,
        retention_days=7,
        rights_review_ref="private-rights-process",
        consent_process_ref="private-consent-process",
        withdrawal_process_ref="private-withdrawal-process",
        storage_plan_ref="private-storage-plan",
        permitted_scene_changes=("none",),
        planned_takes=tuple(PlannedTake("development", scenario, 1) for scenario in SCENARIOS)
        + (PlannedTake("test", "novel", 1),),
    )


def _event(split: str, label: str) -> CaptureEvent:
    group = f"private-{split}-{label}"
    return CaptureEvent(
        event_id=f"private-event-{split}-{label}",
        recording_id=f"private-recording-{split}",
        session_id=f"private-session-{split}",
        participant_group=group,
        session_person_code=f"private-code-{label}",
        split=split,
        opportunity_frame=30 if label == "novel" else 80,
        reviews=(IndependentReview("a", label), IndependentReview("b", label)),
        last_visible_before_exit_frame=10 if label == "return" else None,
        first_out_of_scene_frame=11 if label == "return" else None,
    )


def test_private_cli_freezes_plan_and_prints_no_identifiers(tmp_path, capsys) -> None:
    manifest = _manifest()
    path = tmp_path / "plan.json"
    path.write_text(json.dumps(asdict(manifest)), encoding="utf-8")

    assert main(["--manifest", str(path)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["phase"] == "plan_preflight"
    assert result["manifest_sha256"] == manifest.fingerprint
    assert result["rights_and_consent"] == "not_verified_by_software"
    assert result["identity_accuracy"] == "not_evaluated"
    assert "synthetic-example" not in json.dumps(result)


def test_private_cli_checks_frozen_ledger_and_only_returns_aggregates(tmp_path, capsys) -> None:
    manifest = _manifest()
    manifest_path = tmp_path / "plan.json"
    manifest_path.write_text(json.dumps(asdict(manifest)), encoding="utf-8")
    events = tuple(
        _event(split, label) for split in ("development", "test") for label in ("novel", "return")
    )
    ledger_path = tmp_path / "ledger.jsonl"
    ledger_path.write_text(
        "".join(json.dumps(asdict(event)) + "\n" for event in events), encoding="utf-8"
    )

    assert (
        main(
            [
                "--manifest",
                str(manifest_path),
                "--ledger",
                str(ledger_path),
                "--expected-fingerprint",
                manifest.fingerprint,
            ]
        )
        == 0
    )
    output = capsys.readouterr().out
    result = json.loads(output)
    assert result["counts"]["events"] == 4
    assert result["counts"]["return"] == 2
    assert result["research_gate"] == "metadata_incomplete"
    assert result["take_coverage"] == "not_checked"
    assert result["identity_accuracy"] == "not_evaluated"
    for event in events:
        assert event.event_id not in output
        assert event.participant_group not in output


def test_fingerprint_and_ledger_split_leakage_fail_closed(tmp_path, capsys) -> None:
    manifest_path = tmp_path / "plan.json"
    manifest_path.write_text(json.dumps(asdict(_manifest())), encoding="utf-8")
    ledger_path = tmp_path / "ledger.jsonl"
    events = (_event("development", "novel"), _event("test", "novel"))
    rows = [asdict(event) for event in events]
    rows[1]["participant_group"] = rows[0]["participant_group"]
    ledger_path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")

    with pytest.raises(SystemExit):
        main(["--manifest", str(manifest_path), "--ledger", str(ledger_path)])
    assert "requires --expected-fingerprint" in capsys.readouterr().err
    with pytest.raises(SystemExit):
        main(["--manifest", str(manifest_path), "--expected-fingerprint", "0" * 64])
    assert "differs from the recorded" in capsys.readouterr().err
    with pytest.raises(ValueError, match="consistency check failed"):
        load_ledger(ledger_path)


def test_strict_input_rejects_unknown_fields_bool_numbers_and_invalid_reviews() -> None:
    plan = json.loads(json.dumps(asdict(_manifest())))
    plan["gallery_capacity"] = True
    with pytest.raises(ValueError, match="must be an integer"):
        parse_manifest(plan)
    plan = json.loads(json.dumps(asdict(_manifest())))
    plan["unregistered_setting"] = "unsafe"
    with pytest.raises(ValueError, match="unknown fields"):
        parse_manifest(plan)
    event = json.loads(json.dumps(asdict(_event("development", "return"))))
    event["reviews"][1]["reviewer_code"] = "a"
    with pytest.raises(ValueError, match="distinct reviewer"):
        parse_event(event)


def test_empty_or_unresolved_ledger_never_becomes_a_real_study() -> None:
    empty = summarize(_manifest(), ())
    assert empty["research_gate"] == "metadata_incomplete"
    assert empty["identity_accuracy"] == "not_evaluated"


def test_checked_in_examples_are_synthetic_and_runnable(capsys) -> None:
    root = Path(__file__).resolve().parents[1]
    plan = root / "experiments/examples/reentry_pilot_manifest.example.json"
    ledger = root / "experiments/examples/reentry_pilot_ledger.example.jsonl"
    fingerprint = load_manifest(plan).fingerprint

    assert (
        main(
            [
                "--manifest",
                str(plan),
                "--ledger",
                str(ledger),
                "--expected-fingerprint",
                fingerprint,
            ]
        )
        == 0
    )
    output = capsys.readouterr().out
    assert json.loads(output)["counts"]["events"] == 4
    assert "EXAMPLE-DEV-GROUP" not in output


def test_example_take_inventory_exposes_incomplete_coverage_without_private_ids(capsys) -> None:
    root = Path(__file__).resolve().parents[1]
    plan = root / "experiments/examples/reentry_pilot_manifest.example.json"
    ledger = root / "experiments/examples/reentry_pilot_ledger.example.jsonl"
    inventory = root / "experiments/examples/reentry_pilot_inventory.example.json"
    fingerprint = load_manifest(plan).fingerprint

    assert (
        main(
            [
                "--manifest",
                str(plan),
                "--ledger",
                str(ledger),
                "--inventory",
                str(inventory),
                "--expected-fingerprint",
                fingerprint,
            ]
        )
        == 0
    )
    output = capsys.readouterr().out
    result = json.loads(output)
    assert result["take_coverage"] == {
        "planned": 9,
        "recorded": 4,
        "missing": 5,
        "excluded": 0,
        "linked_events": 4,
        "reset_controls": 0,
    }
    assert result["research_gate"] == "metadata_incomplete"
    assert result["identity_accuracy"] == "not_evaluated"
    assert "EXAMPLE-DEV-NOVEL-TAKE" not in output
    assert "EXAMPLE-DEV-RECORDING" not in output


def test_take_inventory_rejects_missing_duplicate_or_mislinked_slots() -> None:
    root = Path(__file__).resolve().parents[1]
    plan = load_manifest(root / "experiments/examples/reentry_pilot_manifest.example.json")
    ledger = load_ledger(root / "experiments/examples/reentry_pilot_ledger.example.jsonl")
    raw = json.loads(
        (root / "experiments/examples/reentry_pilot_inventory.example.json").read_text()
    )
    inventory = parse_inventory(raw)
    assert validate_take_inventory(plan, inventory, ledger).missing == 5

    incomplete = json.loads(json.dumps(raw))
    incomplete["takes"].pop()
    with pytest.raises(ValueError, match="each planned slot"):
        validate_take_inventory(plan, parse_inventory(incomplete), ledger)

    duplicated = json.loads(json.dumps(raw))
    duplicated["takes"][1]["scenario"] = "novel"
    with pytest.raises(ValueError, match="each planned slot"):
        validate_take_inventory(plan, parse_inventory(duplicated), ledger)

    wrong_event = json.loads(json.dumps(raw))
    wrong_event["takes"][0]["event_id"] = "EXAMPLE-TEST-NOVEL"
    with pytest.raises(ValueError, match="does not match"):
        validate_take_inventory(plan, parse_inventory(wrong_event), ledger)

    wrong_hash = json.loads(json.dumps(raw))
    wrong_hash["manifest_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="frozen manifest"):
        validate_take_inventory(plan, parse_inventory(wrong_hash), ledger)

    duplicate_id = json.loads(json.dumps(raw))
    duplicate_id["takes"][1]["take_id"] = duplicate_id["takes"][0]["take_id"]
    with pytest.raises(ValueError, match="duplicate take_id"):
        validate_take_inventory(plan, parse_inventory(duplicate_id), ledger)

    crossed_recording = json.loads(json.dumps(raw))
    crossed_recording["takes"][7]["recording_id"] = "EXAMPLE-DEV-RECORDING"
    with pytest.raises(ValueError, match="recording crosses"):
        validate_take_inventory(plan, parse_inventory(crossed_recording), ledger)


def test_take_inventory_rejects_invalid_states_and_unlinked_events(tmp_path, capsys) -> None:
    root = Path(__file__).resolve().parents[1]
    plan = load_manifest(root / "experiments/examples/reentry_pilot_manifest.example.json")
    ledger = load_ledger(root / "experiments/examples/reentry_pilot_ledger.example.jsonl")
    raw = json.loads(
        (root / "experiments/examples/reentry_pilot_inventory.example.json").read_text()
    )
    invalid = json.loads(json.dumps(raw))
    invalid["takes"][2]["status"] = "excluded"
    with pytest.raises(ValueError, match="exclusion code"):
        parse_inventory(invalid)
    invalid = json.loads(json.dumps(raw))
    invalid["takes"][2]["slot"] = True
    with pytest.raises(ValueError, match="must be an integer"):
        parse_inventory(invalid)
    invalid = json.loads(json.dumps(raw))
    invalid["takes"][2]["unexpected"] = "private-value"
    with pytest.raises(ValueError, match="unknown fields"):
        parse_inventory(invalid)
    excluded = json.loads(json.dumps(raw))
    excluded["takes"][2]["status"] = "excluded"
    excluded["takes"][2]["exclusion_code"] = "technical"
    assert validate_take_inventory(plan, parse_inventory(excluded), ledger).excluded == 1
    with pytest.raises(ValueError, match="missing or duplicated"):
        validate_take_inventory(plan, parse_inventory(raw), ledger[:-1])
    extra = replace(ledger[0], event_id="EXAMPLE-EXTRA", opportunity_frame=100)
    with pytest.raises(ValueError, match="not linked"):
        validate_take_inventory(plan, parse_inventory(raw), ledger + (extra,))

    path = tmp_path / "inventory.json"
    path.write_text('{"manifest_sha256":"private","manifest_sha256":"other"}')
    with pytest.raises(ValueError, match="invalid take inventory JSON"):
        load_inventory(path)
    with pytest.raises(SystemExit):
        main(
            [
                "--manifest",
                str(root / "experiments/examples/reentry_pilot_manifest.example.json"),
                "--inventory",
                str(path),
            ]
        )
    assert "requires --ledger" in capsys.readouterr().err


def test_complete_declared_take_coverage_still_needs_human_review() -> None:
    root = Path(__file__).resolve().parents[1]
    plan = load_manifest(root / "experiments/examples/reentry_pilot_manifest.example.json")
    ledger = list(load_ledger(root / "experiments/examples/reentry_pilot_ledger.example.jsonl"))
    raw = json.loads(
        (root / "experiments/examples/reentry_pilot_inventory.example.json").read_text()
    )
    for index in range(2, 7):
        take = raw["takes"][index]
        take["status"] = "recorded"
        take["recording_id"] = "EXAMPLE-DEV-RECORDING"
        take["session_id"] = "EXAMPLE-DEV-SESSION"
        scenario = take["scenario"]
        if scenario == "session_reset":
            continue
        take["event_id"] = f"EXAMPLE-{scenario}"
        label = (
            "return"
            if scenario in ("long_return", "expired_return")
            else "occlusion_control"
            if scenario == "occlusion_control"
            else "novel"
        )
        template = ledger[1] if label == "return" else ledger[0]
        ledger.append(
            replace(
                template,
                event_id=take["event_id"],
                participant_group=f"EXAMPLE-GROUP-{scenario}",
                session_person_code=f"EXAMPLE-PERSON-{scenario}",
                opportunity_frame=120 + index,
                reviews=(IndependentReview("a", label), IndependentReview("b", label)),
            )
        )
    events = tuple(ledger)
    validate_capture_ledger(events)
    result = summarize(plan, events, parse_inventory(raw))
    assert result["take_coverage"]["missing"] == 0
    assert result["take_coverage"]["recorded"] == 9
    assert result["take_coverage"]["reset_controls"] == 1
    assert result["research_gate"] == "metadata_only_review_required"
    assert result["rights_and_consent"] == "not_verified_by_software"
    assert result["visual_truth"] == "not_verified_by_software"
    assert result["identity_accuracy"] == "not_evaluated"


def test_duplicate_json_key_is_rejected_without_echoing_private_values(tmp_path, capsys) -> None:
    path = tmp_path / "plan.json"
    path.write_text('{"study_id":"private-value","study_id":"other"}', encoding="utf-8")

    with pytest.raises(SystemExit):
        main(["--manifest", str(path)])
    error = capsys.readouterr().err
    assert "invalid manifest JSON" in error
    assert "private-value" not in error
