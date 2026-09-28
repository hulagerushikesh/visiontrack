import assert from "node:assert/strict"
import { readFile } from "node:fs/promises"
import ts from "typescript"

import { sha256Canonical } from "../src/features/reliability-lab/decision-contract.mjs"
import {
  serializePlayback,
  validatePlaybackReportLineage,
  verifyFailurePlayback,
} from "../src/features/reliability-lab/playback-contract.mjs"
import { verifyPlaybackLaneFiles } from "../src/features/reliability-lab/playback-media.mjs"
import { nextPlaybackFrame, playbackStepDelay } from "../src/features/reliability-lab/playback-transport.mjs"

const fixtureUrl = new URL("../tests/fixtures/lab_browser_workflow.json", import.meta.url)
const fixture = JSON.parse(await readFile(fixtureUrl, "utf8"))
assert.equal(fixture.schema_version, 1)

// Execute the same report parser used by React without adding a second validator.
const reportSource = await readFile(new URL("../src/features/reliability-lab/types.ts", import.meta.url), "utf8")
const reportModule = ts.transpileModule(reportSource, {
  compilerOptions: { module: ts.ModuleKind.ES2022, target: ts.ScriptTarget.ES2022 },
}).outputText
const reportApi = await import(`data:text/javascript;base64,${Buffer.from(reportModule).toString("base64")}`)
const reportResult = reportApi.parseReportModel(structuredClone(fixture.report))
assert.equal(reportResult.kind, "ready", reportResult.message)

const playbackId = await sha256Canonical(fixture.playback_content)
const playbackFile = serializePlayback({ playback_id: playbackId, ...fixture.playback_content })
const playback = JSON.parse(playbackFile)
assert.deepEqual(await verifyFailurePlayback(playback), { valid: true })
assert.deepEqual(validatePlaybackReportLineage(playback, reportResult.report), { valid: true })

const mockFiles = (entries) => entries.map((entry) => {
  const bytes = Buffer.from(entry.base64, "base64")
  return {
    name: entry.name,
    type: entry.media_type,
    size: bytes.length,
    arrayBuffer: async () => bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength),
  }
})
for (const lane of playback.lanes) {
  const media = await verifyPlaybackLaneFiles(mockFiles(fixture.lane_files[lane.variant]), lane)
  assert.equal(media.runId, lane.run_id)
  assert.equal(media.files.size, lane.frames.filter((frame) => frame.status === "available").length)
}

assert.equal(playbackStepDelay(playback, 0, 1), 40)
assert.equal(playbackStepDelay(playback, 0, 2), 20)
assert.equal(nextPlaybackFrame(playback.frame_range, 0), 1)
assert.equal(nextPlaybackFrame(playback.frame_range, 1), 2)
assert.equal(nextPlaybackFrame(playback.frame_range, 2), 2, "transport stops at the verified boundary")
assert.equal(playback.lanes[1].frames[1].privacy, "source_pixels")
assert.equal(playback.lanes[0].frames[1].status, "missing")

const mediaSource = await readFile(new URL("../src/features/reliability-lab/playback-media.mjs", import.meta.url), "utf8")
assert.equal(mediaSource.includes("createObjectURL"), false, "verification cannot reveal pixels")
assert.equal(mediaSource.includes("fetch("), false, "verification cannot fetch media")

console.log("Synthetic browser playback workflow accepted report, playback, both PNG lanes, timing, privacy, and bounded transport.")
