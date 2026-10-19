"""Dataset-free stress probe for the registered RQ5 selective re-entry rules.

This is a synthetic evaluator check, not an identity model or real-data result.
Run from the checkout after installing the project, or use:
PYTHONPATH=src python -m experiments.reentry_stress --gallery-size 100 --events 3000
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass

import numpy as np

from visiontrack.eval.selective_identity import (
    ReentryDecision,
    score_reentry,
    wilson_upper_bound,
)


@dataclass(frozen=True)
class ProbeEvent:
    event_id: str
    truth_id: str | None
    candidate_ids: frozenset[str]
    best_id: str
    best_score: float
    runner_up_score: float


def policy_grid(*, allow_margin: bool) -> tuple[tuple[float, float], ...]:
    """The original fixed development grid, not a held-out threshold search."""
    thresholds = (0.0, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90, 1.0)
    margins = (0.0, 0.03, 0.06, 0.10, 0.15, 0.20) if allow_margin else (0.0,)
    return tuple((threshold, margin) for threshold in thresholds for margin in margins)


def _unit(vector: np.ndarray) -> np.ndarray:
    return vector / np.linalg.norm(vector)


def generate_events(
    *, seed: int, gallery_size: int, events: int, dimensions: int = 64
) -> list[ProbeEvent]:
    """Generate fixed-gallery returns, unavailable returns, and novel arrivals."""
    if gallery_size < 2 or events < 1 or dimensions < 2:
        raise ValueError("gallery_size >= 2, events >= 1, dimensions >= 2 required")
    rng = np.random.default_rng(seed)
    gallery = rng.normal(size=(gallery_size, dimensions))
    gallery /= np.linalg.norm(gallery, axis=1, keepdims=True)
    # Shared-looking pairs create ambiguity without assigning a real-world identity.
    for index in range(1, gallery_size, 10):
        gallery[index] = _unit(gallery[index - 1] + 0.25 * rng.normal(size=dimensions))
    candidates = tuple(f"g{index}" for index in range(gallery_size))
    candidate_set = frozenset(candidates)
    result: list[ProbeEvent] = []
    for number in range(events):
        draw = rng.random()
        if draw < 0.55:
            chosen = int(rng.integers(gallery_size))
            truth_id = candidates[chosen]
            latent = gallery[chosen]
        elif draw < 0.65:
            # An actual return whose previous identity has expired or been evicted.
            truth_id = f"expired-{number}"
            latent = _unit(rng.normal(size=dimensions))
        else:
            truth_id = None
            latent = _unit(rng.normal(size=dimensions))
        noise = 0.10 if rng.random() < 0.7 else 0.28
        query = _unit(latent + noise * rng.normal(size=dimensions))
        scores = gallery @ query
        best_index = int(np.argmax(scores))
        runner_up = float(np.partition(scores, -2)[-2])
        result.append(
            ProbeEvent(
                f"seed-{seed}-event-{number}",
                truth_id,
                candidate_set,
                candidates[best_index],
                float(scores[best_index]),
                runner_up,
            )
        )
    return result


def decide(event: ProbeEvent, *, threshold: float, margin: float) -> str | None:
    """Exact nearest-candidate scoring with optional absolute and margin gates."""
    if not -1 <= threshold <= 1 or not 0 <= margin <= 2:
        raise ValueError("threshold and margin outside their declared range")
    if event.best_score < threshold or event.best_score - event.runner_up_score < margin:
        return None
    return event.best_id


def evaluate(events: list[ProbeEvent], *, threshold: float, margin: float) -> dict:
    decisions = [
        ReentryDecision(
            event.event_id,
            event.truth_id,
            event.candidate_ids,
            decide(event, threshold=threshold, margin=margin),
        )
        for event in events
    ]
    metrics = score_reentry(decisions)
    attempts = metrics.correct_restorations + metrics.false_restorations
    return {
        **asdict(metrics),
        "restoration_coverage": metrics.restoration_coverage,
        "selective_risk": metrics.selective_risk,
        "eligible_return_recall": metrics.eligible_return_recall,
        "novel_false_match_rate": metrics.novel_false_match_rate,
        "synthetic_risk_upper_95": wilson_upper_bound(metrics.false_restorations, attempts),
    }


def calibrate(
    development: list[ProbeEvent], *, allow_margin: bool, risk_budget: float = 0.01
) -> tuple[float, float] | None:
    """Choose the most useful development rule meeting the registered risk bound."""
    eligible = []
    for threshold, margin in policy_grid(allow_margin=allow_margin):
        result = evaluate(development, threshold=threshold, margin=margin)
        upper = result["synthetic_risk_upper_95"]
        if upper is not None and upper <= risk_budget:
            eligible.append((result["eligible_return_recall"], -threshold, -margin))
    if not eligible:
        return None
    _, negative_threshold, negative_margin = max(eligible)
    return -negative_threshold, -negative_margin


def operating_curve(events: list[ProbeEvent], *, allow_margin: bool) -> list[dict]:
    """Score every fixed grid point; never select or rank using these results.

    Risk need not improve monotonically as a gate tightens. Preserve every
    point and its counts, including undefined risk when there are no attempts.
    """
    points = []
    for threshold, margin in policy_grid(allow_margin=allow_margin):
        metrics = evaluate(events, threshold=threshold, margin=margin)
        points.append(
            {
                "threshold": threshold,
                "margin": margin,
                "metrics": {
                    **metrics,
                    "attempted_restorations": (
                        metrics["correct_restorations"] + metrics["false_restorations"]
                    ),
                },
            }
        )
    return points


def run_probe(
    *, gallery_size: int = 100, events: int = 3000, seed: int = 7, include_curves: bool = False
) -> dict:
    if events < 1:
        raise ValueError("events must be positive")
    development = generate_events(seed=seed, gallery_size=gallery_size, events=events)
    test = generate_events(seed=seed + 1, gallery_size=gallery_size, events=events)
    results = {
        "abstain_all": evaluate(test, threshold=1.0, margin=2.0),
        "forced_nearest": evaluate(test, threshold=-1.0, margin=0.0),
    }
    selected: dict[str, dict | None] = {}
    for name, allow_margin in (("threshold_only", False), ("threshold_and_margin", True)):
        parameters = calibrate(development, allow_margin=allow_margin)
        selected[name] = (
            None
            if parameters is None
            else {
                "threshold": parameters[0],
                "margin": parameters[1],
                "held_out": evaluate(test, threshold=parameters[0], margin=parameters[1]),
            }
        )
    result = {
        "label": "synthetic stress probe; no real-data accuracy claim",
        "seed": seed,
        "gallery_size": gallery_size,
        "development_events": events,
        "held_out_events": events,
        "development_risk_budget": 0.01,
        "fixed_baselines": results,
        "calibrated_policies": selected,
    }
    if include_curves:
        # Calibration above is complete before producing descriptive test curves.
        # Neither the test curve nor a test risk bound can change the chosen rule.
        curves = {}
        for name, allow_margin in (("threshold_only", False), ("threshold_and_margin", True)):
            development_curve = operating_curve(development, allow_margin=allow_margin)
            test_curve = operating_curve(test, allow_margin=allow_margin)
            chosen = selected[name]
            curves[name] = [
                {
                    "threshold": dev["threshold"],
                    "margin": dev["margin"],
                    "selected_on_development": chosen is not None
                    and (dev["threshold"], dev["margin"])
                    == (chosen["threshold"], chosen["margin"]),
                    "development": dev["metrics"],
                    "held_out": held_out["metrics"],
                }
                for dev, held_out in zip(development_curve, test_curve, strict=True)
            ]
        result["operating_curves"] = {
            "schema_version": 1,
            "label": "descriptive fixed-grid synthetic curves; not real-data accuracy",
            "selection_partition": "development only; held-out curves must not select a rule",
            "risk_bound_scope": "one-sided 95% Wilson; independent synthetic events only",
            "undefined_rates": "null means no denominator, not zero risk or zero recall",
            "policies": curves,
        }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gallery-size", type=int, default=100)
    parser.add_argument("--events", type=int, default=3000)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument(
        "--include-curves",
        action="store_true",
        help="Include every fixed-grid development/test point; test curves are descriptive only",
    )
    args = parser.parse_args()
    print(
        json.dumps(
            run_probe(
                gallery_size=args.gallery_size,
                events=args.events,
                seed=args.seed,
                include_curves=args.include_curves,
            ),
            allow_nan=False,
        )
    )


if __name__ == "__main__":
    main()
