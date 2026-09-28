"""Observable contracts for the React benchmark front door."""
import json
from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_benchmark_hub_separates_overview_from_authoritative_reports() -> None:
    page = (ROOT / "src/features/benchmark-hub/BenchmarkHub.tsx").read_text()
    app = (ROOT / "src/App.tsx").read_text()
    deployment = json.loads((ROOT / "vercel.json").read_text())
    routes = {route["src"]: route["dest"] for route in deployment["routes"]}

    assert routes["/benchmark/?"] == "/app/index.html"
    assert routes["/benchmark/synthetic/?"] == "/web/benchmark.html"
    for route in (
        "/benchmark/synthetic",
        "/benchmark/dancetrack",
        "/benchmark/dancetrack-yolox",
        "/benchmark/sportsmot",
        "/benchmark/explorer",
    ):
        assert route in page
    assert "authoritative rendered artifacts" in page
    assert "No winner is selected automatically." in page
    assert "location.pathname.startsWith('/benchmark/')" in app


def test_benchmark_hub_explains_protocol_and_dataset_boundaries() -> None:
    page = (ROOT / "src/features/benchmark-hub/BenchmarkHub.tsx").read_text()
    for phrase in (
        "Every variant receives the same detections, sequences, and seeds.",
        "Paired against baseline",
        "Wilcoxon · p&lt;0.05",
        "Config hash + source",
        "These are not one interchangeable leaderboard.",
        "detector quality",
    ):
        assert phrase in page
    assert "document.title" in page
    assert "https://visiontrack.hulage.in/benchmark" in page


def test_generated_synthetic_report_has_its_own_canonical_route() -> None:
    report = (ROOT / "web/benchmark.html").read_text()
    generator = (ROOT / "experiments/_benchmark_html.py").read_text()
    assert 'href="https://visiontrack.hulage.in/benchmark/synthetic"' in report
    assert '<a href="/benchmark/synthetic">synthetic</a>' in report
    assert 'return "/benchmark/synthetic"' in generator


def test_all_generated_reports_use_the_shared_evidence_layout() -> None:
    for name in (
        "benchmark.html",
        "benchmark-dancetrack.html",
        "benchmark-dancetrack-yolox.html",
        "benchmark-sportsmot.html",
    ):
        page = (ROOT / "web" / name).read_text()
        for contract in (
            'class="report-hero"',
            'class="report-protocol"',
            'class="report-section"',
            'class="report-reproduce"',
            'href="/benchmark/explorer"',
            "The page does not choose a recommended tracker.",
        ):
            assert contract in page


def test_generator_owns_the_report_layout_and_keeps_evidence_sections() -> None:
    generator = (ROOT / "experiments/_benchmark_html.py").read_text()
    stylesheet = (ROOT / "assets/site.css").read_text()
    for contract in (
        'class="report-hero"',
        'class="report-protocol"',
        'class="report-section"',
        'class="report-reproduce"',
        "{meta_chips}",
        "{''.join(rows)}",
        "{''.join(tax)}",
    ):
        assert contract in generator
    assert ".report-hero" in stylesheet
    assert ".report-section" in stylesheet
    assert ".report-reproduce" in stylesheet
