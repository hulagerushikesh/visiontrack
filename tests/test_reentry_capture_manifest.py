"""The RQ5 pilot plan must freeze basic controls before recording."""

from dataclasses import replace

import pytest

from experiments.reentry_capture_manifest import SCENARIOS, CaptureManifest, PlannedTake


def _manifest() -> CaptureManifest:
    return CaptureManifest(
        study_id="local-pilot-1",
        frozen_on="2026-10-14",
        camera_setup="fixed camera, fixed lighting",
        scene_exit_rule="entire person crosses marked frame edge",
        frame_rate=30,
        width=1280,
        height=720,
        short_absence_seconds=5,
        long_absence_seconds=20,
        gallery_ttl_seconds=60,
        expired_return_seconds=90,
        gallery_capacity=100,
        retention_days=7,
        rights_review_ref="owner-private-rights-review",
        consent_process_ref="owner-private-consent-process",
        withdrawal_process_ref="owner-private-withdrawal-process",
        storage_plan_ref="owner-private-storage-plan",
        permitted_scene_changes=("none",),
        planned_takes=tuple(PlannedTake("development", scenario, 1) for scenario in SCENARIOS)
        + (PlannedTake("test", "novel", 1),),
    )


def test_valid_plan_has_stable_fingerprint() -> None:
    manifest = _manifest()
    assert len(manifest.fingerprint) == 64
    assert manifest.fingerprint == _manifest().fingerprint
    assert manifest.fingerprint == replace(
        manifest, planned_takes=tuple(reversed(manifest.planned_takes))
    ).fingerprint
    assert manifest.fingerprint != replace(manifest, gallery_capacity=10).fingerprint


def test_intervals_and_required_controls_fail_closed() -> None:
    with pytest.raises(ValueError, match="short < long < TTL < expired"):
        replace(_manifest(), expired_return_seconds=60)
    with pytest.raises(ValueError, match="every required control"):
        replace(
            _manifest(),
            planned_takes=tuple(
                take for take in _manifest().planned_takes if take.scenario != "session_reset"
            ),
        )
    with pytest.raises(ValueError, match="both development and test"):
        replace(
            _manifest(),
            planned_takes=tuple(take for take in _manifest().planned_takes if take.split == "test"),
        )


def test_invalid_dates_and_duplicate_plan_cells_fail() -> None:
    with pytest.raises(ValueError, match="ISO calendar date"):
        replace(_manifest(), frozen_on="2026-02-30")
    with pytest.raises(ValueError, match="duplicate planned take"):
        replace(
            _manifest(),
            planned_takes=_manifest().planned_takes + (PlannedTake("test", "novel", 1),),
        )
    with pytest.raises(ValueError, match="positive"):
        replace(_manifest(), retention_days=0)
