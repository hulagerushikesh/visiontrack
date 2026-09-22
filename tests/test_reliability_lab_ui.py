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
    assert "Automatic selection is not enabled" in component
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
    assert "const failures = value.failures" in types
    assert "Failure event totals do not match the verified variant evidence." in types
    assert "The human decision boundary is missing or invalid." in types
    assert "The report must state at least one non-empty limitation." in types


def test_failure_explorer_filters_only_displayed_report_events() -> None:
    component = (ROOT / "src/features/reliability-lab/ReliabilityLab.tsx").read_text()

    assert "function FailureExplorer" in component
    assert 'id="failure-variant"' in component
    assert 'id="failure-type"' in component
    assert 'id="failure-frame"' in component
    assert "report.failures.filter" in component
    assert "matching displayed" in component
    assert "never recalculate metrics or change the source artifacts" in component
    assert "Reset filters" in component


def test_failure_explorer_exposes_accessible_read_only_detail() -> None:
    component = (ROOT / "src/features/reliability-lab/ReliabilityLab.tsx").read_text()

    assert 'aria-live="polite"' in component
    assert 'aria-controls="failure-event-detail"' in component
    assert 'aria-pressed={selectedEventId === failure.event_id}' in component
    assert 'id="failure-event-detail"' in component
    assert "Recorded context" in component
    assert "Event fingerprint" in component
    assert "Run fingerprint" in component
    assert "does not infer a persistent person identity" in component


def test_lab_surfaces_media_availability_and_privacy_before_local_reveal() -> None:
    component = (ROOT / "src/features/reliability-lab/ReliabilityLab.tsx").read_text()
    fixture = (ROOT / "src/features/reliability-lab/fixture.ts").read_text()

    assert "Image evidence" in component
    assert "verified local" in component
    assert "Privacy:" in component
    assert "Report metadata does not contain image bytes." in component
    assert "No image URL exists until a verified image is deliberately revealed." in component
    assert 'status: "available"' in fixture
    assert 'privacy: ["synthetic"]' in fixture


def test_lab_import_strictly_validates_optional_media_metadata() -> None:
    types = (ROOT / "src/features/reliability-lab/types.ts").read_text()

    assert "function isMediaEvidence" in types
    assert "One or more failure events have invalid media-evidence metadata." in types
    assert "The report media-evidence summary is invalid." in types
    assert 'images_embedded: false' in types
    assert "failure.media_evidence === undefined" in types


def test_lab_evidence_picker_verifies_files_without_upload_or_directory_scan() -> None:
    component = (ROOT / "src/features/reliability-lab/ReliabilityLab.tsx").read_text()
    evidence = (ROOT / "src/features/reliability-lab/evidence.ts").read_text()

    assert "Select evidence files" in component
    assert 'multiple accept="application/json,.json,image/png,.png"' in component
    assert "webkitdirectory" not in component
    assert "verifyEvidenceSelection" in component
    assert "crypto.subtle.digest" in evidence
    assert "pngDimensions" in evidence
    assert "The selected PNG filenames do not exactly match the manifest." in evidence
    assert "The manifest does not match the selected report event and source lineage." in evidence
    assert "fetch(" not in evidence
    assert "FormData" not in evidence


def test_lab_evidence_reveal_preserves_privacy_and_revokes_object_urls() -> None:
    component = (ROOT / "src/features/reliability-lab/ReliabilityLab.tsx").read_text()

    assert "Pixels remain concealed" in component
    assert "Reveal source pixels" in component
    assert "URL.createObjectURL(file)" in component
    assert "URL.revokeObjectURL(url)" in component
    assert "source_pixels" in component
    assert 'key={`${report.report_id}:${selectedEvent.event_id}`}' in component


