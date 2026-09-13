"""Keep the public learning hub and its deployed routes connected."""

from __future__ import annotations

import json
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class _Links(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hrefs: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            values = dict(attrs)
            if values.get("href"):
                self.hrefs.add(values["href"])


def _hrefs(path: Path) -> set[str]:
    parser = _Links()
    parser.feed(path.read_text())
    return parser.hrefs


def test_learning_hub_exposes_all_three_paths() -> None:
    hrefs = _hrefs(ROOT / "web" / "teaching.html")
    assert "/study" in hrefs
    assert "/roadmap" in hrefs
    assert (
        "https://github.com/hulagerushikesh/visiontrack-cpp/tree/main/learning"
        in hrefs
    )


def test_learning_routes_point_to_committed_modules() -> None:
    config = json.loads((ROOT / "vercel.json").read_text())
    routes = {route["src"]: route["dest"] for route in config["routes"]}
    expected = {
        "/study/?": "/learning/LEARNING_PATH.html",
        "/roadmap/?": "/learning/CV_ROADMAP.html",
    }
    for route, destination in expected.items():
        assert routes[route] == destination
        assert (ROOT / destination.lstrip("/")).is_file()


def test_learning_index_links_to_both_local_modules() -> None:
    index = (ROOT / "learning" / "README.md").read_text()
    assert "[VisionTrack study guide](LEARNING_PATH.html)" in index
    assert "[Computer-vision roadmap](CV_ROADMAP.html)" in index


def test_study_guide_links_core_concepts_to_both_implementations() -> None:
    hrefs = _hrefs(ROOT / "learning" / "LEARNING_PATH.html")
    expected = {
        "https://github.com/hulagerushikesh/visiontrack/blob/main/src/visiontrack/core/geometry.py",
        "https://github.com/hulagerushikesh/visiontrack/blob/main/src/visiontrack/core/kalman.py",
        "https://github.com/hulagerushikesh/visiontrack/blob/main/src/visiontrack/core/assignment.py",
        "https://github.com/hulagerushikesh/visiontrack/blob/main/src/visiontrack/tracking/tracker.py",
        "https://github.com/hulagerushikesh/visiontrack-cpp/blob/main/core/geometry.hpp",
        "https://github.com/hulagerushikesh/visiontrack-cpp/blob/main/core/kalman.hpp",
        "https://github.com/hulagerushikesh/visiontrack-cpp/blob/main/core/assignment.hpp",
        "https://github.com/hulagerushikesh/visiontrack-cpp/blob/main/core/tracker.hpp",
    }
    assert expected <= hrefs


def test_study_guide_links_all_dataset_free_exercises() -> None:
    hrefs = _hrefs(ROOT / "learning" / "LEARNING_PATH.html")
    base = "https://github.com/hulagerushikesh/visiontrack/blob/main/learning/EXERCISES.md"
    assert {
        f"{base}#1-geometry-overlap",
        f"{base}#2-kalman-predict-and-update",
        f"{base}#3-global-assignment",
        f"{base}#4-track-lifecycle",
    } <= hrefs


def test_study_guide_links_parity_capstone() -> None:
    hrefs = _hrefs(ROOT / "learning" / "LEARNING_PATH.html")
    assert (
        "https://github.com/hulagerushikesh/visiontrack/blob/main/learning/PARITY_CAPSTONE.md"
        in hrefs
    )
