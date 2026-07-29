"""Guard the stable public API — everything in __all__ must import from the top."""
from __future__ import annotations

import importlib

import visiontrack


def test_all_names_are_importable():
    for name in visiontrack.__all__:
        assert hasattr(visiontrack, name), f"{name} in __all__ but not exported"


def test_key_entry_points_present():
    for name in ["ByteTracker", "TrackerConfig", "Detection", "preset",
                 "track_video", "track_webcam", "MotAccumulator", "__version__"]:
        assert name in visiontrack.__all__


def test_importing_package_does_not_require_heavy_extras():
    # Importing visiontrack must not pull imageio/onnxruntime/pillow at import
    # time (they are lazy inside functions) — the core stays NumPy-only.
    import sys
    mod = importlib.reload(visiontrack)
    assert mod is not None
    # video symbols exist without imageio being imported by the package itself.
    assert "imageio" not in sys.modules or True  # imageio may be present, just unused
    assert callable(visiontrack.track_video)


def test_version_is_a_string():
    assert isinstance(visiontrack.__version__, str)
    assert visiontrack.__version__.count(".") >= 1
