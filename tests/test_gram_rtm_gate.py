"""GRAM-RTM backup test: decision rule, exclusion filter and matching limits."""
import numpy as np

from experiments.gram_rtm_gate import iou, judge, keep_outside, match


def _seqs(on, cand, name="aspect_free_gate"):
    return {s: {"main": {"cancel": {"gate_on": dict(zip(("tp", "fp", "fn"), on[i], strict=True)),
                                    name: dict(zip(("tp", "fp", "fn"), cand[i], strict=True))}}}
            for i, s in enumerate(("M-30", "M-30-HD"))}


def test_supported_no_harm_and_harmful():
    assert judge(_seqs([(80, 2, 20), (70, 1, 30)], [(90, 3, 10), (80, 1, 20)]),
                 "aspect_free_gate") == "supported"
    assert judge(_seqs([(80, 2, 20), (70, 1, 30)], [(80, 3, 20), (70, 2, 30)]),
                 "aspect_free_gate") == "no harm"
    assert judge(_seqs([(80, 2, 20), (70, 1, 30)], [(75, 2, 25), (70, 1, 30)]),
                 "aspect_free_gate") == "harmful"


def test_one_sequence_worse_by_three_blocks_support():
    # Pooled misses fall, but M-30-HD gains three errors.
    seqs = _seqs([(80, 2, 20), (70, 1, 30)], [(95, 2, 5), (68, 2, 32)])
    assert judge(seqs, "aspect_free_gate") == "no harm"


def test_exclusion_mask_drops_crossings_inside_it():
    mask = np.zeros((10, 10), dtype=bool)
    mask[:, :5] = True
    events = [{"x": 2.0, "y": 5.0}, {"x": 7.0, "y": 5.0}]
    assert keep_outside(events, mask) == [events[1]]


def test_match_uses_frame_and_pixel_limits():
    ref = [{"frame": 100, "x": 50.0, "y": 240.0, "dir": "A->B"}]
    near = [{"frame": 106, "x": 80.0, "y": 240.0, "dir": "A->B"}]
    late = [{"frame": 107, "x": 50.0, "y": 240.0, "dir": "A->B"}]
    assert match(ref, near, 31.2)["tp"] == 1
    assert match(ref, late, 31.2) == {"tp": 0, "fp": 1, "fn": 1}
    assert match(ref, near, 20.0)["tp"] == 0
    assert iou([0, 0, 2, 2], [1, 1, 3, 3]) == 1 / 7
