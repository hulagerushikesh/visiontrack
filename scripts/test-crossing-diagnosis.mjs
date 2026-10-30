import assert from "node:assert/strict"
import { readFile } from "node:fs/promises"
import { createElement } from "react"
import { renderToStaticMarkup } from "react-dom/server"
import ts from "typescript"

const root = new URL("../", import.meta.url)
const data = JSON.parse(await readFile(new URL("src/features/crossing-diagnosis/rain.json", root), "utf8"))
const source = await readFile(new URL("src/features/crossing-diagnosis/CrossingDiagnosis.tsx", root), "utf8")
const compiled = ts.transpileModule(source.replace('import rain from "./rain.json"', `const rain = ${JSON.stringify(data)}`), {
  compilerOptions: { module: ts.ModuleKind.ES2022, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX },
}).outputText.replace(/from "(react(?:\/jsx-runtime)?)"/g, (_, name) => `from "${import.meta.resolve(name)}"`)
const { default: Page, StagePlot, CaseExplanation } = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString("base64")}`)
const render = (component, props) => renderToStaticMarkup(createElement(component, props))
const initial = render(Page)
for (const text of ["Why wasn&#x27;t it counted?", "Detector", "Association", "Confirmation", "Counting",
  "does not use your imported Lab report", "not accuracy percentages", "not video or object matches",
  "candidate was chosen after seeing this clip", "not establish accuracy or justify a default change",
  "Fresh evaluation", "Baseline only", "Previous frame", "Next frame", "Evidence source"])
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

const app = await readFile(new URL("src/App.tsx", root), "utf8")
const deployment = JSON.parse(await readFile(new URL("vercel.json", root), "utf8"))
const lab = await readFile(new URL("src/features/reliability-lab/ReliabilityLab.tsx", root), "utf8")
assert.match(app, /path==='\/lab\/crossings'\?<CrossingDiagnosis\/>/)
assert.match(lab, /href="\/lab\/crossings"/)
assert.ok(deployment.routes.some(route => route.src === "/lab/crossings/?" && route.dest === "/app/index.html"))
console.log("Crossing diagnosis passed: 5 case explanations, all 45 frame plots, evidence limits and deployed navigation.")
