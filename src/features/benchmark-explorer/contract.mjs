const isRecord = (value) => typeof value === "object" && value !== null && !Array.isArray(value)
const isString = (value) => typeof value === "string" && value.trim().length > 0
const isFiniteNumber = (value) => typeof value === "number" && Number.isFinite(value)
const hasExactFields = (value, fields) =>
  isRecord(value) && Object.keys(value).length === fields.length && fields.every((field) => field in value)

const topFields = ["schema_version", "report_id", "title", "summary", "dataset", "provenance", "baseline", "metrics", "variants", "limitations"]
const datasetFields = ["name", "split", "protocol", "detector", "pair_count", "runs_per_variant"]
const provenanceFields = ["source_document", "source_kind", "config_hash", "visiontrack_version", "git_revision"]
const metricFields = ["key", "label", "direction", "format"]
const variantFields = ["name", "baseline", "values"]
const valueFields = ["mean", "std", "delta", "p_value", "significant"]

export function validateBenchmarkReport(value) {
  const fail = (error) => ({ valid: false, error })
  if (!hasExactFields(value, topFields)) return fail("The benchmark report structure is invalid.")
  if (value.schema_version !== 1) return fail("The benchmark report schema version is unsupported.")
  if (!/^[a-z0-9][a-z0-9._-]{2,127}$/.test(value.report_id) || !isString(value.title) || !isString(value.summary)) {
    return fail("The benchmark report identity or description is invalid.")
  }

  const dataset = value.dataset
  if (!hasExactFields(dataset, datasetFields) || !isString(dataset.name) || !isString(dataset.split) ||
      !isString(dataset.protocol) || !isString(dataset.detector) || !Number.isInteger(dataset.pair_count) ||
      dataset.pair_count < 1 || !Number.isInteger(dataset.runs_per_variant) || dataset.runs_per_variant < 1 ||
      dataset.pair_count !== dataset.runs_per_variant) {
    return fail("The dataset or evaluation protocol is incomplete.")
  }

  const provenance = value.provenance
  if (!hasExactFields(provenance, provenanceFields) || !isString(provenance.source_document) ||
      !["checked_in_research_artifact", "structured_experiment_result"].includes(provenance.source_kind) ||
      !/^[a-f0-9]{12}$/.test(provenance.config_hash) || !isString(provenance.visiontrack_version) ||
      !(provenance.git_revision === null || /^[a-f0-9]{7,40}$/.test(provenance.git_revision))) {
    return fail("The benchmark provenance is incomplete or invalid.")
  }

  if (!isString(value.baseline) || !Array.isArray(value.metrics) || value.metrics.length === 0) {
    return fail("The baseline and metric definitions are required.")
  }
  const metricKeys = new Set()
  for (const metric of value.metrics) {
    if (!hasExactFields(metric, metricFields) || !/^[A-Z][A-Z0-9_]{1,15}$/.test(metric.key) ||
        metricKeys.has(metric.key) || !isString(metric.label) ||
        !["higher", "lower"].includes(metric.direction) || !["score", "count"].includes(metric.format)) {
      return fail("One or more metric definitions are invalid.")
    }
    metricKeys.add(metric.key)
  }

  if (!Array.isArray(value.variants) || value.variants.length < 2) {
    return fail("At least two benchmark variants are required.")
  }
  const variantNames = new Set()
  let baselineCount = 0
  for (const variant of value.variants) {
    if (!hasExactFields(variant, variantFields) || !/^[a-z0-9][a-z0-9._-]{0,63}$/.test(variant.name) ||
        variantNames.has(variant.name) || typeof variant.baseline !== "boolean" || !isRecord(variant.values) ||
        Object.keys(variant.values).length !== metricKeys.size ||
        [...metricKeys].some((key) => !(key in variant.values))) {
      return fail("One or more benchmark variants are invalid.")
    }
    variantNames.add(variant.name)
    if (variant.baseline) baselineCount += 1
    for (const key of metricKeys) {
      const result = variant.values[key]
      if (!hasExactFields(result, valueFields) || !isFiniteNumber(result.mean) ||
          !(result.std === null || (isFiniteNumber(result.std) && result.std >= 0)) ||
          !isFiniteNumber(result.delta) ||
          !(result.p_value === null || (isFiniteNumber(result.p_value) && result.p_value >= 0 && result.p_value <= 1)) ||
          typeof result.significant !== "boolean" ||
          (result.p_value !== null && result.significant !== (result.p_value < 0.05))) {
        return fail(`The ${variant.name} ${key} result is invalid.`)
      }
      if (variant.baseline && (result.delta !== 0 || result.significant)) {
        return fail("Baseline comparisons must remain a zero-delta reference row.")
      }
    }
  }
  if (baselineCount !== 1 || !variantNames.has(value.baseline) ||
      !value.variants.some((variant) => variant.name === value.baseline && variant.baseline)) {
    return fail("The declared baseline does not match exactly one variant.")
  }
  if (!Array.isArray(value.limitations) || value.limitations.length === 0 || !value.limitations.every(isString)) {
    return fail("The report must preserve at least one explicit limitation.")
  }
  return { valid: true }
}
