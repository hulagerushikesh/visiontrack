"""Owner-local RQ5 preflight must never turn metadata into an accuracy claim."""

import json
from dataclasses import asdict
from pathlib import Path

import pytest

from experiments.reentry_capture_ledger import CaptureEvent, IndependentReview
from experiments.reentry_capture_manifest import SCENARIOS, CaptureManifest, PlannedTake
from experiments.reentry_pilot_preflight import (
    load_ledger,
    load_manifest,
    main,
    parse_event,
    parse_manifest,
    summarize,
)


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
        _event(split, label)
        for split in ("development", "test")
        for label in ("novel", "return")
    )
    ledger_path = tmp_path / "ledger.jsonl"
    ledger_path.write_text(
        "".join(json.dumps(asdict(event)) + "\n" for event in events), encoding="utf-8"
    )

    assert main(
        [
            "--manifest",
            str(manifest_path),
            "--ledger",
            str(ledger_path),
            "--expected-fingerprint",
            manifest.fingerprint,
        ]
    ) == 0
    output = capsys.readouterr().out
    result = json.loads(output)
    assert result["counts"]["events"] == 4
    assert result["counts"]["return"] == 2
    assert result["research_gate"] == "metadata_only_review_required"
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

    assert main(
        [
            "--manifest",
            str(plan),
            "--ledger",
            str(ledger),
            "--expected-fingerprint",
            fingerprint,
        ]
    ) == 0
    output = capsys.readouterr().out
    assert json.loads(output)["counts"]["events"] == 4
    assert "EXAMPLE-DEV-GROUP" not in output


def test_duplicate_json_key_is_rejected_without_echoing_private_values(tmp_path, capsys) -> None:
    path = tmp_path / "plan.json"
    path.write_text('{"study_id":"private-value","study_id":"other"}', encoding="utf-8")

    with pytest.raises(SystemExit):
        main(["--manifest", str(path)])
    error = capsys.readouterr().err
    assert "invalid manifest JSON" in error
    assert "private-value" not in error
