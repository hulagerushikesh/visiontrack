"""Keep the first identity-continuity metrics honest at every boundary."""

import pytest

from visiontrack.eval.selective_identity import (
    GroupedReentryDecision,
    ReentryDecision,
    grouped_reentry_bootstrap,
    score_reentry,
    wilson_upper_bound,
)


def test_reentry_outcomes_separate_wrong_restore_expiry_and_abstention() -> None:
    decisions = [
        ReentryDecision("correct", "a", ("a", "b"), "a"),
        ReentryDecision("wrong", "a", ("a", "b"), "b"),
        ReentryDecision("missed", "a", ("a", "b"), None),
        ReentryDecision("expired", "a", ("b",), None),
        ReentryDecision("expired_wrong", "a", ("b",), "b"),
        ReentryDecision("novel", None, ("a", "b"), None),
        ReentryDecision("novel_wrong", None, ("a", "b"), "a"),
    ]
    result = score_reentry(decisions)
    assert result.opportunities == 7
    assert result.eligible_returns == 3
    assert result.unavailable_returns == 2
    assert result.novel_arrivals == 2
    assert result.correct_restorations == 1
    assert result.false_restorations == 3
    assert result.false_restorations_of_novel == 1
    assert result.eligible_abstentions == 1
    assert result.unavailable_abstentions == 1
    assert result.novel_abstentions == 1
    assert result.restoration_coverage == pytest.approx(4 / 7)
    assert result.selective_risk == pytest.approx(3 / 4)
    assert result.eligible_return_recall == pytest.approx(1 / 3)
    assert result.novel_false_match_rate == pytest.approx(1 / 2)


def test_zero_decisions_do_not_claim_zero_risk() -> None:
    result = score_reentry([ReentryDecision("novel", None, (), None)])
    assert result.selective_risk is None
    assert result.eligible_return_recall is None
    assert result.novel_false_match_rate == 0
    assert score_reentry([]).restoration_coverage is None
    assert wilson_upper_bound(0, 0) is None


def test_zero_observed_errors_have_nonzero_uncertainty() -> None:
    assert 0 < wilson_upper_bound(0, 100) < 0.05
    assert wilson_upper_bound(100, 100) == 1
    with pytest.raises(ValueError):
        wilson_upper_bound(2, 1)


def test_invalid_candidates_or_duplicate_events_fail() -> None:
    with pytest.raises(ValueError, match="available candidate"):
        ReentryDecision("event", "a", ("a",), "b")
    with pytest.raises(ValueError, match="unique"):
        ReentryDecision("event", "a", ("a", "a"), None)
    event = ReentryDecision("event", "a", ("a",), "a")
    with pytest.raises(ValueError, match="duplicate event_id"):
        score_reentry([event, event])


def _grouped(event_id: str, participant: str, recording: str, correct: bool):
    return GroupedReentryDecision(
        ReentryDecision(event_id, "true", ("true", "other"), "true" if correct else "other"),
        participant,
        recording,
    )


def test_grouped_bootstrap_is_seeded_and_uses_whole_dependency_groups() -> None:
    events = [
        _grouped("a", "p1", "r1", True),
        _grouped("b", "p2", "r2", False),
        _grouped("c", "p3", "r3", True),
    ]
    estimate = grouped_reentry_bootstrap(events, resamples=300, seed=7)
    assert estimate == grouped_reentry_bootstrap(events, resamples=300, seed=7)
    assert estimate.independent_groups == 3
    assert estimate.observed.selective_risk == pytest.approx(1 / 3)
    assert estimate.risk_interval is not None
    assert estimate.risk_interval.low <= 1 / 3 <= estimate.risk_interval.high
    assert estimate.eligible_recall_interval is not None

    # A shared recording joins two participants; a participant seen in two
    # recordings joins those recordings too. These are not four independent events.
    linked = [
        _grouped("a", "p1", "r1", True),
        _grouped("b", "p2", "r1", False),
        _grouped("c", "p2", "r2", True),
        _grouped("d", "p3", "r3", True),
    ]
    assert grouped_reentry_bootstrap(linked, resamples=50).independent_groups == 2


def test_grouped_bootstrap_withholds_unsupported_intervals() -> None:
    no_errors = [_grouped("a", "p1", "r1", True), _grouped("b", "p2", "r2", True)]
    assert grouped_reentry_bootstrap(no_errors, resamples=50).risk_interval is None
    one_group = [_grouped("a", "p1", "r1", True), _grouped("b", "p2", "r1", False)]
    estimate = grouped_reentry_bootstrap(one_group, resamples=50)
    assert estimate.independent_groups == 1
    assert estimate.risk_interval is None
    assert estimate.eligible_recall_interval is None

    with pytest.raises(ValueError, match="duplicate event_id"):
        grouped_reentry_bootstrap([no_errors[0], no_errors[0]])
    with pytest.raises(ValueError, match="resamples must be positive"):
        grouped_reentry_bootstrap(no_errors, resamples=0)
