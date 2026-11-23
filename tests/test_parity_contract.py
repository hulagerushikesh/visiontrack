"""Executable, dataset-free Python authority for tracker parity v1."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from visiontrack.cli import main as cli_main
from visiontrack.parity_contract import (
    CONTRACT_ID,
    assert_contract,
    canonical_json,
    execute_contract,
    fixture_sha256,
    load_contract,
    validate_contract,
)

FIXTURE = Path(__file__).parent / "fixtures/tracker_parity_v1.json"
DIGEST = Path(__file__).parent / "fixtures/tracker_parity_v1.sha256"


def recorded_digest() -> str:
    digest, filename = DIGEST.read_text(encoding="utf-8").strip().split("  ")
    assert filename == FIXTURE.name
    return digest


def test_fixture_is_canonical_content_addressed_and_exact() -> None:
    payload = load_contract(FIXTURE, expected_sha256=recorded_digest())
    assert payload["contract_id"] == CONTRACT_ID
    assert fixture_sha256(canonical_json(payload)) == recorded_digest()
    assert_contract(payload)


def test_fixture_covers_lifecycle_recovery_classes_features_empty_frames_and_ties() -> None:
    payload = load_contract(FIXTURE)
    frames = payload["frames"]
    observations = execute_contract(payload)

    assert any(not frame["detections"] for frame in frames)
    detections = [detection for frame in frames for detection in frame["detections"]]
    assert any(0.1 <= detection["score"] < 0.5 for detection in detections)
    assert all(detection["feature"] is not None for detection in detections)
    assert {detection["class_id"] for detection in detections} == {0, 1}
    assert any(
        len(frame["detections"]) == 2
        and frame["detections"][0]["xyxy"] == frame["detections"][1]["xyxy"]
        and frame["detections"][0]["score"] == frame["detections"][1]["score"]
        for frame in frames
    )
    assert {item["frame_index"] for item in observations}.isdisjoint({0, 3, 4, 5, 6, 9})


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda value: value.update(extra=True), "unknown contract"),
        (lambda value: value.update(contract_id="v2"), "contract_id"),
        (lambda value: value["config"].update(use_gmc=True), "unsupported config"),
        (lambda value: value["frames"][1].update(frame_index=4), "contiguous"),
        (lambda value: value["frames"][0]["detections"][0].update(score=float("nan")), "finite"),
        (lambda value: value["frames"][0]["detections"][0].update(xyxy=[3, 0, 2, 1]), "x2"),
        (lambda value: value["frames"][1]["detections"][0].update(feature=[1, 0, 0]), "width"),
    ],
)
def test_validator_rejects_contract_drift(mutation, message: str) -> None:
    value = copy.deepcopy(load_contract(FIXTURE))
    mutation(value)
    with pytest.raises(ValueError, match=message):
        validate_contract(value)


def test_digest_mismatch_and_noncanonical_bytes_are_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        load_contract(FIXTURE, expected_sha256="0" * 64)

    noncanonical = tmp_path / "fixture.json"
    noncanonical.write_text(FIXTURE.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="not canonical"):
        load_contract(noncanonical)


GATE_OFF_FIXTURE = Path(__file__).parent / "fixtures/tracker_parity_v1_gate_off.json"
GATE_OFF_DIGEST = Path(__file__).parent / "fixtures/tracker_parity_v1_gate_off.sha256"


def recorded_gate_off_digest() -> str:
    digest, filename = GATE_OFF_DIGEST.read_text(encoding="utf-8").strip().split("  ")
    assert filename == GATE_OFF_FIXTURE.name
    return digest


def test_gate_off_fixture_is_canonical_content_addressed_and_exact() -> None:
    payload = load_contract(GATE_OFF_FIXTURE, expected_sha256=recorded_gate_off_digest())
    assert payload["contract_id"] == CONTRACT_ID
    assert payload["config"]["use_mahalanobis_gating"] is False
    assert fixture_sha256(canonical_json(payload)) == recorded_gate_off_digest()
    assert_contract(payload)


def test_gate_off_fixture_differs_only_in_gate_and_tentative_threshold() -> None:
    gate_on = load_contract(FIXTURE)["config"]
    gate_off = load_contract(GATE_OFF_FIXTURE)["config"]
    changed = {key for key in gate_on if gate_on[key] != gate_off[key]}
    assert set(gate_on) == set(gate_off)
    assert changed == {"use_mahalanobis_gating", "n_init"}


def test_gate_off_fixture_discriminates_the_gate_switch() -> None:
    """The same frames with the gate on must give a different track ID.

    Frame 1 widens the tentative box: IoU 0.5 passes, but the aspect change puts
    the squared Mahalanobis distance near 24.5, far above the 9.4877 threshold.
    Gate off keeps the tentative track (ID 1), so the later stationary track is
    ID 2. Gate on drops it and spawns ID 2 from the wide box, so the later track
    is ID 3. Emitted boxes stay stationary and therefore exact on every backend.
    """
    payload = load_contract(GATE_OFF_FIXTURE)
    assert {item["track_id"] for item in payload["expected_observations"]} == {2}

    gated = copy.deepcopy(payload)
    gated["config"]["use_mahalanobis_gating"] = True
    gated_ids = {item["track_id"] for item in execute_contract(gated)}
    assert gated_ids == {3}


def test_public_cli_verifies_gate_off_fixture(capsys) -> None:
    assert (
        cli_main(["parity-contract", str(GATE_OFF_FIXTURE), "--digest", str(GATE_OFF_DIGEST)])
        == 0
    )
    output = capsys.readouterr().out
    assert recorded_gate_off_digest() in output
    assert "observations: 3" in output
    assert "parity: exact; reset: deterministic" in output


def test_public_cli_verifies_fixture_digest_exact_output_and_reset(capsys) -> None:
    assert cli_main(["parity-contract", str(FIXTURE), "--digest", str(DIGEST)]) == 0
    output = capsys.readouterr().out
    assert CONTRACT_ID in output
    assert recorded_digest() in output
    assert "observations: 7" in output
    assert "parity: exact; reset: deterministic" in output
