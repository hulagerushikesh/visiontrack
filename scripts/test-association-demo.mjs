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
  let source
  try { source = await readFile(new URL(`../src/features/reliability-lab/${name}.${extension}`, import.meta.url), "utf8") }
  catch (error) {
    if (extension !== "ts" || error.code !== "ENOENT") throw error
    extension = "tsx"
    source = await readFile(new URL(`../src/features/reliability-lab/${name}.${extension}`, import.meta.url), "utf8")
  }
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
const { AssociationDemoReader } = await import(await moduleUrl("association-demo"))
const { default: Lesson, AssociationLessonStep, AssociationLessonContent } = await import(await moduleUrl("AssociationLesson", "tsx"))
const [reportText, traceText, explanationText] = await Promise.all(["report.json", "initiation-trace.json", "association.json"].map(name => readFile(new URL(`../src/features/reliability-lab/association-demo/${name}`, import.meta.url), "utf8")))
const texts = { reportText, traceText, explanationText }
const sha = text => createHash("sha256").update(text).digest("hex")
assert.deepEqual(Object.values(texts).map(sha), [
  "3830be7a5876915a7756b7dcc6d5b1262861f81cba906e0179be57e073ca3692",
  "1cc88cfc764176ca9591d9ee6ba885746e3f0d4988e753a89aed01d8d3cc793c",
  "0d184dd7981b53bce09d05471f3f33752fc4a6385a6517a151f6c6055ad2e00a",
])
const reader = new AssociationDemoReader()
const result = await reader.read(async () => texts)
assert.equal(result.kind, "ready", result.message)
const { demo } = result
const pair = demo.explanation.stages[2].pair
assert.deepEqual(pair.failed_gates, ["mahalanobis"])
assert.equal(pair.iou, 0.9047619047619048)
assert.equal(pair.minimum_iou, 0.3)
assert.equal(pair.mahalanobis_squared, 132231.4049586777)
assert.equal(pair.mahalanobis_limit, 9.4877)
assert.equal(pair.class_mismatch, false)
assert.equal(pair.outcome, "blocked_by_gate")
assert.equal(demo.trace.config.kf_noise_scale, 0.001)
assert.deepEqual(demo.trace.frames[0].tracks.map(t => [t.track_id, t.state, t.event]), [[1, "deleted", "deleted_unconfirmed"], [2, "tentative", "born"]])
assert.deepEqual(demo.trace.frames[0].public_track_ids, [])
assert.equal(demo.explanation.accuracy_claim, false)
assert.equal(demo.explanation.physical_identity_verified, false)
assert.equal(demo.report.media_evidence.image_artifacts, 0)

for (const key of Object.keys(texts)) {
  for (const value of ["", "{}", "bad JSON", texts[key].replace('"run_id":"', '"run_id":"0'), "x".repeat((key === "explanationText" ? 1 : 16) * 1024 * 1024 + 1)]) {
    assert.equal((await reader.read(async () => ({ ...texts, [key]: value }))).kind, "error", key)
  }
}
const releasedTexts = await Promise.all(["report.json", "initiation-trace.json"].map(name => readFile(new URL(`../src/features/reliability-lab/demo/${name}`, import.meta.url), "utf8")))
assert.equal((await reader.read(async () => ({ ...texts, reportText: releasedTexts[0], traceText: releasedTexts[1] }))).kind, "error", "Different valid teaching records cannot change this lesson")
assert.equal((await reader.read(async () => { throw new Error("Missing lesson chunk") })).kind, "error")

const delayed = () => { let resolve, reject; const promise = new Promise((a, b) => { resolve = a; reject = b }); return { promise, resolve, reject } }
for (const action of ["close", "report-change", "unmount", "restart", "late-failure"]) {
  const wait = delayed()
  const pending = reader.read(() => wait.promise)
  if (action === "restart") assert.equal((await reader.read(async () => texts)).kind, "ready")
  else reader.cancel()
  if (action === "late-failure") wait.reject(new Error("Stale failure"))
  else wait.resolve(texts)
  assert.equal(await pending, null, action)
}

