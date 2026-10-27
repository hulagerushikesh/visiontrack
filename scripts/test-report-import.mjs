import assert from "node:assert/strict"
import { readFile } from "node:fs/promises"
import ts from "typescript"

async function browserModule(name) {
  const source = await readFile(new URL(`../src/features/reliability-lab/${name}.ts`, import.meta.url), "utf8")
  const compiled = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.ES2022, target: ts.ScriptTarget.ES2022 },
  }).outputText
  return import(`data:text/javascript;base64,${Buffer.from(compiled).toString("base64")}`)
}

const { parseReportModel } = await browserModule("types")
const { ReportFileReader, maxReportBytes, verifyReportFingerprint } = await browserModule("report-import")
const fixture = JSON.parse(await readFile(new URL("../tests/fixtures/lab_browser_workflow.json", import.meta.url), "utf8"))
const policyVector = JSON.parse(await readFile(new URL("../tests/fixtures/lab_preprocessing_v2.json", import.meta.url), "utf8"))
const exportedPolicyReport = policyVector.report
const insertionPoint = ',"schema_version":1,"source":'
assert.equal(policyVector.canonical_report_content.split(insertionPoint).length, 2)
const report = policyVector.canonical_report_content.replace(
  insertionPoint,
  `,"report_id":"${exportedPolicyReport.report_id}"${insertionPoint}`,
) + "\n"
const file = (text) => ({ size: Buffer.byteLength(text), text: async () => text })
const reader = new ReportFileReader(parseReportModel)
assert.equal((await reader.read(file(report))).kind, "ready")
assert.deepEqual(JSON.parse(report), exportedPolicyReport)
assert.equal(await verifyReportFingerprint(report, exportedPolicyReport.report_id), true)
assert.equal(await verifyReportFingerprint(report.slice(0, -1), exportedPolicyReport.report_id), true)
assert.equal((await reader.read(file(JSON.stringify(exportedPolicyReport)))).kind, "missing",
  "a JS reserialization cannot preserve Python's numeric JSON tokens")
for (const tampered of [
  report.replace("Track IDs are run-local", "Track IDs are permanent"),
  report.replace('"fps":30.0', '"fps":30'),
  report.replace(exportedPolicyReport.report_id, "0".repeat(64)),
  report.replace(',"report_id":', ', "report_id":'),
  report.replace(',"report_id":', ',"report_id":"' + "0".repeat(64) + '","report_id":'),
  `${report}\n`,
]) {
  const result = await reader.read(file(tampered))
  assert.equal(result.kind, "missing", "edited report bytes must not be treated as verified evidence")
}
const nestedContent = '{"note":"literal \\u0022report_id\\u0022 inside text","other":{"report_id":"nested"},"value":1.0}'
assert.equal(JSON.parse(nestedContent).note, 'literal "report_id" inside text')
const nestedId = await sha256Text(nestedContent)
const nestedReport = nestedContent.replace(',"value":', `,"report_id":"${nestedId}","value":`)
assert.equal(await verifyReportFingerprint(nestedReport, nestedId), true,
  "nested and escaped mentions of report_id are not removed from source bytes")
