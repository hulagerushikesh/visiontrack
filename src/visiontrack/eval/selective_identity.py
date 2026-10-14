"""Event-level evaluation for experimental, bounded anonymous re-entry.

This module scores already-recorded decisions. It does not identify people,
retain embeddings, or change the default online tracker.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, fields
from math import floor, isfinite
from random import Random


@dataclass(frozen=True)
class ReentryDecision:
    """One chance to link a new tracklet to a recent anonymous identity.

    ``truth_id=None`` means a genuinely new identity. An existing truth ID may
    be absent from ``candidate_ids`` because it expired or was evicted.
    ``restored_id=None`` is an explicit abstention, not an evaluation error.
    """

    event_id: str
    truth_id: str | None
    candidate_ids: tuple[str, ...] | frozenset[str]
    restored_id: str | None

    def __post_init__(self) -> None:
        if not self.event_id:
            raise ValueError("event_id must not be empty")
        if self.truth_id == "" or self.restored_id == "":
            raise ValueError("identity IDs must not be empty")
        if isinstance(self.candidate_ids, frozenset):
            if "" in self.candidate_ids:
                raise ValueError("candidate IDs must not be empty")
        else:
            if any(not candidate for candidate in self.candidate_ids):
                raise ValueError("candidate IDs must not be empty")
            if len(set(self.candidate_ids)) != len(self.candidate_ids):
                raise ValueError("candidate IDs must be unique")
        if self.restored_id is not None and self.restored_id not in self.candidate_ids:
            raise ValueError("restored identity must be an available candidate")


@dataclass(frozen=True)
class SelectiveIdentityMetrics:
    opportunities: int
    eligible_returns: int
    unavailable_returns: int
    novel_arrivals: int
    correct_restorations: int
    false_restorations: int
    false_restorations_of_novel: int
    eligible_abstentions: int
    unavailable_abstentions: int
    novel_abstentions: int

    @property
    def restoration_coverage(self) -> float | None:
        """Fraction of all opportunities on which the system restored an ID."""
        if not self.opportunities:
            return None
        return (self.correct_restorations + self.false_restorations) / self.opportunities

    @property
    def selective_risk(self) -> float | None:
        """False restorations / all restorations; undefined if none were attempted."""
        attempted = self.correct_restorations + self.false_restorations
        return self.false_restorations / attempted if attempted else None

    @property
    def eligible_return_recall(self) -> float | None:
        """Correct restores / returns whose true identity was still in memory."""
        if not self.eligible_returns:
            return None
        return self.correct_restorations / self.eligible_returns

    @property
    def novel_false_match_rate(self) -> float | None:
        if not self.novel_arrivals:
            return None
        return self.false_restorations_of_novel / self.novel_arrivals


@dataclass(frozen=True)
class GroupedReentryDecision:
    """An event with owner-private, anonymous dependency-group keys.

    The same participant may span recordings, and a recording may contain
    several participants. Neither key should be a name or public identifier.
    """

    decision: ReentryDecision
    participant_group: str
    recording_group: str

    def __post_init__(self) -> None:
        if not self.participant_group.strip() or not self.recording_group.strip():
            raise ValueError("participant and recording groups must not be empty")


@dataclass(frozen=True)
class MetricInterval:
    low: float
    high: float


@dataclass(frozen=True)
class GroupedReentryEstimate:
    observed: SelectiveIdentityMetrics
    independent_groups: int
    resamples: int
    risk_interval: MetricInterval | None
    eligible_recall_interval: MetricInterval | None


def _percentile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    lower = floor(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def grouped_reentry_bootstrap(
    events: Iterable[GroupedReentryDecision],
    *,
    resamples: int = 2000,
    seed: int = 0,
    confidence: float = 0.95,
) -> GroupedReentryEstimate:
    """Descriptive cluster-bootstrap intervals for real-video event ratios.

    A participant shared across recordings or participants sharing a recording
    form one dependency-connected group. Resampling events individually would
    overstate precision. These percentile intervals are *not* a certified
    operating-risk bound; zero observed false restores, one group, or a
    denominator-free resample yields no corresponding interval.
    """
    if resamples < 1:
        raise ValueError("resamples must be positive")
    if not isfinite(confidence) or not 0 < confidence < 1:
        raise ValueError("confidence must be between zero and one")

    records = tuple(events)
    observed = score_reentry(record.decision for record in records)
    parent: dict[str, str] = {}

    def root(key: str) -> str:
        parent.setdefault(key, key)
        while parent[key] != key:
            parent[key] = parent[parent[key]]
            key = parent[key]
        return key

    for record in records:
        participant = f"p:{record.participant_group}"
        recording = f"r:{record.recording_group}"
        parent[root(recording)] = root(participant)

    groups: dict[str, list[ReentryDecision]] = {}
    for record in records:
        key = root(f"p:{record.participant_group}")
        groups.setdefault(key, []).append(record.decision)
    group_metrics = [score_reentry(group) for group in groups.values()]
    number_of_groups = len(group_metrics)
    if number_of_groups < 2:
        return GroupedReentryEstimate(observed, number_of_groups, resamples, None, None)

    rng = Random(seed)
    risk_samples: list[float] = []
    recall_samples: list[float] = []
    metric_names = tuple(field.name for field in fields(SelectiveIdentityMetrics))
    for _ in range(resamples):
        sampled = [group_metrics[rng.randrange(number_of_groups)] for _ in range(number_of_groups)]
        totals = {name: sum(getattr(group, name) for group in sampled) for name in metric_names}
        metrics = SelectiveIdentityMetrics(**totals)
        if metrics.selective_risk is not None:
            risk_samples.append(metrics.selective_risk)
        if metrics.eligible_return_recall is not None:
            recall_samples.append(metrics.eligible_return_recall)

    alpha = 1 - confidence
    risk_interval = None
    if observed.false_restorations and len(risk_samples) == resamples:
        risk_interval = MetricInterval(
            _percentile(risk_samples, alpha / 2), _percentile(risk_samples, 1 - alpha / 2)
        )
    recall_interval = None
    if len(recall_samples) == resamples:
        recall_interval = MetricInterval(
            _percentile(recall_samples, alpha / 2), _percentile(recall_samples, 1 - alpha / 2)
        )
    return GroupedReentryEstimate(
        observed, number_of_groups, resamples, risk_interval, recall_interval
    )


def score_reentry(decisions: Iterable[ReentryDecision]) -> SelectiveIdentityMetrics:
    """Score restores and abstentions without hiding expiry or novel arrivals."""
    counts = {
        "opportunities": 0,
        "eligible_returns": 0,
        "unavailable_returns": 0,
        "novel_arrivals": 0,
        "correct_restorations": 0,
        "false_restorations": 0,
        "false_restorations_of_novel": 0,
        "eligible_abstentions": 0,
        "unavailable_abstentions": 0,
        "novel_abstentions": 0,
    }
    seen: set[str] = set()
    for decision in decisions:
        if decision.event_id in seen:
            raise ValueError(f"duplicate event_id: {decision.event_id}")
        seen.add(decision.event_id)
        counts["opportunities"] += 1
        if decision.truth_id is None:
            counts["novel_arrivals"] += 1
            if decision.restored_id is None:
                counts["novel_abstentions"] += 1
            else:
                counts["false_restorations"] += 1
                counts["false_restorations_of_novel"] += 1
        elif decision.truth_id in decision.candidate_ids:
            counts["eligible_returns"] += 1
            if decision.restored_id == decision.truth_id:
                counts["correct_restorations"] += 1
            elif decision.restored_id is None:
                counts["eligible_abstentions"] += 1
            else:
                counts["false_restorations"] += 1
        else:
            counts["unavailable_returns"] += 1
            if decision.restored_id is None:
                counts["unavailable_abstentions"] += 1
            else:
                counts["false_restorations"] += 1
    return SelectiveIdentityMetrics(**counts)


def wilson_upper_bound(errors: int, trials: int, *, z: float = 1.645) -> float | None:
    """One-sided 95% Wilson upper bound for a descriptive binomial rate.

    Clustered real-video events need a participant/camera-group bootstrap
    instead; this helper is intended for independent synthetic events.
    """
    if trials < 0 or not 0 <= errors <= trials:
        raise ValueError("require 0 <= errors <= trials")
    if not isfinite(z) or z <= 0:
        raise ValueError("z must be positive and finite")
    if trials == 0:
        return None
    p = errors / trials
    z2 = z * z
    center = p + z2 / (2 * trials)
    radius = z * ((p * (1 - p) / trials + z2 / (4 * trials * trials)) ** 0.5)
    return min(1.0, (center + radius) / (1 + z2 / trials))
