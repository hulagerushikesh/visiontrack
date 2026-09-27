"""Keep the first benchmark explorer slice read-only and evidence-linked."""

import json
from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_benchmark_explorer_route_uses_react_without_replacing_legacy_reports() -> None:
    app = (ROOT / "src/App.tsx").read_text()
    deployment = json.loads((ROOT / "vercel.json").read_text())
    routes = {route["src"]: route["dest"] for route in deployment["routes"]}

    assert "BenchmarkExplorer" in app
    assert "path==='/benchmark/explorer'?<BenchmarkExplorer/>" in app
    assert "['Results','/benchmark/explorer']" in app
    assert routes["/benchmark/explorer/?"] == "/app/index.html"
    assert routes["/benchmark/?"] == "/web/benchmark.html"


def test_benchmark_sample_is_tied_to_the_checked_in_research_artifact() -> None:
    sample = json.loads(
        (ROOT / "src/features/benchmark-explorer/sample.json").read_text()
    )
    source = (ROOT / "web/benchmark.html").read_text()

    assert sample["schema_version"] == 1
    assert sample["provenance"]["source_document"] == "web/benchmark.html"
    assert sample["provenance"]["config_hash"] == "0bf2d757c381"
    assert "config: 0bf2d757c381" in source
    assert [variant["name"] for variant in sample["variants"]] == [
        "sort", "deepsort", "bytetrack", "bytetrack_reid", "bytetrack_giou", "oc_sort"
    ]
    assert sample["variants"][3]["values"]["IDF1"] == {
        "mean": 0.781,
        "std": None,
        "delta": 0.002,
        "p_value": None,
        "significant": True,
    }


def test_benchmark_contract_is_strict_and_does_not_encode_a_recommendation() -> None:
    contract = (ROOT / "src/features/benchmark-explorer/contract.mjs").read_text()
    sample = (ROOT / "src/features/benchmark-explorer/sample.json").read_text()

    assert "hasExactFields" in contract
    assert "Baseline comparisons must remain a zero-delta reference row." in contract
    assert 'result.p_value !== null && result.significant !== (result.p_value < 0.05)' in contract
    assert "The report must preserve at least one explicit limitation." in contract
    assert '"recommendation"' not in sample
    assert '"winner"' not in sample


def test_benchmark_explorer_is_read_only_and_keeps_protocol_visible() -> None:
    component = (
        ROOT / "src/features/benchmark-explorer/BenchmarkExplorer.tsx"
    ).read_text()

    assert "validateBenchmarkReport(sample)" in component
    assert "Validated checked-in artifact" in component
    assert "No winner is selected automatically." in component
    assert "Read the limits first" in component
    assert '<caption className="sr-only">' in component
    assert 'scope="col"' in component
    assert 'scope="row"' in component
    assert 'href="/benchmark"' in component
    assert 'type="file"' not in component
    assert "fetch(" not in component
