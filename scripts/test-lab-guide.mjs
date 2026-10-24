import assert from "node:assert/strict"
import { readFile } from "node:fs/promises"
import { createElement } from "react"
import { renderToStaticMarkup } from "react-dom/server"
import ts from "typescript"

async function browserModule(name, extension) {
  const source = await readFile(new URL(`../src/features/reliability-lab/${name}.${extension}`, import.meta.url), "utf8")
  const compiled = ts.transpileModule(source, {
    fileName: `${name}.${extension}`,
    compilerOptions: { module: ts.ModuleKind.ES2022, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX },
  }).outputText.replace(/from "(react(?:\/jsx-runtime)?)"/g, (_, name) => `from "${import.meta.resolve(name)}"`)
  return import(`data:text/javascript;base64,${Buffer.from(compiled).toString("base64")}`)
}

const { default: LabGuide, lessonSteps, TrackingLesson } = await browserModule("LabGuide", "tsx")
const guide = renderToStaticMarkup(createElement(LabGuide))
assert.match(guide, /<details open=""/)
assert.match(guide, /it does not start your webcam or fix the tracker/)
assert.match(guide, /separate from the report below/)
assert.match(guide, /You do not need to make a decision to explore/)
assert.match(guide, /aria-controls="tracking-lesson-panel"/)
assert.equal((guide.match(/aria-pressed="true"/g) ?? []).length, 1)
assert.equal((guide.match(/aria-pressed="false"/g) ?? []).length, 2)
assert.match(guide, /href="#lab-title"/)
assert.doesNotMatch(guide, /<input|<video|<iframe|<img|<form|https:\/\//)

for (const [step, item] of lessonSteps.entries()) {
  const rendered = renderToStaticMarkup(createElement(TrackingLesson, { step }))
  assert.ok(rendered.includes(item.expected))
  assert.ok(rendered.includes(item.observed))
  assert.match(rendered, /aria-live="polite"/)
  assert.match(rendered, /Tracking IDs are temporary labels, not personal identities/)
  assert.match(rendered, /not footage, a result from your report/)
  if (step === 0) assert.equal((rendered.match(/>ID 7</g) ?? []).length, 2)
  if (step === 1) {
    assert.doesNotMatch(rendered, />ID \d+</)
    assert.match(rendered, /does not, by itself, prove a tracking mistake/)
  }
  if (step === 2) {
    assert.equal((rendered.match(/>ID 7</g) ?? []).length, 1)
    assert.equal((rendered.match(/>ID 12</g) ?? []).length, 1)
    assert.match(rendered, /illustrates an ID switch/)
  }
}

const { failureExplanations, explainFailure, explanationFor } = await browserModule("explanations", "ts")
const fixture = JSON.parse(await readFile(new URL("../tests/fixtures/lab_browser_workflow.json", import.meta.url), "utf8"))
for (const [type, explanation] of Object.entries(failureExplanations)) {
  const event = { ...fixture.report.failures[0], event_type: type, variant: "example-variant", frame_index: 0 }
  assert.equal(explainFailure(event), `example-variant, frame 0: ${explanation.meaning}`)
  assert.ok(explanation.label.length > 0)
  assert.doesNotMatch(explainFailure(event), /detector failed|recognizes|camera|pillar/)
}
assert.equal(Object.keys(failureExplanations).length, 4)
assert.match(failureExplanations.miss.meaning, /under the evaluation rules/)
assert.match(failureExplanations.fragmentation.meaning, /previously matched reference object is now unmatched/)
assert.match(failureExplanations.false_positive.meaning, /reference labels under the evaluation rules/)
const resumed = { ...fixture.report.failures[0], event_type: "fragmentation", context: { evaluator: "visiontrack.metrics/v2" } }
assert.match(explainFailure(resumed), /matched again after an interruption/)
assert.equal(explanationFor(resumed).label, "Tracking resumed after an interruption")

const { default: EvidenceProgress } = await browserModule("EvidenceProgress", "tsx")
const progress = (props) => renderToStaticMarkup(createElement(EvidenceProgress, props))
for (const status of ["idle", "verifying", "error"]) {
  const rendered = progress({ status, listedCount: 2 })
  assert.match(rendered, /1\. Listed in the report/)
  assert.match(rendered, />2 images</)
  assert.match(rendered, /2\. Checked in this browser/)
  assert.match(rendered, /3\. Pictures revealed/)
  assert.equal((rendered.match(/>0 of 2</g) ?? []).length, 2)
  assert.match(rendered, /role="status" aria-live="polite"/)
  assert.doesNotMatch(rendered, /<img|<input|<video|blob:|https:\/\//)
}
assert.match(progress({ status: "idle", listedCount: 2 }), /Importing report.json does not open its pictures/)
assert.match(progress({ status: "verifying", listedCount: 2 }), /Pictures remain hidden/)
assert.match(progress({ status: "error", listedCount: 2 }), /did not pass verification/)
for (const revealedCount of [0, 1, 2]) {
  const rendered = progress({ status: "ready", listedCount: 2, verifiedCount: 2, revealedCount })
  assert.match(rendered, />2 of 2</)
  assert.ok(rendered.includes(`>${revealedCount} of 2<`))
  assert.match(rendered, /do not prove tracking accuracy/)
  assert.doesNotMatch(rendered, /<img|blob:/)
}
const empty = progress({ status: "idle", listedCount: 0 })
assert.match(empty, />0 images</)
assert.equal((empty.match(/>0 of 0</g) ?? []).length, 2)
const { default: MetricComparison, metricMeanings } = await browserModule("MetricComparison", "tsx")
const comparison = (report) => renderToStaticMarkup(createElement(MetricComparison, { report }))
const example = structuredClone(fixture.report)
example.variants[0].metrics = { HOTA: 0.5, IDSW: 2, MOTA: -0.25, FP: 3, frames: 3, custom_metric: 42 }
example.variants[0].metric_deltas = { HOTA: 0, IDSW: 0, MOTA: 0, FP: 0, frames: 0, custom_metric: 0 }
example.variants[1].metrics = { HOTA: 0.6, IDSW: 1, MOTA: -0.2, FP: 4, frames: 3, custom_metric: 43 }
example.variants[1].metric_deltas = { HOTA: 0.1, IDSW: -1, MOTA: 0.05, FP: 1, frames: 0, custom_metric: 1 }
example.variants[1].configuration = { preset: "example-only", overrides: { max_age: 60 } }
const frozenReport = JSON.stringify(example)
const renderedComparison = comparison(example)
assert.equal(JSON.stringify(example), frozenReport, "Rendering must not mutate the report")
for (const text of [
  "How to read this comparison", "reference configuration, not a guaranteed best tracker",
  "one fewer switch, not a negative error count", "not automatically converted to percentages",
  "not a statistical significance test", "not just the failure event you opened",
  "Synthetic or illustrative results do not establish real-world performance",
  "No decision is required", "Tracking-ID changes", "Lower is preferred for this metric alone",
  "Higher is preferred for this metric alone", "Context only · no preferred direction",
  "Direction not specified", "Additional metric supplied by this report",
  "More recorded metrics and evaluation counts (3)", "example-only", "max_age",
]) assert.ok(renderedComparison.includes(text), `Missing comparison explanation: ${text}`)
assert.match(renderedComparison, />0\.6<.*?Change: \+0\.1/s)
assert.match(renderedComparison, />1<.*?Change: -1/s)
assert.match(renderedComparison, />-0\.2<.*?Change: \+0\.05/s)
assert.match(renderedComparison, />43<.*?Change: \+1/s)
assert.match(renderedComparison, /<caption /)
assert.match(renderedComparison, /scope="row"/)
assert.match(renderedComparison, /scope="col"/)
assert.equal((renderedComparison.match(/<table /g) ?? []).length, 2)
assert.equal((renderedComparison.match(/<details /g) ?? []).length, 2)
assert.doesNotMatch(renderedComparison, /<details open|<button|<input|<form|<img|<video|<iframe/)

const full = structuredClone(example)
for (const variant of full.variants) {
  variant.metrics = Object.fromEntries(Object.keys(metricMeanings).map((key) => [key, 0]))
  variant.metric_deltas = { ...variant.metrics }
}
const allMetrics = comparison(full)
assert.equal(Object.keys(metricMeanings).length, 28)
for (const [key, info] of Object.entries(metricMeanings)) {
  assert.ok(allMetrics.includes(`(${key})`), `Missing metric ${key}`)
  assert.ok(allMetrics.includes(info.label), `Missing label ${key}`)
}
assert.match(metricMeanings.MT.meaning, /at least 80%/)
assert.match(metricMeanings.ML.meaning, /less than 20%/)
assert.match(metricMeanings.MOTP.meaning, /intersection-over-union/)
assert.match(metricMeanings.Frag.meaning, /matched reference object to an unmatched one/)

// A supported report may contain only non-core or previously unknown metrics.
const unusual = structuredClone(fixture.report)
unusual.variants = [unusual.variants[0]]
unusual.variants[0].metrics = { __proto_metric: 1, PT: 0, constructor: 2 }
unusual.variants[0].metric_deltas = { __proto_metric: 0, PT: 0, constructor: 0 }
const uncommon = comparison(unusual)
assert.equal((uncommon.match(/<table /g) ?? []).length, 1)
assert.doesNotMatch(uncommon, /More recorded metrics/)
assert.match(uncommon, /__proto_metric/)
assert.match(uncommon, /constructor/)
assert.equal((uncommon.match(/Direction not specified/g) ?? []).length, 2)

const unsafe = structuredClone(fixture.report)
unsafe.experiment.baseline = "<script>not-html</script>"
unsafe.variants[0].name = unsafe.experiment.baseline
unsafe.variants[0].configuration = { note: "<img src=x onerror=alert(1)>" }
const escaped = comparison(unsafe)
assert.match(escaped, /&lt;script&gt;/)
assert.match(escaped, /&lt;img/)
assert.doesNotMatch(escaped, /<script|<img/)
console.log("Lab guide passed: lesson stages, failure explanations, image states, and immutable metric comparisons.")
