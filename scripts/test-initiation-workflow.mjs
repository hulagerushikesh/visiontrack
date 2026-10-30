import assert from "node:assert/strict"
import { createHash } from "node:crypto"
import { spawnSync } from "node:child_process"
import { mkdtemp, readFile, rm } from "node:fs/promises"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { createElement } from "react"
import { renderToStaticMarkup } from "react-dom/server"
import ts from "typescript"

Error.stackTraceLimit = 0
const urls = new Map()
async function moduleUrl(name, extension = "ts") {
  if (urls.has(name)) return urls.get(name)
  const source = await readFile(new URL(`../src/features/reliability-lab/${name}.${extension}`, import.meta.url), "utf8")
  let code = ts.transpileModule(source, { fileName: `${name}.${extension}`, compilerOptions: {
    module: ts.ModuleKind.ES2022, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX,
  } }).outputText
  for (const dep of [...code.matchAll(/from "(\.[^\"]+)"/g)]) {
    const local = dep[1].slice(2)
    const url = local.endsWith(".mjs") ? new URL(`../src/features/reliability-lab/${local}`, import.meta.url).href : await moduleUrl(local)
    code = code.replace(`from "${dep[1]}"`, `from "${url}"`)
  }
  code = code.replace(/from "(react(?:\/jsx-runtime)?)"/g, (_, pkg) => `from "${import.meta.resolve(pkg)}"`)
  const url = `data:text/javascript;base64,${Buffer.from(code).toString("base64")}`
  urls.set(name, url)
  return url
}
const api = await import(await moduleUrl("initiation"))
const { ReportFileReader } = await import(await moduleUrl("report-import"))
const { parseReportModel } = await import(await moduleUrl("types"))
const { canonicalJson } = await import("../src/features/reliability-lab/decision-contract.mjs")
const { default: Inspector, InitiationFrameView, InitiationTimeline } = await import(await moduleUrl("InitiationInspector", "tsx"))
const fixture = JSON.parse(await readFile(new URL("../tests/fixtures/lab_initiation_conformance.json", import.meta.url), "utf8"))
const asFile = text => ({ size: Buffer.byteLength(text), text: async () => text })
const reportResult = await new ReportFileReader(parseReportModel).read(asFile(fixture.report_json))
assert.equal(reportResult.kind, "ready")
const report = reportResult.report
const text = fixture.vectors[0].trace_json
const trace = await api.verifyInitiationTrace(text, report)
for (const vector of fixture.vectors) {
  assert.deepEqual(await api.verifyInitiationTrace(vector.trace_json, report), JSON.parse(vector.trace_json), vector.name)
  assert.deepEqual(await api.verifyInitiationTrace(vector.trace_json.trimEnd(), report), JSON.parse(vector.trace_json))
}
const sha = text => createHash("sha256").update(text).digest("hex")
// Re-sign edited content while retaining the Python config tokens. This makes
// semantic and lineage rejections independent of fingerprint-mismatch checks.
function edited(mutate, { preserveConfig = true } = {}) {
  const changed = structuredClone(trace)
  mutate(changed)
  delete changed.trace_id
  const rawConfig = text.match(/"config":(\{[^}]+\}),/)[1]
  const render = value => {
    let encoded = canonicalJson(value)
    if (preserveConfig) encoded = encoded.replace(`"config":${canonicalJson(changed.config)},`, `"config":${rawConfig},`)
    return encoded
  }
  return `${render({ ...changed, trace_id: sha(render(changed)) })}\n`
}
assert.deepEqual((await api.verifyInitiationTrace(edited(() => {}), report)).frames, trace.frames)
const rejects = [
  [t => { t.schema = "visiontrack.initiation-trace/v2" }, /structure|version/],
  [t => { t.accuracy_claim = true }, /boundaries/],
  [t => { t.extra = "unknown" }, /structure/],
  [t => { t.experiment_id = "0".repeat(64) }, /active report/],
  [t => { t.source_id = "0".repeat(64) }, /active report/],
  [t => { t.run_id = "0".repeat(64) }, /active report/],
  [t => { t.variant = "absent" }, /active report/],
  [t => { t.detection_sha256 = "0".repeat(64) }, /active report/],
  [t => { t.track_sha256 = "0".repeat(64) }, /active report/],
  [t => { t.trace_frame_range.end = 201 }, /window/],
  [t => { t.frames[0].frame_index = 1 }, /frames/],
  [t => { t.frames.pop() }, /cover/],
  [t => { t.frames[0].detections[0].score = 1.1 }, /score/],
  [t => { t.frames[0].detections[0].xyxy[2] = 0 }, /box/],
  [t => { t.frames[0].detections[0].detection_index = Number.MAX_SAFE_INTEGER + 1 }, /key/],
  [t => { t.frames[0].detections[0].class_id = false }, /class/],
  [t => { t.frames[0].detections.push(t.frames[0].detections[0]) }, /key/],
  [t => { t.frames[0].detections[0].disposition = "matched_confirmed_high"; t.frames[0].detections[0].track_id = 1 }, /admission/],
  [t => { t.frames[3].tracks[0].public = true }, /output/],
  [t => { t.frames[3].public_track_ids = [1] }, /Public IDs/],
  [t => { t.frames[4].tracks[0].hits = 1 }, /history/],
  [t => { t.frames[4].tracks = []; t.frames[4].detections[0].track_id = null }, /links/],
  [t => { t.frames[7].tracks[0].time_since_update = 0 }, /output/],
  [t => { t.frames[8].tracks[0].event = "coasting" }, /event/],
  [t => { t.frames[10].tracks[0].previous_state = "deleted" }, /lifecycle/],
  [t => { t.producer.implementation_sha256 = { "../private.py": "a".repeat(64) } }, /source hashes/],
  [t => { t.limits = [] }, /limitations/],
]
for (const [mutate, expected] of rejects) await assert.rejects(api.verifyInitiationTrace(edited(mutate), report), expected)
await assert.rejects(api.verifyInitiationTrace(edited(t => { t.config.kf_noise_scale = 2 }, { preserveConfig: false }), report), /run ID/)
await assert.rejects(api.verifyInitiationTrace(text.replace('"n_init":3', '"n_init":4'), report), /fingerprint/)
await assert.rejects(api.verifyInitiationTrace(text.replace('"kf_noise_scale":1.0', '"kf_noise_scale":1'), report), /fingerprint/)
await assert.rejects(api.verifyInitiationTrace(`${text}\n`, report), /fingerprint/)
for (const duplicate of [
  text.replace('"accuracy_claim":false', '"accuracy_claim":false,"accuracy_claim":false'),
  text.replace('"max_age":1', '"max_age":1,"max_age":1'),
  text.replace('"score":0.05', '"score":0.05,"score":0.05'),
]) await assert.rejects(api.verifyInitiationTrace(duplicate, report), /Duplicate/)
const wrongReport = structuredClone(report)
wrongReport.variants[0].diagnostics.observation_count += 1
await assert.rejects(api.verifyInitiationTrace(text, wrongReport), /run ID/)
delete wrongReport.variants[0].diagnostics.observation_count
await assert.rejects(api.verifyInitiationTrace(text, wrongReport), /observation count/)
const crowded = structuredClone(trace.frames[0])
crowded.detections = Array.from({ length: 20_001 }, (_, i) => ({ ...crowded.detections[0], detection_index: i }))
await assert.rejects(api.verifyInitiationTrace(edited(t => { t.frames[0] = crowded }), report), /20,000/)

