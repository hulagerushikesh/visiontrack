"""Keep the first identity-continuity metrics honest at every boundary."""

import pytest

from visiontrack.eval.selective_identity import (
    ReentryDecision,
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
