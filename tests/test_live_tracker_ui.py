"""Observable contracts for the React live tracker boundary."""
from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_react_surface_keeps_required_runtime_controls() -> None:
    page = (ROOT / "src/features/live-tracker/LiveTracker.tsx").read_text()
    for element_id in ("src-video", "live-cv", "start-btn", "src-seg", "det-toggle", "status"):
        assert f'id="{element_id}"' in page
    for metric_id in ("m-fps", "m-tracks", "m-ids", "m-dets"):
        assert f'["{metric_id}"' in page
    assert "runtime.mount(root.current)" in page
    assert "cleanup?.()" in page


def test_live_privacy_and_identity_boundary_is_explicit() -> None:
    page = (ROOT / "src/features/live-tracker/LiveTracker.tsx").read_text()
    assert "Nothing leaves your device" in page
    assert "only after you press Start" in page
    assert "session labels—not persistent person identities" in page
    assert 'type="file"' not in page
    assert "fetch(" not in page


def test_adapter_preserves_sources_autostart_and_cleanup() -> None:
    runtime = (ROOT / "assets/live.js").read_text()
    assert 'window.VTLive = { mount: mount }' in runtime
    assert 'hasAttribute("data-live-standalone")' in runtime
    assert 'getUserMedia' in runtime
    assert 'video.src = "/assets/street_tracking.mp4"' in runtime
    assert 'query.has("demo")' in runtime
    assert 'query.get("src") !== "sample"' in runtime
    assert 'stream.getTracks()' in runtime
    assert 'cancelAnimationFrame(animationFrame)' in runtime
    assert 'removeEventListener("click", onStart)' in runtime


def test_react_adapter_reuses_the_existing_tracker_engine() -> None:
    loader = (ROOT / "src/features/live-tracker/runtime.ts").read_text()
    page = (ROOT / "src/features/live-tracker/LiveTracker.tsx").read_text()
    tracker = (ROOT / "assets/tracker.js").read_text()
    assert 'loadScript("/assets/tracker.js"' in loader
    assert "ByteTracker" not in page
    assert "function ByteTracker" in tracker
    assert "function hungarian" in tracker
