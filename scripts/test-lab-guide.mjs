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

const { failureExplanations, explainFailure } = await browserModule("explanations", "ts")
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
console.log("Lab guide passed: rendered lesson stages, accessible controls, evidence boundaries, and all four failure explanations.")