const reader = new api.InitiationFileReader()
for (const size of [0, api.maxTraceBytes + 1]) {
  let read = false
  assert.equal((await reader.read({ size, text: async () => { read = true; return text } }, report)).kind, "error")
  assert.equal(read, false)
}
assert.equal((await reader.read(asFile("invalid"), report)).kind, "error")
assert.equal((await reader.read({ size: 100, text: async () => { throw new Error("unreadable") } }, report)).kind, "error")
assert.equal((await reader.read(asFile(text), report)).kind, "ready")
const delayed = () => { let resolve, reject; const promise = new Promise((a, b) => { resolve = a; reject = b }); return { file: { size: 100, text: () => promise }, resolve, reject } }
for (const action of ["cancel", "replace", "invalid", "error"]) {
  const pending = delayed(), old = reader.read(pending.file, report)
  if (action === "cancel") reader.cancel()
  else await reader.read(asFile(action === "invalid" ? "bad" : text), report)
  if (action === "error") pending.reject(new Error("stale"))
  else pending.resolve(text)
  assert.equal(await old, null, action)
}

// Cancellation while cryptographic checks are pending must also suppress publication.
const originalMethod = crypto.subtle.digest
const originalDigest = originalMethod.bind(crypto.subtle)
let finishDigest, signalDigest
const digestStarted = new Promise(resolve => { signalDigest = resolve })
const blockedDigest = new Promise(resolve => { finishDigest = resolve })
let firstDigest = true
crypto.subtle.digest = async (...args) => {
  const result = await originalDigest(...args)
  if (firstDigest) { firstDigest = false; signalDigest(); await blockedDigest }
  return result
}
try {
  const pending = reader.read(asFile(text), report)
  // Let the read reach the first digest before superseding it.
  await digestStarted
  reader.cancel()
  finishDigest()
  assert.equal(await pending, null)
} finally { crypto.subtle.digest = originalMethod }

