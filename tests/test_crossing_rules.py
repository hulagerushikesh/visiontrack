"""Jitter-proof counting rules: one crossing per real pass, plain behaviour otherwise."""
from experiments.crossing_rules import cancel_reversals, hysteresis_crossings
from experiments.roundabouthd_gate import crossings

LINE = ((0.0, 100.0), (200.0, 100.0))  # horizontal line y = 100


def _track(ys, ident=1, x=50.0, start=1):
    return {(start + k, ident): (x, float(y)) for k, y in enumerate(ys)}


CLEAN = [60, 80, 95, 105, 120, 140]
JITTER = [60, 80, 97, 103, 98, 104, 120, 140]  # wobbles on the line, then leaves


def test_clean_pass_is_counted_once_by_every_rule():
    plain = crossings(_track(CLEAN), LINE)
    assert len(plain) == 1
    assert cancel_reversals(plain, 15) == plain
    assert hysteresis_crossings(_track(CLEAN), LINE, 20.0) == plain


def test_jitter_counts_three_times_plain_but_once_with_either_rule():
    plain = crossings(_track(JITTER), LINE)
    assert [e["dir"] for e in plain] == ["A->B", "B->A", "A->B"]
    for rule in (cancel_reversals(plain, 15), hysteresis_crossings(_track(JITTER), LINE, 20.0)):
        assert len(rule) == 1 and rule[0]["dir"] == "A->B"
        assert rule[0]["frame"] == 6  # reported at the last raw crossing


def test_slow_real_return_is_kept_by_cancel_rule():
    there_and_back = [60, 95, 105, 140] + [140] * 20 + [105, 95, 60]
    plain = crossings(_track(there_and_back), LINE)
    assert len(plain) == 2
    assert cancel_reversals(plain, 15) == plain
    assert len(hysteresis_crossings(_track(there_and_back), LINE, 20.0)) == 2


def test_wobble_that_returns_to_its_side_is_not_counted():
    wobble = [60, 95, 103, 96, 60]
    assert len(crossings(_track(wobble), LINE)) == 2
    assert cancel_reversals(crossings(_track(wobble), LINE), 15) == []
    assert hysteresis_crossings(_track(wobble), LINE, 20.0) == []


def test_zero_band_matches_plain_counter_and_ids_stay_separate():
    centres = _track(JITTER) | _track(CLEAN, ident=2, x=150.0)
    assert hysteresis_crossings(centres, LINE, 0.0) == crossings(centres, LINE)
    assert {e["id"] for e in cancel_reversals(crossings(centres, LINE), 15)} == {1, 2}
