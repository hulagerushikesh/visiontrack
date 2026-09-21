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

export type FailureType = "id_switch" | "fragmentation" | "miss" | "false_positive"

export type MediaEvidenceStatus = "not_declared" | "declared_empty" | "available"

export interface ReportMediaEvidence {
  status: MediaEvidenceStatus
  evidence_id: string | null
  artifact_count: number
  privacy: Array<"source_pixels" | "redacted" | "synthetic">
  views: Array<"full_frame" | "crop">
  frame_indices: number[]
}

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
  media_evidence?: ReportMediaEvidence
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
  media_evidence?: {
    event_manifests: number
    image_artifacts: number
    privacy_counts: Record<"source_pixels" | "redacted" | "synthetic", number>
    images_embedded: false
  }
  decision: { status: string; accepted_variant: string | null; reason: string }
  limitations: string[]
}

export type ReportLoadResult =
  | { kind: "ready"; report: ReliabilityReport }
  | { kind: "unsupported"; schemaVersion: unknown }
  | { kind: "missing"; message: string }

const failureTypes: FailureType[] = ["id_switch", "fragmentation", "miss", "false_positive"]
const videoStatuses: ReportSource["video_status"][] = ["hash_only_not_bundled", "not_declared"]
const mediaStatuses: MediaEvidenceStatus[] = ["not_declared", "declared_empty", "available"]
const privacyClasses = ["source_pixels", "redacted", "synthetic"] as const
const mediaViews = ["full_frame", "crop"] as const
const privacyCountShape = { source_pixels: 0, redacted: 0, synthetic: 0 }

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value)
const isNonEmptyString = (value: unknown): value is string =>
  typeof value === "string" && value.trim().length > 0
const isHash = (value: unknown): value is string =>
  typeof value === "string" && /^[a-f0-9]{64}$/.test(value)
const isFiniteNumber = (value: unknown): value is number =>
  typeof value === "number" && Number.isFinite(value)
const isInteger = (value: unknown): value is number => Number.isInteger(value)
const isNonNegativeInteger = (value: unknown): value is number => isInteger(value) && value >= 0
const isPositiveInteger = (value: unknown): value is number => isInteger(value) && value > 0
const isNumericRecord = (value: unknown, allowNull = false): value is Record<string, number | null> =>
  isRecord(value) && Object.keys(value).length > 0 && Object.entries(value).every(
    ([key, item]) => isNonEmptyString(key) && (isFiniteNumber(item) || (allowNull && item === null)),
  )
const hasSameKeys = (left: Record<string, unknown>, right: Record<string, unknown>) => {
  const leftKeys = Object.keys(left).sort()
  const rightKeys = Object.keys(right).sort()
  return leftKeys.length === rightKeys.length && leftKeys.every((key, index) => key === rightKeys[index])
}
const isIdArray = (value: unknown): value is number[] =>
  Array.isArray(value) && value.every(isPositiveInteger) && new Set(value).size === value.length
const missing = (message: string): ReportLoadResult => ({ kind: "missing", message })
const isUniqueIntegerArray = (value: unknown): value is number[] =>
  Array.isArray(value) && value.every(isNonNegativeInteger) && new Set(value).size === value.length

function isMediaEvidence(value: unknown, frameStart: number, frameEnd: number): value is ReportMediaEvidence {
  if (!isRecord(value) || !mediaStatuses.includes(value.status as MediaEvidenceStatus)) return false
  if (
    !(value.evidence_id === null || isHash(value.evidence_id)) ||
    !isNonNegativeInteger(value.artifact_count) || !Array.isArray(value.privacy) ||
    !value.privacy.every((item) => privacyClasses.includes(item as typeof privacyClasses[number])) ||
    new Set(value.privacy).size !== value.privacy.length || !Array.isArray(value.views) ||
    !value.views.every((item) => mediaViews.includes(item as typeof mediaViews[number])) ||
    new Set(value.views).size !== value.views.length || !isUniqueIntegerArray(value.frame_indices) ||
    value.frame_indices.some((item) => item < frameStart || item >= frameEnd)
  ) return false
  if (value.status === "not_declared") {
    return value.evidence_id === null && value.artifact_count === 0 &&
      value.privacy.length === 0 && value.views.length === 0 && value.frame_indices.length === 0
  }
  if (!isHash(value.evidence_id)) return false
  if (value.status === "declared_empty") {
    return value.artifact_count === 0 && value.privacy.length === 0 &&
      value.views.length === 0 && value.frame_indices.length === 0
  }
  return value.artifact_count > 0 && value.privacy.length > 0 && value.views.length > 0 &&
    value.frame_indices.length > 0 && value.artifact_count >= value.privacy.length &&
    value.artifact_count >= value.views.length && value.artifact_count >= value.frame_indices.length
}

