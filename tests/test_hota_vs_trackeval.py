"""Cross-check our from-scratch HOTA/IDF1 against the reference `trackeval`.

A reviewer won't trust a hand-rolled HOTA. This asserts our numbers match the
canonical implementation within tolerance on constructed sequences (perfect
tracking, an identity switch, and several random scenes). It is data-free, so
it runs in CI whenever trackeval is installed; it skips cleanly otherwise.

Install the reference to enable it::

    pip install git+https://github.com/JonathonLuiten/TrackEval.git
"""
import numpy as np
import pytest

from visiontrack.eval.hota import compute_hota, compute_identity

# trackeval predates NumPy 2.0 and still references the removed builtin aliases
# (np.float, np.int, ...). Re-add them for this dev-only cross-check so the
# reference implementation runs under modern NumPy. This affects nothing in our
# own code — it only restores attributes trackeval expects.
for _name, _py in (("float", float), ("int", int), ("bool", bool)):
    if not hasattr(np, _name):
        setattr(np, _name, _py)

trackeval = pytest.importorskip("trackeval", reason="trackeval not installed")
from trackeval.metrics import HOTA, Identity  # noqa: E402

TOL = 1e-3


def _to_trackeval_data(frames):
    """Convert our (gt_ids, gt_boxes, tr_ids, tr_boxes) frames to a trackeval
    `data` dict with 0-indexed ids and per-frame IoU similarity matrices."""
    from visiontrack.core.geometry import iou_matrix

    gt_ids_all, tr_ids_all = set(), set()
    for g, _, t, _ in frames:
        gt_ids_all.update(g.tolist())
        tr_ids_all.update(t.tolist())
    gmap = {g: i for i, g in enumerate(sorted(gt_ids_all))}
    tmap = {t: i for i, t in enumerate(sorted(tr_ids_all))}

    gt_ids, tr_ids, sims = [], [], []
    n_gt_dets = n_tr_dets = 0
    for g, gb, t, tb in frames:
        gi = np.array([gmap[x] for x in g.tolist()], dtype=int)
        ti = np.array([tmap[x] for x in t.tolist()], dtype=int)
        gt_ids.append(gi)
        tr_ids.append(ti)
        n_gt_dets += gi.size
        n_tr_dets += ti.size
        if gi.size and ti.size:
            sims.append(iou_matrix(gb, tb))
        else:
            sims.append(np.zeros((gi.size, ti.size)))
    return {
        "num_gt_ids": len(gmap),
        "num_tracker_ids": len(tmap),
        "num_gt_dets": n_gt_dets,
        "num_tracker_dets": n_tr_dets,
        "gt_ids": gt_ids,
        "tracker_ids": tr_ids,
        "similarity_scores": sims,
        "num_timesteps": len(frames),
    }


def _reference(frames):
    data = _to_trackeval_data(frames)
    hota = HOTA().eval_sequence(data)
    ident = Identity().eval_sequence(data)
    return {
        "HOTA": float(np.mean(hota["HOTA"])),
        "DetA": float(np.mean(hota["DetA"])),
        "AssA": float(np.mean(hota["AssA"])),
        "IDF1": float(ident["IDF1"]),
    }


def _box(cx, cy, w=20, h=40):
    return [cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2]


def _random_frames(seed, n=25):
    rng = np.random.default_rng(seed)
    frames = []
    for _ in range(n):
        g = int(rng.integers(1, 6))
        gt_ids = rng.choice(np.arange(1, 10), size=g, replace=False)
        gt_boxes = np.array([_box(*rng.uniform(50, 600, size=2)) for _ in range(g)])
        # Trackers: perturbations of some gt boxes plus occasional noise ids.
        tr_ids, tr_boxes = [], []
        for k in range(g):
            if rng.random() < 0.8:
                tr_ids.append(int(gt_ids[k]) + 100)
                tr_boxes.append(gt_boxes[k] + rng.normal(0, 4, size=4))
        if rng.random() < 0.3:
            tr_ids.append(int(rng.integers(500, 600)))
            tr_boxes.append(np.array(_box(*rng.uniform(50, 600, size=2))))
        tr_ids = np.array(tr_ids, dtype=int) if tr_ids else np.empty(0, int)
        tr_boxes = np.array(tr_boxes).reshape(-1, 4)
        frames.append((gt_ids, gt_boxes, tr_ids, tr_boxes))
    return frames


def test_perfect_matches_trackeval():
    frames = []
    for t in range(10):
        ids = np.array([1, 2, 3])
        boxes = np.array([_box(100 * k + t, 100) for k in range(3)])
        frames.append((ids, boxes, ids + 50, boxes.copy()))
    ref = _reference(frames)
    assert compute_hota(frames).hota == pytest.approx(ref["HOTA"], abs=TOL)
    assert compute_identity(frames).idf1 == pytest.approx(ref["IDF1"], abs=TOL)


def test_identity_switch_matches_trackeval():
    n = 20
    frames = []
    for t in range(n):
        gt_ids = np.array([1])
        box = np.array([_box(100 + t, 100)])
        tr_id = np.array([10 if t < n // 2 else 20])
        frames.append((gt_ids, box, tr_id, box.copy()))
    ref = _reference(frames)
    ours = compute_hota(frames)
    assert ours.hota == pytest.approx(ref["HOTA"], abs=TOL)
    assert ours.det_a == pytest.approx(ref["DetA"], abs=TOL)
    assert ours.ass_a == pytest.approx(ref["AssA"], abs=TOL)
    assert compute_identity(frames).idf1 == pytest.approx(ref["IDF1"], abs=TOL)


@pytest.mark.parametrize("seed", range(6))
def test_random_scenes_match_trackeval(seed):
    frames = _random_frames(seed)
    ref = _reference(frames)
    ours_h = compute_hota(frames)
    ours_id = compute_identity(frames)
    assert ours_h.hota == pytest.approx(ref["HOTA"], abs=TOL)
    assert ours_h.det_a == pytest.approx(ref["DetA"], abs=TOL)
    assert ours_h.ass_a == pytest.approx(ref["AssA"], abs=TOL)
    assert ours_id.idf1 == pytest.approx(ref["IDF1"], abs=TOL)