def test_lab_decision_import_is_explicit_private_and_read_only() -> None:
    component = (ROOT / "src/features/reliability-lab/ReliabilityLab.tsx").read_text()
    decision = (ROOT / "src/features/reliability-lab/decision.ts").read_text()

    assert "function DecisionInspector" in component
    assert "Select decision.json" in component
    assert "Verified local decision" in component
    assert "Metrics above never select a winner." in component
    assert "nothing is uploaded or written into the bundle" in component
    assert "verifyDecisionFile" in component
    assert "fetch(" not in decision
    assert "FormData" not in decision
    assert "showDirectoryPicker" not in decision


def test_lab_decision_verifies_schema_fingerprint_and_full_lineage() -> None:
    decision = (ROOT / "src/features/reliability-lab/decision.ts").read_text()

    assert 'file.name !== "decision.json"' in decision
    assert "hasExactFields(value, decisionFields)" in decision
    assert "The decision structure or schema version is invalid." in decision
    assert "crypto.subtle.digest" in decision
    assert "The decision fingerprint does not match its content." in decision
    assert "decision.experiment_id !== report.experiment.experiment_id" in decision
    assert "decision.source_id !== report.source.source_id" in decision
    assert "decision.comparison_id !== report.comparison_id" in decision
    assert "decision.report_id !== report.report_id" in decision
    assert "The accepted variant is not present in the active report." in decision


def test_lab_decision_ui_has_missing_invalid_and_verified_states() -> None:
    component = (ROOT / "src/features/reliability-lab/ReliabilityLab.tsx").read_text()

    assert 'kind: "idle"' in component
    assert 'kind: "verifying"' in component
    assert 'kind: "error"; message: string' in component
    assert 'kind: "ready"; result: VerifiedDecision' in component
    assert "Decision not opened." in component
    assert "All variants rejected" in component
    assert "accepted" in component
    assert "Read only" in component


def test_lab_decision_draft_has_no_automatic_outcome_or_variant() -> None:
    component = (ROOT / "src/features/reliability-lab/ReliabilityLab.tsx").read_text()

    assert 'useState<"" | "accepted" | "rejected_all">("")' in component
    assert 'useState("")' in component
    assert '<option value="">Choose a verified variant</option>' in component
    assert "Nothing is preselected." in component
    assert "Metrics above never select a winner." in component
    assert 'canDraft={origin.kind === "file"}' in component
    assert "The illustrative sample cannot produce an audit record." in component


def test_lab_decision_draft_requires_preview_before_local_download() -> None:
    component = (ROOT / "src/features/reliability-lab/ReliabilityLab.tsx").read_text()
    decision = (ROOT / "src/features/reliability-lab/decision.ts").read_text()

    assert "createDecisionDraft" in component
    assert "Preview exact decision" in component
    assert "Exact decision preview" in component
    assert "Confirm and download decision.json" in component
    assert 'link.download = "decision.json"' in component
    assert "serializeDecision(decision)" in component
    assert "Browser download only · bundle unchanged" in component
    assert "URL.revokeObjectURL(url)" in component
    assert "export function serializeDecision" in decision


def test_lab_decision_draft_matches_immutable_contract_and_blocks_replacement() -> None:
    component = (ROOT / "src/features/reliability-lab/ReliabilityLab.tsx").read_text()
    decision = (ROOT / "src/features/reliability-lab/decision.ts").read_text()
    types = (ROOT / "src/features/reliability-lab/types.ts").read_text()

    assert 'report.decision.status !== "not_selected"' in decision
    assert "Choose whether to accept one variant or reject all variants." in decision
    assert "Choose one verified variant to accept." in decision
    assert "Rationale must be 1–5000 characters" in decision
    assert "Author must be 1–200 characters" in decision
    assert "Decision time must be a valid UTC timestamp." in decision
    assert 'decision.reason !== "requires_human_acceptance_decision"' in types
    assert '(state.kind === "idle" || state.kind === "error")' in component
    assert 'state.kind !== "ready" && <label' in component
    assert 'state.kind === "ready"' in component
