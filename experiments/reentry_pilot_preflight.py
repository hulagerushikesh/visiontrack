"""Check an owner-private RQ5 pilot plan and ledger without opening media.

The populated JSON/JSONL files belong outside Git. This command validates
metadata and prints aggregate counts only; it cannot verify consent, rights,
visual truth, reviewer independence, or identity-restoration performance.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import MISSING, fields
from pathlib import Path
from typing import Any

from experiments.reentry_capture_ledger import (
    CaptureEvent,
    IndependentReview,
    validate_capture_ledger,
)
from experiments.reentry_capture_manifest import CaptureManifest, PlannedTake

MAX_MANIFEST_BYTES = 100_000
MAX_LEDGER_BYTES = 10_000_000
MAX_LEDGER_EVENTS = 20_000


def _no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _json_object(raw: str, label: str) -> dict[str, Any]:
    try:
        value = json.loads(raw, object_pairs_hook=_no_duplicate_keys)
    except (json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"invalid {label} JSON") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def _shape(value: dict[str, Any], cls: type, label: str) -> None:
    allowed = {field.name for field in fields(cls)}
    required = {field.name for field in fields(cls) if field.default is MISSING}
    if not required <= value.keys() or not value.keys() <= allowed:
        raise ValueError(f"{label} has missing or unknown fields")


def _string(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a string")
    return value


def _int(value: Any, label: str) -> int:
    if type(value) is not int:
        raise ValueError(f"{label} must be an integer")
    return value


def _optional_int(value: Any, label: str) -> int | None:
    return None if value is None else _int(value, label)


def _optional_string(value: Any, label: str) -> str | None:
    return None if value is None else _string(value, label)


def parse_manifest(value: dict[str, Any]) -> CaptureManifest:
    """Reject ambiguous JSON rather than silently changing a frozen plan."""
    _shape(value, CaptureManifest, "manifest")
    changes = value["permitted_scene_changes"]
    takes = value["planned_takes"]
    if not isinstance(changes, list) or not isinstance(takes, list):
        raise ValueError("manifest changes and takes must be arrays")
    parsed_takes = []
    for take in takes:
        if not isinstance(take, dict):
            raise ValueError("planned take must be an object")
        _shape(take, PlannedTake, "planned take")
        parsed_takes.append(
            PlannedTake(
                _string(take["split"], "take split"),
                _string(take["scenario"], "take scenario"),
                _int(take["count"], "take count"),
            )
        )
    strings = (
        "study_id",
        "frozen_on",
        "camera_setup",
        "scene_exit_rule",
        "rights_review_ref",
        "consent_process_ref",
        "withdrawal_process_ref",
        "storage_plan_ref",
    )
    integers = (
        "frame_rate",
        "width",
        "height",
        "short_absence_seconds",
        "long_absence_seconds",
        "gallery_ttl_seconds",
        "expired_return_seconds",
        "gallery_capacity",
        "retention_days",
    )
    return CaptureManifest(
        **{name: _string(value[name], name) for name in strings},
        **{name: _int(value[name], name) for name in integers},
        permitted_scene_changes=tuple(_string(change, "scene change") for change in changes),
        planned_takes=tuple(parsed_takes),
    )


def parse_event(value: dict[str, Any]) -> CaptureEvent:
    _shape(value, CaptureEvent, "ledger event")
    reviews = value["reviews"]
    if not isinstance(reviews, list) or len(reviews) != 2:
        raise ValueError("ledger event needs two reviews")
    parsed_reviews = []
    for review in reviews:
        if not isinstance(review, dict):
            raise ValueError("review must be an object")
        _shape(review, IndependentReview, "review")
        parsed_reviews.append(
            IndependentReview(
                _string(review["reviewer_code"], "reviewer code"),
                _string(review["label"], "review label"),
            )
        )
    strings = (
        "event_id",
        "recording_id",
        "session_id",
        "participant_group",
        "session_person_code",
        "split",
    )
    return CaptureEvent(
        **{name: _string(value[name], name) for name in strings},
        opportunity_frame=_int(value["opportunity_frame"], "opportunity frame"),
        reviews=tuple(parsed_reviews),
        last_visible_before_exit_frame=_optional_int(
            value.get("last_visible_before_exit_frame"), "last visible frame"
        ),
        first_out_of_scene_frame=_optional_int(
            value.get("first_out_of_scene_frame"), "first out-of-scene frame"
        ),
        adjudicated_label=_optional_string(value.get("adjudicated_label"), "final label"),
        adjudication_reason=_optional_string(value.get("adjudication_reason"), "reason"),
    )


def load_manifest(path: Path) -> CaptureManifest:
    if path.stat().st_size > MAX_MANIFEST_BYTES:
        raise ValueError("manifest exceeds the size limit")
    return parse_manifest(_json_object(path.read_text(encoding="utf-8"), "manifest"))


def load_ledger(path: Path) -> tuple[CaptureEvent, ...]:
    if path.stat().st_size > MAX_LEDGER_BYTES:
        raise ValueError("ledger exceeds the size limit")
    events: list[CaptureEvent] = []
    with path.open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, start=1):
            if number > MAX_LEDGER_EVENTS:
                raise ValueError("ledger exceeds the event limit")
            try:
                events.append(parse_event(_json_object(line, "ledger row")))
            except ValueError as exc:
                raise ValueError(f"invalid ledger row {number}") from exc
    try:
        validate_capture_ledger(events)
    except ValueError as exc:
        raise ValueError("ledger consistency check failed") from exc
    return tuple(events)


def summarize(manifest: CaptureManifest, events: tuple[CaptureEvent, ...] | None) -> dict:
    """Return only plan identity and aggregate metadata; never participant keys."""
    result: dict[str, Any] = {
        "manifest_sha256": manifest.fingerprint,
        "metadata_validation": "passed",
        "rights_and_consent": "not_verified_by_software",
        "visual_truth": "not_verified_by_software",
        "identity_accuracy": "not_evaluated",
    }
    if events is None:
        result["phase"] = "plan_preflight"
        return result
    summary = validate_capture_ledger(events)
    result["phase"] = "ledger_preflight"
    result["counts"] = {
        "events": summary.events,
        "development": summary.development_events,
        "test": summary.test_events,
        "novel": summary.novel,
        "return": summary.returns,
        "occlusion_control": summary.occlusion_controls,
        "indeterminate": summary.indeterminate,
    }
    result["coverage"] = {
        split: {
            label: sum(event.split == split and event.resolved_label == label for event in events)
            for label in ("novel", "return", "occlusion_control")
        }
        for split in ("development", "test")
    }
    result["research_gate"] = (
        "metadata_incomplete"
        if not events
        or summary.indeterminate
        or any(
            result["coverage"][split][label] == 0
            for split in ("development", "test")
            for label in ("novel", "return")
        )
        else "metadata_only_review_required"
    )
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True, help="Owner-private plan JSON")
    parser.add_argument("--ledger", type=Path, help="Optional owner-private event JSONL")
    parser.add_argument(
        "--expected-fingerprint", help="Pre-recording SHA-256, required with --ledger"
    )
    args = parser.parse_args(argv)
    if args.ledger is not None and args.expected_fingerprint is None:
        parser.error("--ledger requires --expected-fingerprint from the frozen plan")
    try:
        manifest = load_manifest(args.manifest)
        if args.expected_fingerprint is not None and (
            args.expected_fingerprint != manifest.fingerprint
        ):
            raise ValueError("manifest differs from the recorded pre-capture fingerprint")
        events = load_ledger(args.ledger) if args.ledger is not None else None
    except (OSError, UnicodeError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps(summarize(manifest, events), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
