export type MetricValues = Record<string, number>

export interface ReportExperiment {
  experiment_id: string
  created_at: string
  baseline: string
  frame_range: { start: number; end: number }
  visiontrack_version: string
  git_revision: string | null
}

export interface ReportSource {
  source_id: string
  name: string
  kind: string
  frame_count: number
  width: number
  height: number
  fps: number | null
  detector: Record<string, unknown>
  detection_sha256: string
  ground_truth_sha256: string
  video_sha256: string | null
  video_status: "hash_only_not_bundled" | "not_declared"
}

export interface ReportVariant {
  name: string
  baseline: boolean
  configuration: Record<string, unknown>
  run_id: string
  diagnostics: Record<string, number | null>
  diagnostic_deltas: MetricValues
  metrics: MetricValues
  metric_deltas: MetricValues
  failure_counts: Record<FailureType, number>
  failure_set: Record<string, unknown>
}

export type FailureType =
  | "id_switch"
  | "fragmentation"
  | "miss"
  | "false_positive"

export interface ReportFailure {
  variant: string
  event_id: string
  run_id: string
  frame_index: number
  event_type: FailureType
  track_ids: number[]
  ground_truth_ids: number[]
  context: Record<string, unknown>
  evidence_frames: { start: number; end: number }
  schema_version: 1
}

export interface ReliabilityReport {
  schema_version: 1
  report_id: string
  comparison_id: string
  experiment: ReportExperiment
  source: ReportSource
  variants: ReportVariant[]
  failures: ReportFailure[]
  failure_event_total: number
  failure_event_displayed: number
  failure_events_truncated: boolean
  decision: {
    status: string
    accepted_variant: string | null
    reason: string
  }
  limitations: string[]
}

export type ReportLoadResult =
  | { kind: "ready"; report: ReliabilityReport }
  | { kind: "unsupported"; schemaVersion: unknown }
  | { kind: "missing"; message: string }

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value)

export function parseReportModel(value: unknown): ReportLoadResult {
  if (!isRecord(value)) {
    return { kind: "missing", message: "The report is not a JSON object." }
  }
  if (value.schema_version !== 1) {
    return { kind: "unsupported", schemaVersion: value.schema_version }
  }
  if (
    typeof value.report_id !== "string" ||
    typeof value.comparison_id !== "string" ||
    !isRecord(value.experiment) ||
    !isRecord(value.source) ||
    !Array.isArray(value.variants) ||
    value.variants.length === 0 ||
    !Array.isArray(value.failures) ||
    !Array.isArray(value.limitations) ||
    !isRecord(value.decision)
  ) {
    return { kind: "missing", message: "Required report evidence is missing." }
  }
  const variantsComplete = value.variants.every(
    (variant) =>
      isRecord(variant) &&
      typeof variant.name === "string" &&
      typeof variant.run_id === "string" &&
      isRecord(variant.metrics) &&
      isRecord(variant.metric_deltas) &&
      isRecord(variant.failure_counts),
  )
  if (!variantsComplete) {
    return { kind: "missing", message: "One or more variants lack verified evidence." }
  }
  return { kind: "ready", report: value as unknown as ReliabilityReport }
}
