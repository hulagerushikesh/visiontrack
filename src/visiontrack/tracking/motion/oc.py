"""Observation-centric mechanics — the two defining ideas of OC-SORT.

OC-SORT's insight is that a constant-velocity Kalman filter is *estimation*-
centric: during an occlusion gap it coasts on prediction, and its velocity
estimate — never re-anchored to an observation — drifts, which then causes ID
switches when the object reappears. OC-SORT fixes this by trusting *observations*
over the linear estimate in two places:

* **OCM — Observation-Centric Momentum.** A soft association term that rewards
  matches consistent with the track's *observed* direction of motion. It compares
  the track's velocity direction (from two observations ``delta_t`` frames apart)
  with the direction from the track's last observation to a candidate detection;
  a large angle between them is penalised. Inert (zero) for tracks without enough
  observation history or with ~zero observed velocity, so it never fabricates a
  preference.

* **ORU — Observation-Centric Re-Update.** When a lost track is re-associated
  after coasting for ``gap`` frames, rebuild its state along a *virtual
  trajectory* linearly interpolated between the last observation before the gap
  and the new one, re-running predict→update at each virtual step. This undoes
  the drift accumulated while coasting and, crucially, re-anchors the velocity to
  a smooth, observation-consistent path.

Both are additive to the existing tracker and are switched off by default, so the
baseline behaviour is unchanged.
"""
from __future__ import annotations

import numpy as np

__all__ = ["momentum_cost", "observation_centric_reupdate"]

_EPS = 1e-9


def _centre(box_xyxy: np.ndarray) -> np.ndarray:
    return np.array(
        [(box_xyxy[0] + box_xyxy[2]) / 2.0, (box_xyxy[1] + box_xyxy[3]) / 2.0]
    )


def momentum_cost(tracks, det_boxes: np.ndarray, delta_t: int) -> np.ndarray:
    """``(T, D)`` observation-centric momentum cost in ``[0, 1]``.

    For each track with at least ``delta_t + 1`` observations and a non-negligible
    observed velocity, the cost of a detection is the angle (normalised by ``π``)
    between the track's observed velocity direction and the direction from its last
    observation to that detection. Tracks lacking history or velocity contribute a
    zero row (the term is inert for them).
    """
    n_t, n_d = len(tracks), len(det_boxes)
    out = np.zeros((n_t, n_d), dtype=np.float64)
    if n_t == 0 or n_d == 0:
        return out

    det_boxes = np.asarray(det_boxes, dtype=np.float64)
    det_centres = np.stack(
        [(det_boxes[:, 0] + det_boxes[:, 2]) / 2.0,
         (det_boxes[:, 1] + det_boxes[:, 3]) / 2.0],
        axis=1,
    )  # (D, 2)

    for i, track in enumerate(tracks):
        history = track.history
        if len(history) < delta_t + 1:
            continue  # not enough observations -> inert
        c_now = _centre(history[-1])
        c_prev = _centre(history[-1 - delta_t])
        velocity = c_now - c_prev
        speed = float(np.linalg.norm(velocity))
        if speed < _EPS:
            continue  # ~stationary track -> no directional prior

        directions = det_centres - c_now[None, :]        # (D, 2)
        dist = np.linalg.norm(directions, axis=1)         # (D,)
        cos = (directions @ velocity) / (dist * speed + _EPS)
        angle = np.arccos(np.clip(cos, -1.0, 1.0))        # [0, π]
        row = angle / np.pi
        row[dist < _EPS] = 0.0                            # detection on the track
        out[i] = row
    return out


def observation_centric_reupdate(
    kf,
    start_mean: np.ndarray,
    start_cov: np.ndarray,
    last_obs_xyah: np.ndarray,
    new_obs_xyah: np.ndarray,
    gap: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Rebuild a track's state along a virtual trajectory across an occlusion gap.

    Re-runs the filter **from the state at the last observation** (``start_mean``,
    ``start_cov`` — the post-update estimate before the gap, *not* a fresh
    initialisation), walking a straight line to the new observation in ``gap``
    steps and running predict→update at each virtual observation. Returns the
    ``(mean, covariance)`` at the new observation.

    Anchoring to the pre-gap state (rather than re-initialising) is what makes
    this observation-centric *and* stable: the covariance stays tight, so the next
    frame's gate is not blown wide open — the failure mode of a naive re-init.
    """
    start_mean = np.asarray(start_mean, dtype=np.float64)
    start_cov = np.asarray(start_cov, dtype=np.float64)
    last_obs_xyah = np.asarray(last_obs_xyah, dtype=np.float64)
    new_obs_xyah = np.asarray(new_obs_xyah, dtype=np.float64)
    gap = max(int(gap), 1)

    mean, cov = start_mean.copy(), start_cov.copy()
    step = (new_obs_xyah - last_obs_xyah) / gap
    for i in range(1, gap + 1):
        virtual = last_obs_xyah + step * i
        mean, cov = kf.predict(mean, cov)
        mean, cov = kf.update(mean, cov, virtual)
    return mean, cov
