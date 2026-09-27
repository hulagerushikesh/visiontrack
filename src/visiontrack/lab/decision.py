"""Auditable human decisions over fully verified Reliability Lab reports."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .contracts import DecisionRecord, canonical_json
from .report import build_report_model
from .storage import _write_decision_record

MAX_DECISION_BYTES = 64 * 1024


@dataclass(frozen=True, slots=True)
class DecisionImportPlan:
    """Read-only preview of one external decision import."""

    source_path: Path
    destination_path: Path
    decision: DecisionRecord
    already_stored: bool


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


def _read_external_decision(path: Path) -> tuple[DecisionRecord, bytes]:
    if path.name != "decision.json":
        raise ValueError("external decision file must be named decision.json")
    if path.is_symlink() or not path.is_file():
        raise ValueError("external decision.json must be an existing local file, not a symlink")
    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise ValueError("cannot read external decision.json") from exc
    if not payload or len(payload) > MAX_DECISION_BYTES:
        raise ValueError(f"external decision.json must be 1-{MAX_DECISION_BYTES} bytes")
    try:
        decision = DecisionRecord.from_json(payload.decode("utf-8"))
    except UnicodeDecodeError as exc:
        raise ValueError("external decision.json must be UTF-8") from exc
    expected = (canonical_json(decision.to_dict()) + "\n").encode("utf-8")
    if payload != expected:
        raise ValueError("external decision.json must use canonical downloaded file bytes")
    return decision, payload


def plan_decision_import(
    bundle: str | Path, decision_file: str | Path
) -> DecisionImportPlan:
    """Fully validate one external decision and its destination without writing."""
    bundle_path = Path(bundle)
    source_path = Path(decision_file)
    decision, payload = _read_external_decision(source_path)
    report = _verified_report(bundle_path)
    _verify_decision(decision, report)

    destination = bundle_path / "decision.json"
    already_stored = False
    if destination.exists() or destination.is_symlink():
        if destination.is_symlink() or not destination.is_file():
            raise FileExistsError(f"refusing to overwrite conflicting file: {destination}")
        try:
            stored = destination.read_bytes()
        except OSError as exc:
            raise ValueError("cannot read existing bundle decision.json") from exc
        if stored != payload:
            raise FileExistsError(f"refusing to overwrite conflicting file: {destination}")
        already_stored = True

    return DecisionImportPlan(
        source_path=source_path,
        destination_path=destination,
        decision=decision,
        already_stored=already_stored,
    )


def import_human_decision(bundle: str | Path, decision_file: str | Path) -> Path:
    """Import one fully verified external decision through immutable storage."""
    plan = plan_decision_import(bundle, decision_file)
    return _write_decision_record(Path(bundle), plan.decision)
