export interface BenchmarkMetric {
  key: string
  label: string
  direction: "higher" | "lower"
  format: "score" | "count"
}

export interface BenchmarkResult {
  mean: number
  std: number
  delta: number
  p_value: number
  significant: boolean
}

export interface BenchmarkVariant {
  name: string
  baseline: boolean
  values: Record<string, BenchmarkResult>
}

export interface BenchmarkReport {
  schema_version: 1
  report_id: string
  title: string
  summary: string
  dataset: {
    name: string
    split: string
    protocol: string
    detector: string
    pair_count: number
    runs_per_variant: number
  }
  provenance: {
    source_document: string
    source_kind: "checked_in_research_artifact"
    config_hash: string
    visiontrack_version: string
    git_revision: string | null
  }
  baseline: string
  metrics: BenchmarkMetric[]
  variants: BenchmarkVariant[]
  limitations: string[]
}