async function sha256Text(text) {
  return Buffer.from(await globalThis.crypto.subtle.digest("SHA-256", new TextEncoder().encode(text))).toString("hex")
}
// Hash exact Python canonical bytes. JSON.parse/stringify loses distinctions
// such as 1.0 versus 1; the decision-only serializer is not a report hasher.
const { report_id: exportedId, ...exportedContent } = exportedPolicyReport
assert.deepEqual(JSON.parse(policyVector.canonical_report_content), exportedContent)
assert.equal(await sha256Text(policyVector.canonical_report_content), exportedId)
assert.equal(exportedPolicyReport.variants[0].metrics.FP, 2)
for (const [index, failure] of exportedPolicyReport.failures.entries()) {
  const { event_id, variant, media_evidence, ...content } = failure
  assert.deepEqual(JSON.parse(policyVector.canonical_failure_contents[index]), content)
  assert.equal(await sha256Text(policyVector.canonical_failure_contents[index]), event_id)
  assert.equal(content.context.preprocessing, exportedPolicyReport.preprocessing)
}
const v2Report = structuredClone(fixture.report)
v2Report.evaluator = "visiontrack.metrics/v2"
for (const failure of v2Report.failures) failure.context.evaluator = "visiontrack.metrics/v2"
assert.equal(parseReportModel(v2Report).kind, "ready")
const mixedEvaluator = structuredClone(v2Report)
delete mixedEvaluator.failures[0].context.evaluator
assert.equal(parseReportModel(mixedEvaluator).kind, "missing")
assert.equal(parseReportModel({ ...v2Report, evaluator: "unknown" }).kind, "missing")
const policyReport = structuredClone(v2Report)
policyReport.preprocessing = "visiontrack.mot17-preprocessing/v2"
for (const failure of policyReport.failures) failure.context.preprocessing = policyReport.preprocessing
assert.equal(parseReportModel(policyReport).kind, "ready")
for (const preprocessing of [null, "unknown", "visiontrack.mot17-preprocessing/v1", {}]) {
  assert.equal(parseReportModel({ ...policyReport, preprocessing }).kind, "missing")
}
assert.equal(parseReportModel({ ...policyReport, evaluator: "visiontrack.metrics/v1" }).kind, "missing")
assert.equal(parseReportModel({ ...policyReport, evaluator: undefined }).kind, "missing")
const missingPolicy = structuredClone(policyReport)
delete missingPolicy.failures[0].context.preprocessing
assert.equal(parseReportModel(missingPolicy).kind, "missing")
assert.equal(parseReportModel({ ...policyReport, preprocessing: undefined }).kind, "missing")
const wrongPolicy = structuredClone(policyReport)
wrongPolicy.failures[0].context.preprocessing = "visiontrack.mot17-preprocessing/v1"
assert.equal(parseReportModel(wrongPolicy).kind, "missing")
// Even without displayed events an unknown policy must not be accepted.
assert.equal(parseReportModel({ ...policyReport, failures: [], preprocessing: "unknown" }).kind, "missing")
assert.equal((await reader.read(file("not json"))).kind, "missing")
assert.equal((await reader.read(file('{"schema_version":2}'))).kind, "unsupported")

for (const size of [0, maxReportBytes + 1]) {
  let reads = 0
  const result = await reader.read({ size, text: async () => { reads += 1; return report } })
  assert.equal(result.kind, "missing")
  assert.equal(reads, 0, "empty and oversized files are rejected before reading")
}
assert.equal((await reader.read({ size: 10, text: async () => { throw new Error("unreadable") } })).kind, "missing")

function delayedFile() {
  let resolve, reject
  const pending = new Promise((success, failure) => { resolve = success; reject = failure })
  return { file: { size: Buffer.byteLength(report), text: () => pending }, resolve, reject }
}

const slow = delayedFile()
const earlierRead = reader.read(slow.file)
const latest = await reader.read(file(report))
assert.equal(latest.kind, "ready")
slow.resolve(report)
assert.equal(await earlierRead, null, "a late earlier selection cannot replace the latest report")

const canceled = delayedFile()
const canceledRead = reader.read(canceled.file)
reader.cancel()
canceled.resolve(report)
assert.equal(await canceledRead, null, "returning to sample cancels publication of a pending report")

const failed = delayedFile()
const failedRead = reader.read(failed.file)
assert.equal((await reader.read(file(report))).kind, "ready")
failed.reject(new Error("late read failure"))
assert.equal(await failedRead, null, "an earlier read error cannot replace a newer success")

const replaced = delayedFile()
const replacedRead = reader.read(replaced.file)
assert.equal((await reader.read(file(""))).kind, "missing")
replaced.resolve(report)
assert.equal(await replacedRead, null, "even a rejected new selection supersedes the earlier read")
assert.equal((await reader.read(file(report))).kind, "ready", "import can recover after failure or cancellation")

console.log("Report import passed: canonical fingerprint, validation, bounded reads, latest selection, cancellation, stale errors, and recovery.")