export function parseReportModel(value: unknown): ReportLoadResult {
  if (!isRecord(value)) return missing("The selected file is not a JSON object.")
  if (value.schema_version !== 1) return { kind: "unsupported", schemaVersion: value.schema_version }
  if (!isHash(value.report_id) || !isHash(value.comparison_id)) {
    return missing("The report or comparison fingerprint is missing or invalid.")
  }

  const experiment = value.experiment
  if (
    !isRecord(experiment) || !isHash(experiment.experiment_id) ||
    !isNonEmptyString(experiment.created_at) || !isNonEmptyString(experiment.baseline) ||
    !isRecord(experiment.frame_range) || !isNonNegativeInteger(experiment.frame_range.start) ||
    !isPositiveInteger(experiment.frame_range.end) || experiment.frame_range.start >= experiment.frame_range.end ||
    !isNonEmptyString(experiment.visiontrack_version) ||
    !(experiment.git_revision === null || isNonEmptyString(experiment.git_revision))
  ) return missing("Experiment provenance or frame bounds are incomplete.")

  const source = value.source
  if (
    !isRecord(source) || !isHash(source.source_id) || !isNonEmptyString(source.name) ||
    !isNonEmptyString(source.kind) || !isPositiveInteger(source.frame_count) ||
    !isPositiveInteger(source.width) || !isPositiveInteger(source.height) ||
    !(source.fps === null || (isFiniteNumber(source.fps) && source.fps > 0)) ||
    !isRecord(source.detector) || !isHash(source.detection_sha256) ||
    !isHash(source.ground_truth_sha256) || !(source.video_sha256 === null || isHash(source.video_sha256)) ||
    !videoStatuses.includes(source.video_status as ReportSource["video_status"]) ||
    (source.video_status === "not_declared" && source.video_sha256 !== null) ||
    (source.video_status === "hash_only_not_bundled" && !isHash(source.video_sha256)) ||
    experiment.frame_range.end > source.frame_count
  ) return missing("Source evidence, hashes, or media bounds are incomplete.")

  if (!Array.isArray(value.variants) || value.variants.length === 0) {
    return missing("At least one verified variant is required.")
  }
  const variantNames = new Set<string>()
  const runIds = new Map<string, string>()
  let baselineCount = 0
  let metricKeys: string[] | null = null
  let failureSetTotal = 0
  for (const variant of value.variants) {
    if (
      !isRecord(variant) || !isNonEmptyString(variant.name) || variantNames.has(variant.name) ||
      typeof variant.baseline !== "boolean" || !isRecord(variant.configuration) || !isHash(variant.run_id) ||
      !isNumericRecord(variant.diagnostics, true) || !isNumericRecord(variant.diagnostic_deltas) ||
      !isNumericRecord(variant.metrics) || !isNumericRecord(variant.metric_deltas) ||
      !hasSameKeys(variant.metrics, variant.metric_deltas) || !isRecord(variant.failure_counts) ||
      !failureTypes.every((type) => isNonNegativeInteger(variant.failure_counts[type])) ||
      !isRecord(variant.failure_set)
    ) return missing("One or more variants lack complete, verified evidence.")
    const keys = Object.keys(variant.metrics).sort()
    if (metricKeys && (keys.length !== metricKeys.length || keys.some((key, index) => key !== metricKeys?.[index]))) {
      return missing("All variants must report the same metric set.")
    }
    metricKeys = keys
    const failureSet = variant.failure_set
    const variantFailureTotal = failureTypes.reduce((total, type) => total + Number(variant.failure_counts[type]), 0)
    if (
      !isNonNegativeInteger(failureSet.event_count) || failureSet.event_count !== variantFailureTotal ||
      !isHash(failureSet.failure_sha256) || failureSet.run_id !== variant.run_id ||
      !isHash(failureSet.metric_id) || !isHash(failureSet.track_sha256) ||
      !isHash(failureSet.ground_truth_sha256)
    ) return missing(`Failure evidence for ${variant.name} is inconsistent.`)
    variantNames.add(variant.name)
    runIds.set(variant.name, variant.run_id)
    failureSetTotal += failureSet.event_count
    if (variant.baseline) baselineCount += 1
  }
  if (baselineCount !== 1 || !variantNames.has(experiment.baseline)) {
    return missing("The declared baseline does not match exactly one variant.")
  }
  const baselineVariant = value.variants.find(
    (variant) => isRecord(variant) && variant.name === experiment.baseline,
  )
  if (!isRecord(baselineVariant) || baselineVariant.baseline !== true) {
    return missing("The declared baseline variant is not marked as the baseline.")
  }

  if (!Array.isArray(value.failures)) return missing("The failure event list is missing.")
  const failures = value.failures
  for (const failure of failures) {
    if (
      !isRecord(failure) || !isNonEmptyString(failure.variant) || !variantNames.has(failure.variant) ||
      !isHash(failure.event_id) || !isHash(failure.run_id) || failure.run_id !== runIds.get(failure.variant) ||
      !isNonNegativeInteger(failure.frame_index) || failure.frame_index < experiment.frame_range.start ||
      failure.frame_index >= experiment.frame_range.end || !failureTypes.includes(failure.event_type as FailureType) ||
      !isIdArray(failure.track_ids) || !isIdArray(failure.ground_truth_ids) || !isRecord(failure.context) ||
      !isRecord(failure.evidence_frames) || !isNonNegativeInteger(failure.evidence_frames.start) ||
      !isPositiveInteger(failure.evidence_frames.end) ||
      failure.evidence_frames.start >= failure.evidence_frames.end ||
      failure.evidence_frames.end > source.frame_count || failure.frame_index < failure.evidence_frames.start ||
      failure.frame_index >= failure.evidence_frames.end || failure.schema_version !== 1
    ) return missing("One or more failure events have invalid lineage or frame bounds.")
    if (failure.media_evidence !== undefined && !isMediaEvidence(
      failure.media_evidence,
      failure.evidence_frames.start,
      failure.evidence_frames.end,
    )) {
      return missing("One or more failure events have invalid media-evidence metadata.")
    }
  }

  if (
    !isNonNegativeInteger(value.failure_event_total) || value.failure_event_total !== failureSetTotal ||
    !isNonNegativeInteger(value.failure_event_displayed) || value.failure_event_displayed !== value.failures.length ||
    value.failure_event_total < value.failure_event_displayed ||
    typeof value.failure_events_truncated !== "boolean" ||
    value.failure_events_truncated !== (value.failure_event_total > value.failure_event_displayed)
  ) return missing("Failure event totals do not match the verified variant evidence.")

  if (value.media_evidence !== undefined) {
    const media = value.media_evidence
    let displayedManifests = 0
    let displayedArtifacts = 0
    const displayedPrivacyMinimums = { ...privacyCountShape }
    for (const failure of failures) {
      const eventMedia = failure.media_evidence as ReportMediaEvidence | undefined
      if (!eventMedia) continue
      if (eventMedia.status !== "not_declared") displayedManifests += 1
      displayedArtifacts += eventMedia.artifact_count
      for (const privacy of eventMedia.privacy) displayedPrivacyMinimums[privacy] += 1
    }
    if (
      !isRecord(media) || !isNonNegativeInteger(media.event_manifests) ||
      !isNonNegativeInteger(media.image_artifacts) || !isRecord(media.privacy_counts) ||
      !hasSameKeys(media.privacy_counts, privacyCountShape) ||
      !privacyClasses.every((item) => isNonNegativeInteger(media.privacy_counts[item])) ||
      media.images_embedded !== false || media.event_manifests > value.failure_event_total ||
      media.event_manifests < displayedManifests || media.image_artifacts < displayedArtifacts ||
      privacyClasses.some((item) => Number(media.privacy_counts[item]) < displayedPrivacyMinimums[item]) ||
      privacyClasses.reduce((count, item) => count + Number(media.privacy_counts[item]), 0) !== media.image_artifacts ||
      failures.some((failure) => failure.media_evidence === undefined)
    ) return missing("The report media-evidence summary is invalid.")
  }

  const decision = value.decision
  if (
    !isRecord(decision) || !isNonEmptyString(decision.status) ||
    !(decision.accepted_variant === null ||
      (isNonEmptyString(decision.accepted_variant) && variantNames.has(decision.accepted_variant))) ||
    !isNonEmptyString(decision.reason)
  ) return missing("The human decision boundary is missing or invalid.")
  if (!Array.isArray(value.limitations) || value.limitations.length === 0 || !value.limitations.every(isNonEmptyString)) {
    return missing("The report must state at least one non-empty limitation.")
  }
  return { kind: "ready", report: value as unknown as ReliabilityReport }
}
