"""The synthetic probe is reproducible and cannot select on held-out events."""

from experiments.reentry_stress import calibrate, evaluate, generate_events, run_probe


def test_synthetic_probe_is_repeatable_and_tracks_novel_and_expired_returns() -> None:
    a = generate_events(seed=9, gallery_size=10, events=200)
    b = generate_events(seed=9, gallery_size=10, events=200)
    assert a == b
    assert any(event.truth_id is None for event in a)
    assert any(event.truth_id and event.truth_id.startswith("expired-") for event in a)
    result = evaluate(a, threshold=-1, margin=0)
    assert result["restoration_coverage"] == 1
    assert result["false_restorations"] > 0


def test_abstain_all_is_safe_but_has_no_restoration_recall() -> None:
    events = generate_events(seed=4, gallery_size=10, events=100)
    result = evaluate(events, threshold=1, margin=2)
    assert result["correct_restorations"] == 0
    assert result["false_restorations"] == 0
    assert result["selective_risk"] is None
    assert result["eligible_return_recall"] == 0


def test_development_calibration_and_held_out_test_are_separate() -> None:
    development = generate_events(seed=4, gallery_size=10, events=100)
    test = generate_events(seed=5, gallery_size=10, events=100)
    assert development[0].event_id != test[0].event_id
    assert calibrate(development, allow_margin=True) is None  # insufficient evidence
    result = run_probe(gallery_size=10, events=100, seed=4)
    assert result["calibrated_policies"]["threshold_and_margin"] is None
    assert result["held_out_events"] == 100
