export const ALL_BENCHMARK_METRICS = "__all_metrics__"
export const ALL_BENCHMARK_VARIANTS = "__all_variants__"

/** Derive a display-only slice without changing or recalculating report evidence. */
export function benchmarkView(report, metricFocus, variantFocus) {
  const hasMetric = report.metrics.some((metric) => metric.key === metricFocus)
  const hasVariant = report.variants.some(
    (variant) => !variant.baseline && variant.name === variantFocus,
  )
  const metrics = metricFocus === ALL_BENCHMARK_METRICS || !hasMetric
    ? report.metrics
    : report.metrics.filter((metric) => metric.key === metricFocus)
  const variants = variantFocus === ALL_BENCHMARK_VARIANTS || !hasVariant
    ? report.variants
    : report.variants.filter((variant) => variant.baseline || variant.name === variantFocus)
  return { metrics, variants }
}
