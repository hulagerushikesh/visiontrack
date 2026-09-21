"""Auditable human decisions over fully verified Reliability Lab reports."""

from __future__ import annotations

import json
from pathlib import Path

from .contracts import DecisionRecord, canonical_json
from .report import build_report_model
from .storage import _write_decision_record


def _verified_report(bundle: Path) -> dict:
    report_path = bundle / "report" / "report.json"
    if report_path.is_symlink() or not report_path.is_file():
        raise ValueError("a local report/report.json is required before recording a decision")
    try:
        payload = report_path.read_bytes()
        stored = json.loads(payload)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("stored report.json is not valid JSON") from exc
    expected = build_report_model(bundle)
    if not isinstance(stored, dict) or payload != (canonical_json(expected) + "\n").encode():
        raise ValueError("stored report.json does not match revalidated bundle evidence")
    if stored.get("decision") != {
        "status": "not_selected",
        "accepted_variant": None,
        "reason": "requires_human_acceptance_decision",
    }:
        raise ValueError("the source report does not preserve the unselected decision boundary")
    return expected


def _verify_decision(decision: DecisionRecord, report: dict) -> None:
    variants = {variant["name"] for variant in report["variants"]}
    decision.verify_lineage(
        experiment_id=report["experiment"]["experiment_id"],
        source_id=report["source"]["source_id"],
        comparison_id=report["comparison_id"],
        report_id=report["report_id"],
        variants=variants,
    )


def record_human_decision(
    bundle: str | Path,
    *,
    status: str,
    accepted_variant: str | None,
    rationale: str,
    author: str,
    decided_at: str,
) -> Path:
    """Validate and immutably record one explicit decision over a sealed report."""
    decision = plan_human_decision(
        bundle,
        status=status,
        accepted_variant=accepted_variant,
        rationale=rationale,
        author=author,
        decided_at=decided_at,
    )
    return _write_decision_record(Path(bundle), decision)


def plan_human_decision(
    bundle: str | Path,
    *,
    status: str,
    accepted_variant: str | None,
    rationale: str,
    author: str,
    decided_at: str,
) -> DecisionRecord:
    """Build a fully verified decision record without writing bundle state."""
    bundle_path = Path(bundle)
    report = _verified_report(bundle_path)
    decision = DecisionRecord.create(
        experiment_id=report["experiment"]["experiment_id"],
        source_id=report["source"]["source_id"],
        comparison_id=report["comparison_id"],
        report_id=report["report_id"],
        status=status,
        accepted_variant=accepted_variant,
        rationale=rationale,
        author=author,
        decided_at=decided_at,
    )
    _verify_decision(decision, report)
    return decision


def read_human_decision(bundle: str | Path) -> DecisionRecord:
    """Read one stored decision after revalidating its complete report lineage."""
    bundle_path = Path(bundle)
    path = bundle_path / "decision.json"
    if path.is_symlink() or not path.is_file():
        raise ValueError("decision.json is not an existing local file")
    try:
        decision = DecisionRecord.from_json(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError("cannot read decision.json") from exc
    report = _verified_report(bundle_path)
    _verify_decision(decision, report)
    return decision
