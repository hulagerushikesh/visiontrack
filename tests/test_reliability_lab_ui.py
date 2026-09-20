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


def test_lab_import_stays_private_and_can_return_to_sample() -> None:
    component = (ROOT / "src/features/reliability-lab/ReliabilityLab.tsx").read_text()

    assert 'type="file"' in component
    assert 'accept="application/json,.json"' in component
    assert "JSON.parse(await file.text())" in component
    assert "Processed only in this browser tab. Nothing is uploaded." in component
    assert "Return to sample" in component
    assert 'input.value = ""' in component
    assert "fetch(" not in component
    assert "FormData" not in component


def test_lab_import_validates_nested_evidence() -> None:
    types = (ROOT / "src/features/reliability-lab/types.ts").read_text()

    assert "Experiment provenance or frame bounds are incomplete." in types
    assert "Source evidence, hashes, or media bounds are incomplete." in types
    assert "All variants must report the same metric set." in types
    assert "failure.run_id !== runIds.get(failure.variant)" in types
    assert "Failure event totals do not match the verified variant evidence." in types
    assert "The human decision boundary is missing or invalid." in types
    assert "The report must state at least one non-empty limitation." in types
