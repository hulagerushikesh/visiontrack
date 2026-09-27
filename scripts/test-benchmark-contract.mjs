import assert from "node:assert/strict"
import { readFile } from "node:fs/promises"

import { validateBenchmarkReport } from "../src/features/benchmark-explorer/contract.mjs"

const sampleUrl = new URL("../src/features/benchmark-explorer/sample.json", import.meta.url)
const sample = JSON.parse(await readFile(sampleUrl, "utf8"))

assert.deepEqual(validateBenchmarkReport(sample), { valid: true })
assert.equal(sample.provenance.source_document, "web/benchmark.html")
assert.equal(sample.provenance.config_hash, "0bf2d757c381")
assert.equal(sample.variants.length, 6)
assert.equal(sample.variants.find((variant) => variant.name === "bytetrack_reid").values.IDF1.significant, true)

const clone = () => structuredClone(sample)

const unsupported = clone()
unsupported.schema_version = 2
assert.equal(validateBenchmarkReport(unsupported).valid, false)

const automaticSignificance = clone()
automaticSignificance.variants[0].values.MOTA.p_value = 0.2
automaticSignificance.variants[0].values.MOTA.significant = true
assert.equal(validateBenchmarkReport(automaticSignificance).valid, false)

const ambiguousBaseline = clone()
ambiguousBaseline.variants[0].baseline = true
assert.equal(validateBenchmarkReport(ambiguousBaseline).valid, false)

const unknownField = clone()
unknownField.recommendation = "bytetrack_reid"
assert.equal(validateBenchmarkReport(unknownField).valid, false)

console.log("Benchmark report contract accepted the checked-in sample and rejected 4 invalid variants.")
