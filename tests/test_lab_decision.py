"""Human Lab decisions remain explicit, immutable, and evidence-linked."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from test_lab_report import make_report_bundle

from visiontrack.cli import main as cli_main
from visiontrack.lab import (
    DecisionRecord,
    canonical_json,
    generate_local_report,
    plan_human_decision,
    read_human_decision,
    record_human_decision,
    sha256_json,
)

NOW = "2026-09-21T08:30:00Z"


def decision_values(**changes) -> dict:
    values = {
        "experiment_id": "1" * 64,
        "source_id": "2" * 64,
        "comparison_id": "3" * 64,
        "report_id": "4" * 64,
        "status": "accepted",
        "accepted_variant": "baseline",
        "rationale": "The verified baseline satisfies the registered acceptance threshold.",
        "author": "local-reviewer",
        "decided_at": NOW,
    }
    values.update(changes)
    return values


def sealed_report_bundle(tmp_path: Path) -> Path:
    bundle = make_report_bundle(tmp_path)
    generate_local_report(bundle)
    return bundle


def test_decision_record_is_content_addressed_and_supports_both_outcomes() -> None:
    accepted = DecisionRecord.create(**decision_values())
    content = accepted.to_dict()
    decision_id = content.pop("decision_id")

    assert decision_id == sha256_json(content)
    assert DecisionRecord.from_json(accepted.to_json()) == accepted

    rejected = DecisionRecord.create(
        **decision_values(
            status="rejected_all",
            accepted_variant=None,
            rationale="No verified variant meets the registered identity-switch limit.",
        )
    )
    assert rejected.status == "rejected_all"
    assert rejected.accepted_variant is None


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"status": "automatic"}, "status"),
        ({"accepted_variant": None}, "name a variant"),
        ({"status": "rejected_all"}, "must not name"),
        ({"rationale": " "}, "rationale"),
        ({"author": " reviewer "}, "author"),
        ({"decided_at": "2026-09-21"}, "UTC"),
    ],
)
def test_decision_record_rejects_ambiguous_or_incomplete_choices(changes, message) -> None:
    with pytest.raises(ValueError, match=message):
        DecisionRecord.create(**decision_values(**changes))


def test_record_and_read_decision_revalidate_complete_lineage(tmp_path: Path) -> None:
    bundle = sealed_report_bundle(tmp_path)
    report = json.loads((bundle / "report/report.json").read_text(encoding="utf-8"))

    path = record_human_decision(
        bundle,
        status="accepted",
        accepted_variant="baseline",
        rationale="The measured result and reviewed failure evidence meet the local criteria.",
        author="research-reviewer",
        decided_at=NOW,
    )
    decision = read_human_decision(bundle)

    assert path == bundle / "decision.json"
    assert path.read_bytes() == (canonical_json(decision.to_dict()) + "\n").encode()
    assert decision.report_id == report["report_id"]
    assert decision.comparison_id == report["comparison_id"]
    assert decision.experiment_id == report["experiment"]["experiment_id"]
    assert decision.source_id == report["source"]["source_id"]
    assert decision.accepted_variant == "baseline"
    assert record_human_decision(
        bundle,
        status="accepted",
        accepted_variant="baseline",
        rationale="The measured result and reviewed failure evidence meet the local criteria.",
        author="research-reviewer",
        decided_at=NOW,
    ) == path


def test_decision_plan_matches_written_record_without_mutating_bundle(tmp_path: Path) -> None:
    bundle = sealed_report_bundle(tmp_path)
    values = {
        "status": "accepted",
        "accepted_variant": "baseline",
        "rationale": "The verified evidence meets the registered local criteria.",
        "author": "research-reviewer",
        "decided_at": NOW,
    }

    preview = plan_human_decision(bundle, **values)

    assert preview.accepted_variant == "baseline"
    assert not (bundle / "decision.json").exists()
    path = record_human_decision(bundle, **values)
    assert DecisionRecord.from_json(path.read_text(encoding="utf-8")) == preview


def test_lab_decision_cli_previews_then_writes_exact_record(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle = sealed_report_bundle(tmp_path)
    arguments = [
        "lab-decision",
        str(bundle),
        "--status",
        "accepted",
        "--variant",
        "baseline",
        "--rationale",
        "The verified baseline meets the registered acceptance criteria.",
        "--author",
        "local-reviewer",
        "--decided-at",
        NOW,
    ]

    assert cli_main(arguments) == 0
    preview = capsys.readouterr()
    assert "Human decision preview" in preview.out
    assert "accepted variant: baseline" in preview.out
    assert "comparison:" in preview.out
    assert "report:" in preview.out
    assert "Preview only; nothing was written." in preview.out
    assert not (bundle / "decision.json").exists()

    assert cli_main([*arguments, "--write"]) == 0
    written = capsys.readouterr()
    decision = read_human_decision(bundle)
    assert "Recorded immutable human decision" in written.out
    assert decision.decision_id in written.out
    assert str(bundle / "decision.json") in written.out

    assert cli_main([*arguments, "--write"]) == 0
    capsys.readouterr()


def test_lab_decision_cli_rejects_ambiguous_or_conflicting_choices(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle = sealed_report_bundle(tmp_path)
    common = [
        "lab-decision",
        str(bundle),
        "--rationale",
        "No candidate meets the registered criteria.",
        "--author",
        "local-reviewer",
        "--decided-at",
        NOW,
    ]

    assert cli_main([*common, "--status", "accepted"]) == 2
    assert "must name a variant" in capsys.readouterr().err
    assert cli_main([*common, "--status", "rejected_all", "--variant", "baseline"]) == 2
    assert "must not name" in capsys.readouterr().err

    accepted = [*common, "--status", "accepted", "--variant", "baseline", "--write"]
    assert cli_main(accepted) == 0
    capsys.readouterr()
    assert cli_main([*common, "--status", "rejected_all", "--write"]) == 2
    assert "refusing to overwrite" in capsys.readouterr().err


def test_decision_rejects_unknown_variant_and_conflicting_second_choice(tmp_path: Path) -> None:
    bundle = sealed_report_bundle(tmp_path)
    with pytest.raises(ValueError, match="not a verified report variant"):
        record_human_decision(
            bundle,
            status="accepted",
            accepted_variant="invented",
            rationale="This variant does not exist.",
            author="reviewer",
            decided_at=NOW,
        )

    record_human_decision(
        bundle,
        status="accepted",
        accepted_variant="baseline",
        rationale="The verified evidence meets the local criteria.",
        author="reviewer",
        decided_at=NOW,
    )
    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        record_human_decision(
            bundle,
            status="rejected_all",
            accepted_variant=None,
            rationale="A later conflicting choice must not replace the audit record.",
            author="reviewer",
            decided_at=NOW,
        )


def test_decision_reader_rejects_tampering_and_changed_upstream_evidence(tmp_path: Path) -> None:
    tampered = sealed_report_bundle(tmp_path / "decision")
    record_human_decision(
        tampered,
        status="accepted",
        accepted_variant="baseline",
        rationale="The verified evidence meets the local criteria.",
        author="reviewer",
        decided_at=NOW,
    )
    value = json.loads((tampered / "decision.json").read_text(encoding="utf-8"))
    value["rationale"] = "Changed after signing."
    (tampered / "decision.json").write_text(canonical_json(value) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="decision_id"):
        read_human_decision(tampered)

    changed_report = sealed_report_bundle(tmp_path / "report")
    record_human_decision(
        changed_report,
        status="rejected_all",
        accepted_variant=None,
        rationale="No variant meets the local acceptance criteria.",
        author="reviewer",
        decided_at=NOW,
    )
    report_path = changed_report / "report/report.json"
    report_path.write_text(report_path.read_text(encoding="utf-8") + " ", encoding="utf-8")
    with pytest.raises(ValueError, match="does not match revalidated"):
        read_human_decision(changed_report)
