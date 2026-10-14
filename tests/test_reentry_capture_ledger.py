"""The RQ5 local metadata gate must not promote ambiguous or leaked events."""

from dataclasses import replace

import pytest

from experiments.reentry_capture_ledger import (
    CaptureEvent,
    IndependentReview,
    validate_capture_ledger,
)


def _event(
    event_id: str = "e1",
    *,
    label: str = "novel",
    split: str = "development",
    group: str = "random-group-a",
) -> CaptureEvent:
    return CaptureEvent(
        event_id=event_id,
        recording_id=f"recording-{split}",
        session_id=f"session-{split}",
        participant_group=group,
        session_person_code="p1",
        split=split,
        opportunity_frame=30,
        reviews=(IndependentReview("reviewer-a", label), IndependentReview("reviewer-b", label)),
        last_visible_before_exit_frame=10 if label == "return" else None,
        first_out_of_scene_frame=11 if label == "return" else None,
    )


def test_counts_verified_events_without_scoring_accuracy() -> None:
    result = validate_capture_ledger(
        [_event(), _event("e2", label="return", split="test", group="random-group-b")]
    )
    assert result.events == 2
    assert (result.novel, result.returns, result.indeterminate) == (1, 1, 0)
    assert (result.development_events, result.test_events) == (1, 1)


def test_disagreement_is_indeterminate_until_reasoned_adjudication() -> None:
    disputed = replace(
        _event(),
        reviews=(
            IndependentReview("reviewer-a", "novel"),
            IndependentReview("reviewer-b", "return"),
        ),
    )
    assert validate_capture_ledger([disputed]).indeterminate == 1
    with pytest.raises(ValueError, match="requires a valid label and reason"):
        replace(disputed, adjudicated_label="novel")
    assert validate_capture_ledger(
        [
            replace(
                disputed,
                adjudicated_label="novel",
                adjudication_reason="reviewed scene boundary",
            )
        ]
    ).novel == 1


def test_return_requires_observable_ordered_exit_boundary() -> None:
    with pytest.raises(ValueError, match="requires an observable exit"):
        replace(
            _event(),
            reviews=(IndependentReview("a", "return"), IndependentReview("b", "return")),
        )
    with pytest.raises(ValueError, match="in order"):
        replace(_event(label="return"), first_out_of_scene_frame=30)


def test_one_reviewer_and_override_fail_closed() -> None:
    with pytest.raises(ValueError, match="two distinct"):
        replace(
            _event(),
            reviews=(IndependentReview("a", "novel"), IndependentReview("a", "novel")),
        )
    with pytest.raises(ValueError, match="must not be overridden"):
        replace(_event(), adjudicated_label="return")


def test_duplicate_events_and_cross_split_identity_leakage_fail() -> None:
    event = _event()
    with pytest.raises(ValueError, match="duplicate event_id"):
        validate_capture_ledger([event, event])
    with pytest.raises(ValueError, match="participant split"):
        validate_capture_ledger([event, _event("e2", split="test")])


def test_session_code_and_recording_cannot_change_meaning() -> None:
    event = _event()
    with pytest.raises(ValueError, match="session person code"):
        validate_capture_ledger(
            [event, replace(event, event_id="e2", participant_group="other", opportunity_frame=31)]
        )
    with pytest.raises(ValueError, match="session participant group"):
        validate_capture_ledger(
            [event, replace(event, event_id="e2", session_person_code="p2", opportunity_frame=31)]
        )
    with pytest.raises(ValueError, match="recording split"):
        validate_capture_ledger(
            [event, replace(event, event_id="e2", session_id="another", split="test")]
        )


def test_same_participant_frame_is_not_counted_twice() -> None:
    event = _event()
    with pytest.raises(ValueError, match="duplicate participant opportunity"):
        validate_capture_ledger([event, replace(event, event_id="e2")])


def test_empty_ledger_is_not_a_result() -> None:
    result = validate_capture_ledger([])
    assert result.events == result.returns == result.test_events == 0
