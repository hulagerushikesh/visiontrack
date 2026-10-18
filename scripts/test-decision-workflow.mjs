import assert from "node:assert/strict"
import { spawnSync } from "node:child_process"
import { createHash } from "node:crypto"
import { copyFile, mkdir, mkdtemp, readFile, readdir, rm, writeFile } from "node:fs/promises"
import { tmpdir } from "node:os"
import { delimiter, join, resolve } from "node:path"
import { fileURLToPath, pathToFileURL } from "node:url"
import ts from "typescript"

const root = fileURLToPath(new URL("../", import.meta.url))
const python = process.env.VISIONTRACK_PYTHON || "python"
const environment = {
  ...process.env,
  PYTHONPATH: [join(root, "src"), process.env.PYTHONPATH].filter(Boolean).join(delimiter),
}
const scratch = await mkdtemp(join(tmpdir(), "visiontrack-decision-workflow-"))

function runPython(code, args = []) {
  const result = spawnSync(python, ["-c", code, ...args], {
    cwd: root, env: environment, encoding: "utf8", timeout: 60_000,
  })
  if (result.error) throw result.error
  return result
}

function runCli(args, expectedStatus = 0) {
  const result = runPython(
    "import sys; from visiontrack.cli import main; sys.exit(main(sys.argv[1:]))", args,
  )
  assert.equal(result.status, expectedStatus, `${args[0]}: ${result.stdout}\n${result.stderr}`)
  return result
}

async function compileBrowserModule(name) {
  const source = await readFile(join(root, "src/features/reliability-lab", `${name}.ts`), "utf8")
  const compiled = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.ES2022, target: ts.ScriptTarget.ES2022 },
  }).outputText
  const destination = join(scratch, `${name}.mjs`)
  await writeFile(destination, compiled)
  return import(pathToFileURL(destination).href)
}

async function snapshot(directory) {
  const files = {}
  async function visit(relative = "") {
    for (const entry of await readdir(join(directory, relative), { withFileTypes: true })) {
      const name = join(relative, entry.name)
      if (entry.isDirectory()) await visit(name)
      else files[name] = createHash("sha256").update(await readFile(join(directory, name))).digest("hex")
    }
  }
  await visit()
  return files
}

const asFile = (text) => ({
  name: "decision.json", size: Buffer.byteLength(text, "utf8"), text: async () => text,
})

