import assert from "node:assert/strict"
import { readFile } from "node:fs/promises"

import {
  canonicalJson,
  createDecisionRecord,
  serializeDecision,
  sha256Canonical,
} from "../src/features/reliability-lab/decision-contract.mjs"

const fixtureUrl = new URL("../tests/fixtures/lab_decision_conformance.json", import.meta.url)
const fixture = JSON.parse(await readFile(fixtureUrl, "utf8"))

assert.equal(fixture.schema_version, 1)
assert.deepEqual(new Set(fixture.vectors.map((vector) => vector.values.status)), new Set(["accepted", "rejected_all"]))

for (const vector of fixture.vectors) {
  const content = { ...vector.values, schema_version: fixture.schema_version }
  const decision = await createDecisionRecord(content)
  assert.equal(await sha256Canonical(content), vector.decision_id, `${vector.name}: fingerprint`)
  assert.equal(decision.decision_id, vector.decision_id, `${vector.name}: decision ID`)
  assert.equal(canonicalJson(decision), vector.canonical_json, `${vector.name}: canonical JSON`)
  assert.equal(serializeDecision(decision), `${vector.canonical_json}\n`, `${vector.name}: file bytes`)
}

console.log(`Decision contract conformance passed for ${fixture.vectors.length} vectors.`)
