import assert from "node:assert/strict"
import { readFile } from "node:fs/promises"

import { sha256Canonical } from "../src/features/reliability-lab/decision-contract.mjs"
import {
  serializePlayback,
  sha256Text,
  validateFailurePlayback,
  validatePlaybackReportLineage,
  verifyFailurePlayback,
} from "../src/features/reliability-lab/playback-contract.mjs"

const fixtureUrl = new URL("../tests/fixtures/lab_playback_conformance.json", import.meta.url)
const fixture = JSON.parse(await readFile(fixtureUrl, "utf8"))

assert.equal(fixture.schema_version, 1)
for (const vector of fixture.vectors) {
  const content = { ...vector.values, schema_version: fixture.schema_version }
  const playback = { playback_id: await sha256Canonical(content), ...content }
  assert.equal(playback.playback_id, vector.playback_id, `${vector.name}: playback ID`)
  assert.deepEqual(validateFailurePlayback(playback), { valid: true }, `${vector.name}: structure`)
  assert.deepEqual(await verifyFailurePlayback(playback), { valid: true }, `${vector.name}: fingerprint`)
  const canonical = serializePlayback(playback).slice(0, -1)
  assert.equal(await sha256Text(canonical), vector.canonical_sha256, `${vector.name}: canonical bytes`)
  assert.equal(await sha256Text(`${canonical}\n`), vector.file_sha256, `${vector.name}: file bytes`)
}

const validContent = { ...fixture.vectors[0].values, schema_version: 1 }
const valid = { playback_id: await sha256Canonical(validContent), ...validContent }
const invalid = [
  { ...structuredClone(valid), playback_id: "0".repeat(64) },
  (() => { const value = structuredClone(valid); value.lanes[0].frames[0].relative_path = "https://example.com/frame.png"; return value })(),
  (() => { const value = structuredClone(valid); value.lanes[0].frames[1].privacy = "redacted"; return value })(),
  (() => { const value = structuredClone(valid); value.lanes[1].frames[1].offset_ms = 41; return value })(),
  (() => { const value = structuredClone(valid); value.lanes[1].frames.pop(); return value })(),
]
for (const [index, value] of invalid.entries()) {
  assert.equal((await verifyFailurePlayback(value)).valid, false, `invalid vector ${index}`)
}

const matchingReport = {
  report_id: valid.report_id,
  comparison_id: valid.comparison_id,
  experiment: { experiment_id: valid.experiment_id, baseline: valid.baseline },
  source: { source_id: valid.source_id, frame_count: 100 },
  variants: valid.lanes.map((lane, index) => ({
    name: lane.variant,
    baseline: index === 0,
    run_id: lane.run_id,
  })),
  failures: [{
    event_id: valid.anchor_event_id,
    variant: valid.variant,
    run_id: valid.lanes[1].run_id,
    frame_index: valid.event_frame_index,
    evidence_frames: valid.frame_range,
  }],
}
assert.deepEqual(validatePlaybackReportLineage(valid, matchingReport), { valid: true })
const invalidLineage = [
  { ...structuredClone(matchingReport), report_id: "0".repeat(64) },
  (() => { const report = structuredClone(matchingReport); report.variants[1].run_id = "0".repeat(64); return report })(),
  (() => { const report = structuredClone(matchingReport); report.failures = []; return report })(),
  (() => { const report = structuredClone(matchingReport); report.failures[0].frame_index += 1; return report })(),
]
for (const [index, report] of invalidLineage.entries()) {
  assert.equal(validatePlaybackReportLineage(valid, report).valid, false, `invalid lineage ${index}`)
}

console.log(`Playback contract conformance passed for ${fixture.vectors.length} vectors, ${invalid.length} invalid records, and ${invalidLineage.length} invalid lineages.`)
