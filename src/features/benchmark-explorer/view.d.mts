import type { BenchmarkMetric, BenchmarkReport, BenchmarkVariant } from "./types"

export const ALL_BENCHMARK_METRICS: "__all_metrics__"
export const ALL_BENCHMARK_VARIANTS: "__all_variants__"
export function benchmarkView(
  report: BenchmarkReport,
  metricFocus: string,
  variantFocus: string,
): { metrics: BenchmarkMetric[]; variants: BenchmarkVariant[] }
