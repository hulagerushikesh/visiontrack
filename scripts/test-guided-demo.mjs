import assert from "node:assert/strict"
import { createHash } from "node:crypto"
import { mkdir, mkdtemp, readFile, rm } from "node:fs/promises"
import { fileURLToPath, pathToFileURL } from "node:url"
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
const { GuidedDemoReader } = await import(await moduleUrl("guided-demo"))
const { default: Inspector, GuidedInitiationStep, InitiationFrameView } = await import(await moduleUrl("InitiationInspector", "tsx"))
const [reportText, traceText] = await Promise.all(["report.json", "initiation-trace.json"].map(name =>
  readFile(new URL(`../src/features/reliability-lab/demo/${name}`, import.meta.url), "utf8")))
const texts = { reportText, traceText }
const sha = text => createHash("sha256").update(text).digest("hex")
assert.equal(sha(reportText), "8d4551ee789687bdab3126b5ac6e1e9ee2df7545a234006467cc7869548c007a")
assert.equal(sha(traceText), "b7c2317fa61cd912ca5ca1b1ffa4796f24b2e2fb1e69691e5a07c51965881393")
const reader = new GuidedDemoReader()
const result = await reader.read(async () => texts)
assert.equal(result.kind, "ready", result.message)
const { report, trace } = result.demo
assert.equal(trace.producer.visiontrack, "0.4.0")
assert.equal(trace.accuracy_claim, false)
assert.equal(trace.physical_identity_verified, false)
assert.equal(report.failure_event_total, 64)
assert.equal(report.experiment.frame_range.end, 48)
assert.equal(report.media_evidence.image_artifacts, 0)
for (const variant of report.variants) {
  assert.equal(variant.metrics.FN, 23)
  assert.equal(variant.metrics.FP, 0)
  assert.equal(variant.metrics.IDSW, 0)
}
const track = index => trace.frames[index].tracks.find(t => t.track_id === 1)
assert.deepEqual([0, 1, 2].map(i => track(i).hits), [1, 2, 3])
assert.deepEqual([0, 1, 2].map(i => track(i).state), ["tentative", "tentative", "confirmed"])
assert.deepEqual(trace.frames.slice(0, 3).map(f => f.public_track_ids), [[], [], [1]])

for (const altered of [
  { ...texts, reportText: "bad JSON" },
  { ...texts, reportText: reportText.replace('"report_id":"', '"report_id":"0') },
  { ...texts, traceText: traceText.replace('"n_init":3', '"n_init":4') },
  { ...texts, traceText: "{}" },
  { ...texts, traceText: "" },
  { ...texts, traceText: "x".repeat(16 * 1024 * 1024 + 1) },
]) assert.equal((await reader.read(async () => altered)).kind, "error")
assert.equal((await reader.read(async () => { throw new Error("Missing chunk") })).kind, "error")

// A separately valid report/trace pair cannot silently change the fixed lesson.
const vectors = JSON.parse(await readFile(new URL("../tests/fixtures/lab_initiation_conformance.json", import.meta.url), "utf8"))
assert.equal((await reader.read(async () => ({ reportText: vectors.report_json, traceText: vectors.vectors[0].trace_json }))).kind, "error")
assert.equal((await reader.read(async () => ({ ...texts, traceText: vectors.vectors[0].trace_json }))).kind, "error")

const delayed = () => { let resolve, reject; const promise = new Promise((a, b) => { resolve = a; reject = b }); return { promise, resolve, reject } }
for (const action of ["return-to-sample", "import-local-file", "new-demo", "unmount", "late-load-failure"]) {
  const wait = delayed()
  const pending = reader.read(() => wait.promise)
  if (action === "new-demo") assert.equal((await reader.read(async () => texts)).kind, "ready")
  else reader.cancel()
  if (action === "late-load-failure") wait.reject(new Error("Old chunk failed"))
  else wait.resolve(texts)
  assert.equal(await pending, null, action)
}

// Cancel during either report or trace hashing, not just during asset loading.
const originalMethod = crypto.subtle.digest
const originalDigest = originalMethod.bind(crypto.subtle)
for (const stopAt of [1, 2]) {
  const started = delayed(), finish = delayed()
  let calls = 0
  crypto.subtle.digest = async (...args) => {
    const hash = await originalDigest(...args)
    if (++calls === stopAt) { started.resolve(); await finish.promise }
    return hash
  }
  try {
    const pending = reader.read(async () => texts)
    await started.promise
    reader.cancel()
    finish.resolve()
    assert.equal(await pending, null)
  } finally { crypto.subtle.digest = originalMethod }
}

