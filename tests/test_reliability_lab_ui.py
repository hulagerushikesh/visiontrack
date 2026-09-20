"""Keep the React Reliability Lab aligned with the verified report boundary."""
from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_lab_route_is_deployed_and_uses_shared_navigation() -> None:
    app = (ROOT / "src" / "App.tsx").read_text()
    standalone_nav = (ROOT / "assets" / "site.js").read_text()
    deployment = (ROOT / "vercel.json").read_text()

    assert "ReliabilityLab" in app
    assert "path==='/lab'?<ReliabilityLab/>" in app
    assert "['Lab','/lab']" in app
    assert '["Lab", "/lab"]' in standalone_nav
    assert '"src": "/lab/?", "dest": "/app/index.html"' in deployment


def test_report_types_and_runtime_states_are_explicit() -> None:
    types = (ROOT / "src/features/reliability-lab/types.ts").read_text()
    component = (ROOT / "src/features/reliability-lab/ReliabilityLab.tsx").read_text()

    assert "interface ReliabilityReport" in types
    assert 'schema_version: 1' in types
    assert 'kind: "unsupported"' in types
    assert 'kind: "missing"' in types
    assert "parseReportModel" in types
    assert 'kind: "loading"' in component
    assert "Unsupported report version" in component
    assert "Verified evidence is missing" in component
    assert "No measured failures" in component


def test_lab_ui_keeps_evidence_and_identity_boundaries_visible() -> None:
    component = (ROOT / "src/features/reliability-lab/ReliabilityLab.tsx").read_text()
    fixture = (ROOT / "src/features/reliability-lab/fixture.ts").read_text()

    assert "Demonstration fixture · illustrative data" in component
    assert "The Python pipeline remains the source of truth" in component
    assert "same correspondence as the published metrics" in component
    assert "Variant selection is not enabled" in component
    assert "Track IDs are run-local and are not persistent person identities" in fixture
    assert "satisfies ReliabilityReport" in fixture
    assert '<caption className=' in component
    assert 'scope="col"' in component
    assert 'scope="row"' in component