// Exercise cancellation within each real reader's fingerprint/lineage hashing.
const originalMethod = crypto.subtle.digest
const originalDigest = originalMethod.bind(crypto.subtle)
let total = 0
crypto.subtle.digest = async (...args) => { total++; return originalDigest(...args) }
assert.equal((await reader.read(async () => texts)).kind, "ready")
crypto.subtle.digest = originalMethod
assert.ok(total >= 5)
for (let stopAt = 1; stopAt <= total; stopAt++) {
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
    assert.equal(await pending, null, `hash ${stopAt}`)
  } finally { crypto.subtle.digest = originalMethod }
}
assert.equal((await reader.read(async () => texts)).kind, "ready", "Cancel does not poison a new request")

const render = (component, props) => renderToStaticMarkup(createElement(component, props))
const before = JSON.stringify(demo)
const closed = render(Lesson)
assert.match(closed, /Explain a match failure/)
assert.match(closed, /aria-expanded="false"/)
assert.doesNotMatch(closed, /132231|Step 1 of 3|type="file"|<img|<video|<canvas/)
for (let step = 0; step < 3; step++) {
  const html = render(AssociationLessonStep, { demo, step })
  assert.match(html, new RegExp(`Step ${step + 1} of 3`))
  assert.match(html, /aria-live="polite"/)
  if (step === 0) assert.match(html, /0.9047619047619048 ≥ 0.3 required · Passed/)
  if (step === 1) { assert.match(html, /132231.4049586777 &gt; 9.4877 allowed · Failed/); assert.match(html, /not a distance in pixels/); assert.match(html, /0.001/) }
  if (step === 2) { assert.match(html, /ID 1 deleted · ID 2 tentative · 0 public tracks/); assert.match(html, /No Human review decision is required/); assert.match(html, /does not show that disabling/) }
}
const content = render(AssociationLessonContent, { demo })
assert.match(content, /disabled=""[^>]*>Previous step/)
assert.match(content, /Next step/)
assert.match(content, /Optional: inspect the saved numbers and timeline/)
assert.match(content, /separate from your selected Lab report/)
assert.match(content, /Pair blocked by a gate/)
assert.match(content, /No public tracks/)
assert.doesNotMatch(content, /type="file"|BUNDLE_PATH|<img|<video|<canvas|<iframe/)
assert.equal(JSON.stringify(demo), before)

// Render the actual application composition, without starting a DOM or browser.
const cache = new URL("../node_modules/.cache/", import.meta.url)
await mkdir(cache, { recursive: true })
const scratch = await mkdtemp(fileURLToPath(new URL("association-demo-", cache)))
try {
  const { build } = await import("vite")
  await build({ logLevel: "silent", build: { ssr: "src/features/reliability-lab/ReliabilityLab.tsx", outDir: scratch, copyPublicDir: false, rollupOptions: { output: { entryFileNames: "lab.mjs" } } } })
  const { default: Lab, LabReport } = await import(pathToFileURL(`${scratch}/lab.mjs`).href)
  assert.match(render(Lab), /Optional prepared match failure lesson/)
  // Beginner confirmation remains a separate, unchanged lesson.
  const { GuidedDemoReader } = await import(await moduleUrl("guided-demo"))
  const guided = await new GuidedDemoReader().read(async () => ({ reportText: releasedTexts[0], traceText: releasedTexts[1] }))
  assert.equal(guided.kind, "ready")
  const html = render(LabReport, { report: guided.demo.report, origin: { kind: "demo", trace: guided.demo.trace } })
  assert.match(html, /Guided step 1 of 3/)
  assert.doesNotMatch(html, /Optional prepared match failure lesson|BUNDLE_PATH|Pair blocked by a gate/)
} finally { await rm(scratch, { recursive: true, force: true }) }

console.log(`Prepared match-failure lesson passed: frozen Python records, real three-record validation, refusal/replacement, cancellation at all ${total} hash stages and rendered lesson/application contracts. No browser interaction or visual QA.`)
