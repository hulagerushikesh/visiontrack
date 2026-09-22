"""Python and browser decision records share exact canonical fixture vectors."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from visiontrack.lab import DecisionRecord, canonical_json

FIXTURE_PATH = Path(__file__).parent / "fixtures/lab_decision_conformance.json"
FIXTURE = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_decision_conformance_fixture_covers_both_outcomes_and_unicode() -> None:
    assert FIXTURE["schema_version"] == 1
    assert {vector["values"]["status"] for vector in FIXTURE["vectors"]} == {
        "accepted",
        "rejected_all",
    }
    assert any("पहचान" in vector["values"]["rationale"] for vector in FIXTURE["vectors"])
    assert {vector["values"]["decided_at"][-1] for vector in FIXTURE["vectors"]} == {"Z", "0"}


@pytest.mark.parametrize("vector", FIXTURE["vectors"], ids=lambda vector: vector["name"])
def test_python_decision_contract_matches_shared_browser_vector(vector: dict) -> None:
    decision = DecisionRecord.create(**vector["values"])

    assert decision.decision_id == vector["decision_id"]
    assert canonical_json(decision.to_dict()) == vector["canonical_json"]
    assert DecisionRecord.from_json(vector["canonical_json"]) == decision