const render = (component, props) => renderToStaticMarkup(createElement(component, props))
const before = JSON.stringify(result.demo)
const demo = render(Inspector, { report, enabled: true, initialTrace: trace })
assert.match(demo, /Guided synthetic example/)
assert.match(demo, /Guided step 1 of 3/)
assert.match(demo, /not running inference or watching footage/)
assert.doesNotMatch(demo, /type="file"|Close trace|BUNDLE_PATH/)
for (let i = 0; i < 3; i++) {
  const lesson = render(GuidedInitiationStep, { frameIndex: i })
  assert.match(lesson, new RegExp(`Guided step ${i + 1} of 3`))
  assert.match(lesson, /aria-live="polite"/)
  if (i === 2) assert.match(lesson, /no decision is required/)
  const actual = render(InitiationFrameView, { frame: trace.frames[i] })
  assert.match(actual, i < 2 ? /No public tracks/ : /ID 1/)
}
assert.match(render(GuidedInitiationStep, { frameIndex: 3 }), /Optional further exploration/)
assert.equal(JSON.stringify(result.demo), before)

// Render the actual composed screen in each origin mode. This is component
// contract coverage, not browser interaction or visual QA. Vite resolves the
// real application aliases/raw assets; no DOM, server or browser is started.
const cache = new URL("../node_modules/.cache/", import.meta.url)
await mkdir(cache, { recursive: true })
const scratch = await mkdtemp(fileURLToPath(new URL("guided-demo-", cache)))
try {
  const { build } = await import("vite")
  await build({ logLevel: "silent", build: {
    ssr: "src/features/reliability-lab/ReliabilityLab.tsx", outDir: scratch,
    copyPublicDir: false,
    rollupOptions: { output: { entryFileNames: "lab.mjs" } },
  } })
  const { LabReport, ImportControls } = await import(pathToFileURL(`${scratch}/lab.mjs`).href)
  const demoScreen = render(LabReport, { report, origin: { kind: "demo", trace } })
  assert.match(demoScreen, /Guided demo · synthetic data/)
  assert.match(demoScreen, /Guided step 1 of 3/)
  assert.ok(demoScreen.indexOf('id="initiation-title"') < demoScreen.indexOf('id="metrics-title"'))
  assert.match(demoScreen, /You can finish here/)
  assert.doesNotMatch(demoScreen, /Select decision.json|Preview exact decision|Import initiation trace|name="decision-status"|Private local import/)
  const localScreen = render(LabReport, { report, origin: { kind: "file", filename: "report.json" } })
  assert.match(localScreen, /Private local import · content fingerprint checked/)
  assert.match(localScreen, /Select decision.json/)
  assert.match(localScreen, /Preview exact decision/)
  assert.match(localScreen, /Import initiation trace/)
  assert.doesNotMatch(localScreen, /Guided step 1 of 3/)
  const sampleScreen = render(LabReport, { report, origin: { kind: "sample" } })
  assert.match(sampleScreen, /Demonstration fixture · illustrative data/)
  assert.doesNotMatch(sampleScreen, /Preview exact decision|Guided step 1 of 3/)
  const callbacks = { onDemo() {}, onSample() {}, onImport() {} }
  const initial = render(ImportControls, { origin: { kind: "sample" }, loading: false, ...callbacks })
  assert.match(initial, /Try guided demo/)
  const pending = render(ImportControls, { origin: { kind: "sample" }, loading: true, ...callbacks })
  assert.match(pending, /Return to sample/)
  assert.match(pending, /disabled=""[^>]*>Checking guided demo/)
  const ready = render(ImportControls, { origin: { kind: "demo", trace }, loading: false, ...callbacks })
  assert.match(ready, /Guided synthetic demo · VisionTrack 0.4.0/)
  assert.match(ready, /Return to sample/)
  assert.match(ready, /Import report.json/)
  assert.equal(JSON.stringify(result.demo), before)
} finally { await rm(scratch, { recursive: true, force: true }) }
console.log("Guided demo passed: released bytes, real report/trace readers, tied metrics, lifecycle lesson, invalid pair rejection, cancellation during load/hash and composed sample/demo/local controls.")