try {
  await copyFile(
    join(root, "src/features/reliability-lab/decision-contract.mjs"),
    join(scratch, "decision-contract.mjs"),
  )
  const { parseReportModel } = await compileBrowserModule("types")
  const { createDecisionDraft, serializeDecision, verifyDecisionFile } = await compileBrowserModule("decision")
  const { createDecisionRecord } = await import(pathToFileURL(join(scratch, "decision-contract.mjs")).href)

  for (const status of ["accepted", "rejected_all"]) {
    const output = join(scratch, status)
    const generated = runPython(
      "import sys; from visiontrack.lab import create_synthetic_lab; print(create_synthetic_lab(sys.argv[1]))",
      [output],
    )
    assert.equal(generated.status, 0, generated.stderr)
    const reportPath = generated.stdout.trim()
    const bundle = resolve(reportPath, "../..")
    const result = parseReportModel(JSON.parse(await readFile(reportPath, "utf8")))
    assert.equal(result.kind, "ready", result.message)
    const report = result.report
    assert.ok(report.failures.length > 0, "the generated report offers measured failures to review")
    const original = await snapshot(bundle)
    const input = {
      status,
      acceptedVariant: status === "accepted" ? report.variants[0].name : null,
      rationale: "Synthetic workflow rehearsal — समीक्षा 🧪; no real-data acceptance claim.",
      author: "local-reviewer Δ",
      decidedAt: "2026-10-18T14:00:00.123Z",
    }

    // Date.parse normalizes impossible dates; drafts must reject them before download.
    for (const decidedAt of [
      "2026-02-30T12:00:00Z", "2025-02-29T12:00:00Z", "2026-04-31T12:00:00Z",
      "1900-02-29T12:00:00Z", "2026-13-01T12:00:00Z", "2026-01-00T12:00:00Z",
      "0000-01-01T12:00:00Z", "2026-10-18T24:00:00Z", "2026-10-18T12:00:60Z",
      "2026-10-18T12:00:00+05:30", "2026-10-18T12:00:00", "October 18, 2026 12:00:00Z",
      "2026-10-18T12:00:00Z\n",
    ]) {
      await assert.rejects(createDecisionDraft(report, { ...input, decidedAt }), /valid UTC timestamp/)
    }

    const downloadDirectory = join(scratch, `${status}-downloads`)
    await mkdir(downloadDirectory)
    const download = join(downloadDirectory, "decision.json")
    // Valid UTC spellings and leap days must also survive Python reconstruction.
    for (const decidedAt of [
      input.decidedAt, "2024-02-29T12:00:00Z", "2000-02-29T12:00:00Z",
      "2026-10-18T14:00:00+00:00", "2026-10-18T14:00:00.123456+0000",
      "0001-01-01T00:00:00Z", "2026-10-18 14:00:00,123Z", "2026-10-18T14:00+00",
    ]) {
      const decision = await createDecisionDraft(report, { ...input, decidedAt })
      const bytes = serializeDecision(decision)
      assert.equal((await verifyDecisionFile(asFile(bytes), report)).decision.decision_id, decision.decision_id)
      await writeFile(download, bytes)
      const preview = runCli(["lab-decision-import", bundle, download])
      assert.match(preview.stdout, /Preview only; nothing was written/)
      assert.ok(preview.stdout.includes(decision.decision_id))
      assert.deepEqual(await snapshot(bundle), original, "preview preserves every bundle byte")
    }

    const decision = await createDecisionDraft(report, input)
    const canonical = serializeDecision(decision)
    const content = { ...decision }
    delete content.decision_id
    const wrongLineage = await createDecisionRecord({ ...content, report_id: "0".repeat(64) })
    const unknownVariant = await createDecisionRecord({ ...content, status: "accepted", accepted_variant: "absent-variant" })
    const invalidDate = await createDecisionRecord({ ...content, decided_at: "2026-02-30T12:00:00Z" })
    const changed = { ...decision, rationale: "Changed after download" }
    for (const [invalid, browserError, pythonError] of [
      [changed, /fingerprint/, /decision_id does not match/],
      [wrongLineage, /active report lineage/, /report_id does not match/],
      [unknownVariant, /variant is not present/, /accepted_variant is not a verified report variant/],
      [invalidDate, /structure or schema version/, /ISO-8601 timestamp/],
    ]) {
      const bytes = serializeDecision(invalid)
      await assert.rejects(verifyDecisionFile(asFile(bytes), report), browserError)
      await writeFile(download, bytes)
      const refused = runCli(["lab-decision-import", bundle, download, "--write"], 2)
      assert.match(refused.stderr, pythonError)
      assert.deepEqual(await snapshot(bundle), original, "a refused import preserves every bundle byte")
    }

    await writeFile(download, canonical)
    runCli(["lab-decision-import", bundle, download, "--write"])
    const stored = await readFile(join(bundle, "decision.json"), "utf8")
    assert.equal(stored, canonical, "Python stores the exact browser download bytes")
    const readBack = runPython(
      "import sys; from visiontrack.lab import read_human_decision; print(read_human_decision(sys.argv[1]).to_json())",
      [bundle],
    )
    assert.equal(readBack.status, 0, readBack.stderr)
    assert.equal(readBack.stdout, canonical, "Python retrieves the same verified decision")
    assert.equal((await verifyDecisionFile(asFile(stored), report)).decision.decision_id, decision.decision_id)
    const persisted = await snapshot(bundle)
    const withoutDecision = { ...persisted }
    delete withoutDecision["decision.json"]
    assert.deepEqual(withoutDecision, original, "saving changes only decision.json")

    const repeated = runCli(["lab-decision-import", bundle, download, "--write"])
    assert.match(repeated.stdout, /identical decision already stored/)
    assert.deepEqual(await snapshot(bundle), persisted, "repeated import is idempotent")
    const conflict = await createDecisionDraft(report, { ...input, rationale: "A different human choice." })
    await writeFile(download, serializeDecision(conflict))
    const refused = runCli(["lab-decision-import", bundle, download, "--write"], 2)
    assert.match(refused.stderr, /refusing to overwrite/)
    assert.deepEqual(await snapshot(bundle), persisted, "a conflicting choice cannot replace the record")
  }
  console.log("Synthetic decision round trip passed: generated reports, browser drafts, UTC dates, Python previews, exact storage, repeat imports, and rejected tampering, lineage, variants, and conflicts.")
} finally {
  await rm(scratch, { recursive: true, force: true })
}
