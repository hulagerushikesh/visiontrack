import assert from "node:assert/strict"
import { createHash } from "node:crypto"
import { spawnSync } from "node:child_process"
import { mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises"
import { tmpdir } from "node:os"
import { join } from "node:path"
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
const api = await import(await moduleUrl("association"))
const { verifyInitiationTrace } = await import(await moduleUrl("initiation"))
const { ReportFileReader } = await import(await moduleUrl("report-import"))
const { parseReportModel } = await import(await moduleUrl("types"))
const { canonicalJson } = await import("../src/features/reliability-lab/decision-contract.mjs")
const { default: Inspector, AssociationExplanationView, AssociationPairSelector } = await import(await moduleUrl("AssociationInspector", "tsx"))
const { InitiationTimeline } = await import(await moduleUrl("InitiationInspector", "tsx"))
const asFile = text => ({ size: Buffer.byteLength(text), text: async () => text })
const render = (component, props) => renderToStaticMarkup(createElement(component, props))
const scratch = await mkdtemp(join(tmpdir(), "visiontrack-association-ui-"))
try {
  const run = spawnSync(process.env.VISIONTRACK_PYTHON || "python", ["-c", `
import hashlib,json,sys
from pathlib import Path
from visiontrack.lab import (DetectionRecord,GroundTruthRecord,ExperimentManifest,SourceManifest,
    create_experiment_bundle,detection_payload_sha256,run_comparison,canonical_json,
    build_report_model,build_initiation_trace,build_association_explanation,
    ground_truth_payload_sha256,calculate_bundle_metrics,calculate_failure_events,create_comparison_summary)
root=Path(sys.argv[1])
box=(10.,10.,30.,30.)
d=(7,box,.9,1)
cases=[
    ('tentative',[[d]]*6,{},1,1,7),
    ('confirmed',[[d]]*6,{},4,1,7),
    ('all-gates',[[d],[(7,(100.,100.,120.,120.),.9,2)]],{},1,1,7),
    ('kalman',[[d],[(7,(11.,10.,31.,30.),.9,1)]],{'kf_noise_scale':.001},1,1,7),
    ('class',[[d],[(7,box,.9,2)]],{},1,1,7),
    ('competition',[[d,(99,box,.9,1)],[d]],{},1,2,7),
    ('cost-limit',[[d],[(7,(15.5,15.5,35.5,35.5),.9,1)]],{'use_giou':True,'use_mahalanobis_gating':False},1,1,7),
    ('soft-recovery',[[d]]*3+[[(7,box,.3,1)]],{'w_unc':.2},3,1,7),
    ('plain-recovery',[[d]]*3+[[(7,box,.3,1)]],{},3,1,7),
    ('not-offered',[[d]]*3+[[d,(99,box,.3,1)]],{},3,1,99),
    ('below-score',[[d]]*3+[[(99,box,.05,1)]],{},3,1,99),
    ('class-disabled',[[d],[(7,box,.9,2)]],{'class_aware':False},1,1,7),
    ('class-agnostic',[[(7,box,.9,-1)],[(7,box,.9,2)]],{},1,1,7),
    ('equal-bounds',[[d],[d]],{'match_iou_thresh':1.},1,1,7),
]
out=[]
for name,rows,overrides,frame,track,key in cases:
    records=[DetectionRecord(f,None,k,tuple(b),s,c) for f,ds in enumerate(rows) for k,b,s,c in ds]
    ground_truth=[GroundTruthRecord(f,None,1,box,1,1.,False) for f in range(len(rows))]
    now='2026-11-01T12:00:00Z'
    source=SourceManifest.create(kind='synthetic',name='association UI '+name,
        detection_sha256=detection_payload_sha256(records,frame_count=len(rows)),
        ground_truth_sha256=ground_truth_payload_sha256(ground_truth,frame_count=len(rows)),video_sha256=None,detector={'name':'fixture'},
        frame_count=len(rows),width=300,height=300,fps=30.,coordinate_space='pixel_xyxy',created_at=now)
    experiment=ExperimentManifest.create(source_id=source.source_id,baseline='baseline',
        variants=({'name':'baseline','overrides':overrides},),metrics=('track_count',),
        frame_range={'start':0,'end':len(rows)},visiontrack_version='0.4.0',git_revision=None,
        environment={'python':'fixture'},created_at=now)
    bundle=create_experiment_bundle(root/name,experiment,source,records,ground_truth)
    run_comparison(bundle)
    calculate_bundle_metrics(bundle)
    calculate_failure_events(bundle)
    create_comparison_summary(bundle)
    snapshot=lambda:{str(p.relative_to(bundle)):hashlib.sha256(p.read_bytes()).hexdigest() for p in bundle.rglob('*') if p.is_file()}
    before=snapshot()
    # A one-frame warm-up window can include a previous agnostic class without
    # widening the existing initiation browser contract's detection class range.
    trace=build_initiation_trace(bundle,variant='baseline',start=frame,end=frame+1)
    explanation=build_association_explanation(bundle,variant='baseline',frame=frame,track_id=track,detection_index=key)
    report=build_report_model(bundle)
    assert before==snapshot()
    out.append({'name':name,'report':canonical_json(report)+'\\n',
        'trace':canonical_json(trace)+'\\n','explanation':canonical_json(explanation)+'\\n'})
print(json.dumps(out))
`, scratch], { encoding: "utf8", timeout: 60_000, maxBuffer: 8 * 1024 * 1024 })
  assert.equal(run.status, 0, run.stderr)
  const cases = []
  const outcomes = new Set()
  for (const vector of JSON.parse(run.stdout)) {
    const reportResult = await new ReportFileReader(parseReportModel).read(asFile(vector.report))
    assert.equal(reportResult.kind, "ready", `${vector.name}: ${reportResult.message}`)
    const report = reportResult.report
    const trace = await verifyInitiationTrace(vector.trace, report)
    const expected = JSON.parse(vector.explanation)
    const selection = { frame: expected.frame_index, trackId: expected.track_id, detectionIndex: expected.detection_index }
    const explanation = await api.verifyAssociationExplanation(vector.explanation, report, trace, selection)
    assert.deepEqual(explanation, expected, vector.name)
    assert.deepEqual(await api.verifyAssociationExplanation(vector.explanation.trimEnd(), report, trace, selection), expected)
    const before = JSON.stringify({ report, trace, explanation })
    const html = render(AssociationExplanationView, { explanation })
    assert.match(html, /report\/run and selected trace pair checked/)
    assert.match(html, /does not run the tracker or authenticate the producer/)
    assert.match(html, /Pair not offered in this stage/)
    assert.doesNotMatch(html, /<img|<video|<canvas|<iframe|type="file"/)
    for (const stage of explanation.stages) if (stage.pair) {
      outcomes.add(stage.pair.outcome)
      assert.ok(html.includes(api.outcomeLabels[stage.pair.outcome]))
    }
    if (vector.name === "kalman") { assert.match(html, /Motion consistency/); assert.match(html, /Failed/); assert.match(html, /9.4877/); assert.match(html, /132231.4049586777/) }
    if (vector.name === "soft-recovery") assert.match(html, /recorded for the soft uncertainty cost/)
    if (vector.name === "not-offered") { assert.equal(explanation.stages.every(s => s.pair === null), true); assert.doesNotMatch(html, /Pair blocked by a gate/) }
    const frame = trace.frames[0]
    const selector = render(AssociationPairSelector, { report, trace, frame })
    assert.match(selector, /Original detection key/)
    assert.match(selector, /newer than the published 0.4.0/)
    assert.match(selector, /Import association explanation/)
    assert.match(selector, /--detection-index 7|--detection-index 99/)
    assert.equal(JSON.stringify({ report, trace, explanation }), before)
    cases.push({ ...vector, explanationText: vector.explanation, report, trace, selection, explanation })
  }
  assert.deepEqual([...outcomes].sort(), ["above_cost_limit", "blocked_by_gate", "eligible_not_selected", "selected"])
  const c = cases[0]
  const sha = text => createHash("sha256").update(text).digest("hex")
  const verify = (text, report = c.report, trace = c.trace, selection = c.selection) => api.verifyAssociationExplanation(text, report, trace, selection)
  function edited(mutate, base = c, preserveConfig = true) {
    const changed = structuredClone(base.explanation)
    mutate(changed)
    delete changed.explanation_id
    const rawConfig = base.explanationText.match(/"config":(\{[^}]+\}),/)[1]
    const render = value => {
      let text = canonicalJson(value)
      if (preserveConfig) text = text.replace(`"config":${canonicalJson(changed.config)},`, `"config":${rawConfig},`)
      return text
    }
    return `${render({ ...changed, explanation_id: sha(render(changed)) })}\n`
  }
  // Re-sign edits so shape, semantic and lineage checks cannot rely only on a hash mismatch.
  for (const [mutate, expected] of [
    [e => { e.schema = "visiontrack.association-explanation/v2" }, /version/],
    [e => { e.extra = true }, /structure/],
    [e => { delete e.stages }, /structure/],
    [e => { e.accuracy_claim = true }, /boundaries/],
    [e => { e.experiment_id = "0".repeat(64) }, /trace\/run/],
    [e => { e.source_id = "0".repeat(64) }, /trace\/run/],
    [e => { e.variant = "unknown" }, /trace\/run/],
    [e => { e.run_id = "0".repeat(64) }, /trace\/run/],
    [e => { e.detection_sha256 = "0".repeat(64) }, /trace\/run/],
    [e => { e.track_sha256 = "0".repeat(64) }, /trace\/run/],
    [e => { e.replay_frame_range.end++ }, /trace\/run/],
    [e => { e.frame_index++ }, /different frame or pair/],
    [e => { e.track_id++ }, /different frame or pair/],
    [e => { e.detection_index = 0 }, /different frame or pair/],
    [e => { e.detection.score = .8 }, /detection differs/],
    [e => { e.stages.pop() }, /three/],
    [e => { e.stages.reverse() }, /order/],
    [e => { e.stages[0].pair = e.stages[2].pair }, /not offered/],
    [e => { e.stages[2].pair = null }, /structure/],
    [e => { e.stages[2].track_offered = false }, /inputs disagree/],
    [e => { e.stages[2].detection_count++ }, /inputs disagree/],
    [e => { e.stages[2].pair.predicted_xyxy[2] = 0 }, /box/],
    [e => { e.stages[2].pair.iou = 1.1 }, /geometry/],
    [e => { e.stages[2].pair.minimum_iou = .2 }, /gate settings/],
    [e => { e.stages[2].pair.class_mismatch = true }, /gate settings/],
    [e => { e.stages[2].pair.mahalanobis_limit = null }, /hard Kalman/],
    [e => { e.stages[2].pair.mahalanobis_squared = null }, /distance/],
    [e => { e.stages[2].pair.failed_gates = ["iou"] }, /numeric comparisons/],
    [e => { e.stages[2].pair.cost_eligible = false }, /eligibility/],
    [e => { e.stages[2].pair.track_matched_detection_index = 0 }, /partners/],
    [e => { e.stages[2].pair.detection_matched_track_id = 2 }, /partners/],
    [e => { e.stages[2].pair.outcome = "eligible_not_selected" }, /outcome/],
    [e => { e.producer.implementation_sha256 = { "../secret.py": "a".repeat(64) } }, /source hashes/],
  ]) await assert.rejects(verify(edited(mutate)), expected)
  await assert.rejects(verify(edited(e => { e.config.kf_noise_scale = 2 }, c, false)), /trace\/run/)
  await assert.rejects(verify(edited(() => {}, c, false)), /run ID/)
  // Matching historical runs may be inspected by a newer checkout. Provenance
  // remains declared; a producer string is never treated as authentication.
  assert.equal((await verify(edited(e => { e.producer.visiontrack = "0.4.0-dev" }))).producer.visiontrack, "0.4.0-dev")
  await assert.rejects(verify(c.explanationText.replace('"kf_noise_scale":1.0', '"kf_noise_scale":1')), /fingerprint/)
  await assert.rejects(verify(c.explanationText + "\n"), /fingerprint/)
  await assert.rejects(verify(c.explanationText.replace('"iou":1.0', '"iou":1e999')), /fingerprint|geometry/)
  await assert.rejects(verify(`{"nested":${"[".repeat(33)}0${"]".repeat(33)}}`), /deeply/)
  for (const text of [
    c.explanationText.replace('"accuracy_claim":false', '"accuracy_claim":false,"accuracy_claim":false'),
    c.explanationText.replace('"n_init":3', '"n_init":3,"n_init":3'),
    c.explanationText.replace('"cost_eligible":true', '"cost_eligible":true,"cost_eligible":true'),
  ]) await assert.rejects(verify(text), /Duplicate/)
  const badReport = structuredClone(c.report)
  badReport.variants[0].diagnostics.observation_count++
  await assert.rejects(verify(c.explanationText, badReport), /run ID/)
  delete badReport.variants[0].diagnostics.observation_count
  await assert.rejects(verify(c.explanationText, badReport), /observation count/)
  const wrongTrace = structuredClone(c.trace)
  wrongTrace.frames[0].tracks[0].previous_state = null
  await assert.rejects(verify(c.explanationText, c.report, wrongTrace), /pre-association/)

  const reader = new api.AssociationFileReader()
  const read = file => reader.read(file, c.report, c.trace, c.selection)
  for (const size of [0, api.maxAssociationBytes + 1]) {
    let called = false
    assert.equal((await read({ size, text: async () => { called = true; return c.explanationText } })).kind, "error")
    assert.equal(called, false)
  }
  assert.equal((await read(asFile("invalid"))).kind, "error")
  assert.equal((await read({ size: 100, text: async () => { throw new Error("unreadable") } })).kind, "error")
  assert.equal((await read(asFile(c.explanationText))).kind, "ready")
  assert.equal((await read({ size: 100, text: async () => " ".repeat(api.maxAssociationBytes + 1) })).kind, "error")
  for (const action of ["cancel", "replace", "invalid", "error"]) {
    let resolve, reject
    const promise = new Promise((a, b) => { resolve = a; reject = b })
    const pending = read({ size: 100, text: () => promise })
    if (action === "cancel") reader.cancel()
    else await read(asFile(action === "invalid" ? "bad" : c.explanationText))
    if (action === "error") reject(new Error("stale")); else resolve(c.explanationText)
    assert.equal(await pending, null)
  }
  const original = crypto.subtle.digest, digest = original.bind(crypto.subtle)
  let started, release, first = true
  const reached = new Promise(resolve => { started = resolve }), wait = new Promise(resolve => { release = resolve })
  crypto.subtle.digest = async (...args) => { const result = await digest(...args); if (first) { first = false; started(); await wait } return result }
  try { const pending = read(asFile(c.explanationText)); await reached; reader.cancel(); release(); assert.equal(await pending, null) }
  finally { crypto.subtle.digest = original }

  const closed = render(Inspector, { report: c.report, trace: c.trace, frame: c.trace.frames[0] })
  assert.match(closed, /aria-expanded="false"/)
  assert.doesNotMatch(closed, /type="file"|--json/)
  const timeline = render(InitiationTimeline, { report: c.report, trace: c.trace })
  assert.match(timeline, /Why did this pair match or fail/)
  const guided = render(InitiationTimeline, { report: c.report, trace: c.trace, guided: true })
  assert.doesNotMatch(guided, /Why did this pair match or fail/)
  const birthFrame = { ...c.trace.frames[0], tracks: c.trace.frames[0].tracks.map(t => ({ ...t, previous_state: null })) }
  assert.match(render(AssociationPairSelector, { report: c.report, trace: c.trace, frame: birthFrame }), /no pre-existing track\/detection pair/)
  assert.doesNotMatch(render(AssociationPairSelector, { report: c.report, trace: c.trace, frame: { ...c.trace.frames[0], detections: [] } }), /type="file"/)
  const inspectorSource = await readFile(new URL("../src/features/reliability-lab/AssociationInspector.tsx", import.meta.url), "utf8")
  const timelineSource = await readFile(new URL("../src/features/reliability-lab/InitiationInspector.tsx", import.meta.url), "utf8")
  // Remounts are the React state boundary: frame/trace changes close the whole
  // panel, pair changes discard the old import session, and cleanup cancels it.
  assert.match(timelineSource, /key=\{`\$\{trace.trace_id\}:\$\{frame.frame_index\}`\}/)
  assert.match(inspectorSource, /key=\{`\$\{trackId\}:\$\{detectionIndex\}`\}/)
  assert.match(inspectorSource, /return \(\) => current.cancel\(\)/)
  for (const name of ["association.ts", "AssociationInspector.tsx"]) assert.doesNotMatch(await readFile(new URL(`../src/features/reliability-lab/${name}`, import.meta.url), "utf8"), /fetch\(|XMLHttpRequest|sendBeacon|localStorage|sessionStorage|createObjectURL|<video|<canvas/)
  if (process.env.VISIONTRACK_ASSOCIATION_RECEIPT) {
    const path = process.env.VISIONTRACK_ASSOCIATION_RECEIPT
    await mkdir(path, { recursive: true })
    await writeFile(join(path, "vectors.json"), run.stdout)
    await writeFile(join(path, "receipt.json"), JSON.stringify({ schema: "visiontrack.association-browser-check/v1", cases: cases.map(c => ({ name: c.name, explanation_id: c.explanation.explanation_id, run_id: c.explanation.run_id })), outcomes: [...outcomes].sort(), visual_browser_qa: false, tracker_behavior_changed: false }, null, 2) + "\n")
  }
  console.log("Association workflow passed: 14 real Python exports, all outcomes, exact report/trace/pair lineage, actual stage inputs/partners, semantic refusal, bounded/canceled reads, numeric explanations and rendered local-only controls. No browser interaction QA.")
} finally { await rm(scratch, { recursive: true, force: true }) }
