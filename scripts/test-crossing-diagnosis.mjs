import assert from "node:assert/strict"
import { readFile } from "node:fs/promises"
import { createElement } from "react"
import { renderToStaticMarkup } from "react-dom/server"
import ts from "typescript"

const root = new URL("../", import.meta.url)
const data = JSON.parse(await readFile(new URL("src/features/crossing-diagnosis/rain.json", root), "utf8"))
const study = JSON.parse(await readFile(new URL("experiments/initiation_threshold_v1_results.json", root), "utf8"))
const source = await readFile(new URL("src/features/crossing-diagnosis/CrossingDiagnosis.tsx", root), "utf8")
const compiled = ts.transpileModule(source.replace('import rain from "./rain.json"', `const rain = ${JSON.stringify(data)}`)
  .replace('import thresholdStudy from "../../../experiments/initiation_threshold_v1_results.json"', `const thresholdStudy = ${JSON.stringify(study)}`), {
  compilerOptions: { module: ts.ModuleKind.ES2022, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX },
}).outputText.replace(/from "(react(?:\/jsx-runtime)?)"/g, (_, name) => `from "${import.meta.resolve(name)}"`)
const { default: Page, StagePlot, CaseExplanation } = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString("base64")}`)
const render = (component, props) => renderToStaticMarkup(createElement(component, props))
const initial = render(Page)
for (const text of ["Why wasn&#x27;t it counted?", "Detector", "Association", "Confirmation", "Counting",
  "does not use your imported Lab report", "not accuracy percentages", "not video or object matches",
  "candidate was chosen after seeing this clip", "not establish accuracy or justify a default change",
  "representative traffic evaluation remains open", "Baseline only", "Previous frame", "Next frame", "Evidence source",
  "54 fixed synthetic comparisons", "Earlier is not always better", "keep the current defaults",
  "not measured traffic accuracy", "persistent noise can", "36 control comparisons"])
  assert.ok(initial.includes(text), `Missing explanation: ${text}`)
assert.equal((initial.match(/aria-pressed="true"/g) ?? []).length, 2)
assert.equal((initial.match(/<option /g) ?? []).length, 9)
assert.match(initial, /href="\/lab"/)
assert.match(initial, /<caption /)
assert.doesNotMatch(initial, /<video|<img|<iframe|type="file"|blob:/)

const before = JSON.stringify(data)
for (const item of data.cases) {
  for (let stage = 0; stage < 4; stage++) {
    const text = render(CaseExplanation, { mark: item.mark_frame, stage })
    assert.match(text, /aria-live="polite"/)
    assert.doesNotMatch(text, /undefined/)
  }
  for (const frame of item.frames) {
    const plot = render(StagePlot, { frame })
    assert.match(plot, /role="img"/)
    assert.ok(plot.includes(`Frame ${frame.frame}:`))
    assert.doesNotMatch(plot, /NaN|undefined/)
    const observations = frame.near_line_detections.length + frame.near_line_internal_tracks.length + frame.near_line_public_tracks.length
    assert.equal((plot.match(/<circle /g) ?? []).length, observations)
    for (const track of frame.near_line_public_tracks) assert.ok(plot.includes(`ID ${track.track_id}`))
  }
}
assert.equal(JSON.stringify(data), before)
assert.match(render(CaseExplanation, { mark: 160, stage: 1 }), /33\.107 exceeds 9\.4877/)
assert.match(render(CaseExplanation, { mark: 92, stage: 0 }), /No retained near-line proposal/)

// Every displayed example is sourced from the complete committed study, with
// agreement checked at the other speed rather than inferred from one example.
assert.equal(study.cells.length, 54)
for (const name of ["steady_true", "persistent_false", "confirmed_gap"]) {
  const rows = study.cells.filter(c => c.case === name && c.score === 0.57)
  assert.equal(rows.length, 2)
  assert.deepEqual(rows[0].baseline.crossings, rows[1].baseline.crossings)
  assert.deepEqual(rows[0].candidate.crossings, rows[1].candidate.crossings)
}
const controls = study.cells.filter(c => c.score !== 0.57)
assert.equal(controls.length, 36)
assert.ok(controls.every(c => c.output_sha256.baseline === c.output_sha256.candidate))
for (const name of ["persistent_false", "true_and_clutter"]) {
  for (const row of study.cells.filter(c => c.case === name && c.score === 0.57)) {
    assert.equal(row.candidate.mot.false_positives - row.baseline.mot.false_positives, 10)
    assert.equal(row.candidate.crossings.fp - row.baseline.crossings.fp, 1)
  }
}
assert.equal(study.recommend_default_change, false)
assert.equal(study.real_world_accuracy_claim, false)

const app = await readFile(new URL("src/App.tsx", root), "utf8")
const deployment = JSON.parse(await readFile(new URL("vercel.json", root), "utf8"))
const lab = await readFile(new URL("src/features/reliability-lab/ReliabilityLab.tsx", root), "utf8")
assert.match(app, /path==='\/lab\/crossings'\?<CrossingDiagnosis\/>/)
assert.match(lab, /href="\/lab\/crossings"/)
assert.ok(deployment.routes.some(route => route.src === "/lab/crossings/?" && route.dest === "/app/index.html"))
console.log("Crossing diagnosis passed: 5 cases, 45 frame plots, controlled threshold findings, evidence limits and route configuration.")
