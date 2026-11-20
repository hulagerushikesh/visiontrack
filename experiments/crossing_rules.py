"""Development candidates: counting rules that ignore a track jittering on the line.

The counter used in the RoundaboutHD tests counts every adjacent-frame step of
a box centre across the line. A track whose centre wobbles on the line
(B->A, A->B, B->A within a few frames) is counted three times, for a vehicle
that crossed once. That is how the gate-off variant lost the c003 condition.

Two rules, each applied to the output of the plain counter:

* ``cancel_reversals``: a crossing followed by the same ID crossing back within
  ``window`` frames cancels both. Holds no geometry, so it works on any line.
* ``hysteresis_crossings``: a track's side only changes once its centre is more
  than ``band`` pixels past the line; a committed change is reported at the
  frame and point of its last raw crossing, so timing matches the plain counter.

Experiment-only. See docs/COUNTING_RULE_DEVELOPMENT.md.
"""
from __future__ import annotations

from collections import defaultdict


def cancel_reversals(events: list[dict], window: int) -> list[dict]:
    """Drop crossing pairs where one ID crosses back within ``window`` frames."""
    kept: dict[int, list[dict]] = defaultdict(list)
    for event in sorted(events, key=lambda e: (e["frame"], e["id"])):
        stack = kept[event["id"]]
        if stack and stack[-1]["dir"] != event["dir"] and \
                event["frame"] - stack[-1]["frame"] <= window:
            stack.pop()
        else:
            stack.append(event)
    return sorted((e for stack in kept.values() for e in stack),
                  key=lambda e: (e["frame"], e["id"]))


def hysteresis_crossings(centres: dict, line, band: float) -> list[dict]:
    """Crossings with a dead band of ``band`` pixels either side of the segment line."""
    (ax, ay), (bx, by) = line
    length = ((bx - ax) ** 2 + (by - ay) ** 2) ** 0.5

    def signed(x, y):
        return ((bx - ax) * (y - ay) - (by - ay) * (x - ax)) / length

    tracks: dict[int, list[tuple[int, tuple[float, float]]]] = defaultdict(list)
    for (frame, ident), p in centres.items():
        tracks[ident].append((frame, p))
    events = []
    for ident, points in tracks.items():
        points.sort()
        first = signed(*points[0][1])
        state = (first > 0) - (first < 0)  # committed side; a track born in the band starts here
        pending = None  # last raw crossing inside the segment since the commit
        for (f0, p), (f1, q) in zip(points, points[1:], strict=False):
            s0, s1 = signed(*p), signed(*q)
            if f1 == f0 + 1 and s0 != 0 and s0 * s1 <= 0:
                t = s0 / (s0 - s1)
                x, y = p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1])
                u = ((x - ax) * (bx - ax) + (y - ay) * (by - ay)) / length ** 2
                if 0 <= u <= 1:
                    pending = {"frame": f1, "id": ident, "x": round(x, 1), "y": round(y, 1),
                               "dir": "A->B" if s0 < 0 else "B->A"}
            if abs(s1) > band:
                new = -1 if s1 < 0 else 1
                if new != state and pending is not None:
                    events.append(pending)
                pending, state = None, new
    return sorted(events, key=lambda e: (e["frame"], e["id"]))
