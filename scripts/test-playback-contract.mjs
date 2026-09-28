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
import { verifyPlaybackLaneFiles } from "../src/features/reliability-lab/playback-media.mjs"

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

const png = new Uint8Array(33)
png.set([137, 80, 78, 71, 13, 10, 26, 10], 0)
new DataView(png.buffer).setUint32(8, 13)
png.set([73, 72, 68, 82], 12)
new DataView(png.buffer).setUint32(16, 2)
new DataView(png.buffer).setUint32(20, 2)
const pngHash = await sha256Text(String.fromCharCode(...png))
const digest = await globalThis.crypto.subtle.digest("SHA-256", png)
const expectedHash = Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("")
assert.notEqual(pngHash, expectedHash, "binary hashing must not use text encoding")
const mediaLane = {
  variant: "candidate",
  run_id: "9".repeat(64),
  frames: [{ status: "available", relative_path: "runs/candidate/evidence/event/frame-000001.png", image_sha256: expectedHash }],
}
const file = { name: "frame-000001.png", type: "image/png", size: png.length, arrayBuffer: async () => png.buffer }
const verifiedMedia = await verifyPlaybackLaneFiles([file], mediaLane)
assert.equal(verifiedMedia.files.get(mediaLane.frames[0].relative_path), file)
await assert.rejects(() => verifyPlaybackLaneFiles([{ ...file, name: "wrong.png" }], mediaLane), /exactly match/)
await assert.rejects(() => verifyPlaybackLaneFiles([{ ...file, arrayBuffer: async () => new Uint8Array(33).buffer }], mediaLane), /SHA-256/)

console.log(`Playback contract conformance passed for ${fixture.vectors.length} vectors, ${invalid.length} invalid records, ${invalidLineage.length} invalid lineages, and verified local PNG selection.`)