const render = (component, props) => renderToStaticMarkup(createElement(component, props))
for (const name of ["initiation.ts", "InitiationInspector.tsx"]) {
  const source = await readFile(new URL(`../src/features/reliability-lab/${name}`, import.meta.url), "utf8")
  assert.doesNotMatch(source, /fetch\(|XMLHttpRequest|sendBeacon|localStorage|sessionStorage|createObjectURL|showDirectoryPicker|webkitdirectory/)
}
const before = JSON.stringify(trace)
for (const frame of trace.frames) {
  const html = render(InitiationFrameView, { frame })
  assert.match(html, /1\. Detector proposals/)
  assert.match(html, /2\. Internal track state/)
  assert.match(html, /3\. Public output/)
  assert.match(html, /not personal identities/)
  assert.doesNotMatch(html, /<img|<video|<canvas|<iframe/)
}
assert.match(render(InitiationFrameView, { frame: trace.frames[3] }), /Born tentative/)
assert.match(render(InitiationFrameView, { frame: trace.frames[3] }), /No public tracks/)
assert.match(render(InitiationFrameView, { frame: trace.frames[5] }), /Confirmed now/)
assert.match(render(InitiationFrameView, { frame: trace.frames[7] }), /Coasting internally/)
assert.match(render(InitiationFrameView, { frame: trace.frames[7] }), /No public tracks/)
const timeline = render(InitiationTimeline, { trace })
assert.match(timeline, /aria-label="Initiation trace frame"/)
assert.match(timeline, /role="status" aria-live="polite"/)
assert.match(timeline, /does not rerun Python/)
assert.match(timeline, /Previous<\/button>/)
assert.match(timeline, /disabled=""/)
const sample = render(Inspector, { report, enabled: false })
assert.match(sample, /Import your local report.json first/)
assert.doesNotMatch(sample, /type="file"/)
const imported = render(Inspector, { report, enabled: true })
assert.match(imported, /Import initiation trace/)
assert.match(imported, /--end 10 --json/)
assert.match(imported, /Nothing is uploaded/)
assert.match(imported, /No second command is needed/)
assert.equal(JSON.stringify(trace), before, "Viewing never mutates a trace")

// Fresh producer integration (not just a retained vector), both presets and a
// warm-up window. No camera, model, downloads or saved output mutations.
const scratch = await mkdtemp(join(tmpdir(), "visiontrack-initiation-ui-"))
try {
  const run = spawnSync(process.env.VISIONTRACK_PYTHON || "python", ["-c", `
import hashlib,json,sys
from pathlib import Path
from visiontrack.lab import create_synthetic_lab,build_initiation_trace,canonical_json
report_path=create_synthetic_lab(Path(sys.argv[1])/'demo',with_initiation=True)
bundle=report_path.parent.parent
browser=bundle.parent/'try-in-browser'
assert (browser/'report.json').read_bytes()==report_path.read_bytes()
snapshot=lambda:{str(p.relative_to(bundle)):hashlib.sha256(p.read_bytes()).hexdigest() for p in bundle.rglob('*') if p.is_file()}
before=snapshot()
traces=[canonical_json(build_initiation_trace(bundle,variant=v,start=s,end=e))+'\\n' for v,s,e in [('bytetrack',0,48),('single-stage',0,48),('bytetrack',7,9)]]
assert before==snapshot()
print(json.dumps({'report':(browser/'report.json').read_text(),'traces':traces,
                 'prepared_trace':(browser/'initiation-trace.json').read_text()}))
`, scratch], { encoding: "utf8", timeout: 60_000 })
  assert.equal(run.status, 0, run.stderr)
  const produced = JSON.parse(run.stdout)
  const result = await new ReportFileReader(parseReportModel).read(asFile(produced.report))
  assert.equal(result.kind, "ready", result.message)
  for (const exported of produced.traces) assert.equal((await reader.read(asFile(exported), result.report)).kind, "ready")
  const prepared = await reader.read(asFile(produced.prepared_trace), result.report)
  assert.equal(prepared.kind, "ready", prepared.message)
  assert.equal(prepared.trace.frames[0].frame_index, 0)
  assert.equal(prepared.trace.frames[9].frame_index, 9)
  assert.deepEqual(prepared.trace.frames[0].public_track_ids, [])
  assert.deepEqual(prepared.trace.frames[2].public_track_ids, [1])
} finally { await rm(scratch, { recursive: true, force: true }) }
console.log("Initiation workflow passed: Python vectors, real replay, exact config/run hashing, lineage, lifecycle, bounded reads, cancellation, and rendered controls.")
