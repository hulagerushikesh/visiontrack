"""Named tracker presets — the tracking-by-detection *lineage* on one core.

The association core in this repo (gated cost + two-stage matching + Kalman) is a
strict superset of several classic trackers. Turning knobs on
:class:`~visiontrack.tracking.config.TrackerConfig` recovers each of them, so we
can compare the whole family **on identical detections, metrics, and seeds** —
the only honest way to say "two-stage beats single-stage by X".

These are *lineage presets*, not the papers' official code. Each is our
re-expression of a method's defining idea on the shared core:

======================  ============================================  ==========
preset                  defining idea                                 flags
======================  ============================================  ==========
``sort``                single-stage IoU association, no appearance   1 stage
``deepsort``            single-stage IoU **+** appearance re-ID        1 stage, w_app
``bytetrack``           two-stage: recover with low-score detections  2 stage
``bytetrack_reid``      two-stage IoU **+** appearance (BoT-SORT-lite) 2 stage, w_app
``bytetrack_giou``      two-stage, GIoU motion term                   2 stage, GIoU
``oc_sort``             single-stage + observation-centric OCM+ORU     1 stage, w_ocm, ORU
======================  ============================================  ==========

"Single stage" is expressed by collapsing the low/high score band
(``low_score_thresh == high_score_thresh``) so the recovery stage has nothing to
do — exactly SORT's single detection threshold. Appearance presets require the
detections to carry embeddings (the synthetic appearance channel, or a MOT17
Re-ID cache); with no embeddings the ``w_app`` term is simply inert.

``oc_sort`` uses genuinely new mechanics rather than a config flag alone — the
observation-centric momentum term and re-update live in
:mod:`visiontrack.tracking.motion.oc` and are switched on here via ``w_ocm`` and
``use_oru``.

Use-case presets
----------------

Separate from the lineage, :data:`USE_CASE_PRESETS` holds opt-in settings for
a kind of video. They never change the library default and are not part of
:data:`PRESET_NAMES`, so lineage comparisons are unchanged.

``traffic``  ByteTrack with the Mahalanobis motion gate switched off, for
fixed-camera vehicle counting. The default gate is tuned for slow pedestrians
and stopped tracks from confirming on fast near-camera vehicles. Gate off was
supported in two frozen tests on unused video (GRAM-RTM and SVMOT): pooled
missed crossings fell from 53 to 28 of 601, false crossings from 4 to 3, and
SVMOT ID switches from 583 to 244. It is untested on turning traffic at busy
junctions and is not a default change. See ``docs/TRAFFIC_PRESET.md``.

Usage::

    from visiontrack.tracking.presets import preset
    from visiontrack.tracking.tracker import ByteTracker

    tracker = ByteTracker(preset("sort"))
"""
from __future__ import annotations

from dataclasses import replace

from .config import TrackerConfig

__all__ = [
    "PRESETS", "PRESET_NAMES", "USE_CASE_PRESETS", "USE_CASE_PRESET_NAMES",
    "preset", "preset_overrides",
]

# The single detection threshold used by the single-stage ("SORT-style") presets.
# Collapsing the score band onto one value disables the recovery stage.
_SINGLE_STAGE_THRESH = 0.5

#: The lineage. Each value is the set of :class:`TrackerConfig` overrides that
#: turns the shared core into that tracker. ``bytetrack`` is the empty override
#: (it *is* the core's default), and serves as the comparison baseline.
PRESETS: dict[str, dict] = {
    "sort": {
        "high_score_thresh": _SINGLE_STAGE_THRESH,
        "low_score_thresh": _SINGLE_STAGE_THRESH,  # collapse band -> single stage
        "w_app": 0.0,
    },
    "deepsort": {
        "high_score_thresh": _SINGLE_STAGE_THRESH,
        "low_score_thresh": _SINGLE_STAGE_THRESH,  # single stage
        "w_app": 0.6,  # + appearance re-ID
    },
    "bytetrack": {},  # the core's default: two-stage IoU association
    "bytetrack_reid": {
        "w_app": 0.6,  # two-stage + appearance (BoT-SORT-lite)
    },
    "bytetrack_giou": {
        "use_giou": True,  # two-stage, GIoU motion term
    },
    "oc_sort": {
        # Observation-centric SORT: single-stage IoU (like SORT) + OCM momentum
        # term + observation-centric re-update on re-match. No appearance.
        "high_score_thresh": _SINGLE_STAGE_THRESH,
        "low_score_thresh": _SINGLE_STAGE_THRESH,
        "w_ocm": 0.2,
        "use_oru": True,
    },
}

#: Insertion-ordered preset names (single-stage first, then the ByteTrack family).
PRESET_NAMES: list[str] = list(PRESETS)

#: Opt-in settings for a kind of video, kept apart from the lineage so that
#: zoo and benchmark runs over :data:`PRESET_NAMES` are unchanged.
USE_CASE_PRESETS: dict[str, dict] = {
    "traffic": {
        # Fixed-camera vehicle counting: switch the pedestrian-tuned motion
        # gate off. Evidence: docs/TRAFFIC_PRESET.md.
        "use_mahalanobis_gating": False,
    },
}

#: Insertion-ordered use-case preset names.
USE_CASE_PRESET_NAMES: list[str] = list(USE_CASE_PRESETS)


def preset_overrides(name: str) -> dict:
    """Return a *copy* of the override dict for ``name`` (raises on unknown)."""
    if name in PRESETS:
        return dict(PRESETS[name])
    if name in USE_CASE_PRESETS:
        return dict(USE_CASE_PRESETS[name])
    raise KeyError(
        f"unknown preset {name!r}; choose one of "
        f"{PRESET_NAMES + USE_CASE_PRESET_NAMES}"
    )


def preset(name: str, **extra) -> TrackerConfig:
    """Build the :class:`TrackerConfig` for a named preset.

    Any ``extra`` keyword overrides are applied on top (e.g. ``preset("sort",
    max_age=15)``), so presets compose with per-experiment tweaks.
    """
    overrides = preset_overrides(name)
    overrides.update(extra)
    return replace(TrackerConfig(), **overrides)
