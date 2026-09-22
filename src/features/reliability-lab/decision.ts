import type { ReliabilityReport } from "./types"

export interface LabDecision {
  decision_id: string
  experiment_id: string
  source_id: string
  comparison_id: string
  report_id: string
  status: "accepted" | "rejected_all"
  accepted_variant: string | null
  rationale: string
  author: string
  decided_at: string
  schema_version: 1
}

export interface VerifiedDecision {
  decision: LabDecision
  filename: string
}

export interface DecisionDraftInput {
  status: "accepted" | "rejected_all"
  acceptedVariant: string | null
  rationale: string
  author: string
  decidedAt: string
}

const maxDecisionBytes = 1024 * 1024
const hashPattern = /^[a-f0-9]{64}$/
const decisionFields = [
  "accepted_variant", "author", "comparison_id", "decided_at", "decision_id",
  "experiment_id", "rationale", "report_id", "schema_version", "source_id", "status",
]

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value)
const isHash = (value: unknown): value is string =>
  typeof value === "string" && hashPattern.test(value)
const isTrimmedString = (value: unknown, maximum: number): value is string =>
  typeof value === "string" && value === value.trim() && value.length >= 1 && value.length <= maximum
const isNonEmptyTrimmedString = (value: unknown): value is string =>
  typeof value === "string" && value === value.trim() && value.length >= 1
const hasExactFields = (value: Record<string, unknown>, fields: string[]) => {
  const actual = Object.keys(value).sort()
  const expected = [...fields].sort()
  return actual.length === expected.length && actual.every((field, index) => field === expected[index])
}
const isUtcTimestamp = (value: unknown): value is string =>
  typeof value === "string" && /(?:Z|\+00(?::?00)?)$/.test(value) && !Number.isNaN(Date.parse(value))

function canonicalJson(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(",")}]`
  if (isRecord(value)) {
    return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${canonicalJson(value[key])}`).join(",")}}`
  }
  const rendered = JSON.stringify(value)
  if (rendered === undefined) throw new Error("The selected record contains a value that cannot be hashed.")
  return rendered
}

async function sha256(value: unknown) {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(canonicalJson(value)))
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("")
}

function parseDecision(value: unknown): LabDecision | null {
  if (!isRecord(value) || !hasExactFields(value, decisionFields)) return null
  const accepted = value.status === "accepted"
  const rejected = value.status === "rejected_all"
  if (
    value.schema_version !== 1 || !isHash(value.decision_id) || !isHash(value.experiment_id) ||
    !isHash(value.source_id) || !isHash(value.comparison_id) || !isHash(value.report_id) ||
    (!accepted && !rejected) ||
    (accepted && !isNonEmptyTrimmedString(value.accepted_variant)) ||
    (rejected && value.accepted_variant !== null) ||
    !isTrimmedString(value.rationale, 5000) || !isTrimmedString(value.author, 200) ||
    !isUtcTimestamp(value.decided_at)
  ) return null
  return value as unknown as LabDecision
}

export async function createDecisionDraft(
  report: ReliabilityReport,
  input: DecisionDraftInput,
): Promise<LabDecision> {
  if (report.decision.status !== "not_selected" || report.decision.accepted_variant !== null) {
    throw new Error("The active report does not preserve the unselected decision boundary.")
  }
  if (input.status !== "accepted" && input.status !== "rejected_all") {
    throw new Error("Choose whether to accept one variant or reject all variants.")
  }
  const acceptedVariant = input.status === "accepted" ? input.acceptedVariant : null
  if (input.status === "accepted" &&
    (!isNonEmptyTrimmedString(acceptedVariant) ||
      !report.variants.some((variant) => variant.name === acceptedVariant))) {
    throw new Error("Choose one verified variant to accept.")
  }
  if (!isTrimmedString(input.rationale, 5000)) {
    throw new Error("Rationale must be 1–5000 characters with no surrounding whitespace.")
  }
  if (!isTrimmedString(input.author, 200)) {
    throw new Error("Author must be 1–200 characters with no surrounding whitespace.")
  }
  if (!isUtcTimestamp(input.decidedAt)) {
    throw new Error("Decision time must be a valid UTC timestamp.")
  }
  const content = {
    experiment_id: report.experiment.experiment_id,
    source_id: report.source.source_id,
    comparison_id: report.comparison_id,
    report_id: report.report_id,
    status: input.status,
    accepted_variant: acceptedVariant,
    rationale: input.rationale,
    author: input.author,
    decided_at: input.decidedAt,
    schema_version: 1 as const,
  }
  return { decision_id: await sha256(content), ...content }
}

export function serializeDecision(decision: LabDecision) {
  return `${canonicalJson(decision)}\n`
}

function verifyLineage(decision: LabDecision, report: ReliabilityReport) {
  if (
    decision.experiment_id !== report.experiment.experiment_id ||
    decision.source_id !== report.source.source_id ||
    decision.comparison_id !== report.comparison_id ||
    decision.report_id !== report.report_id
  ) throw new Error("The decision does not match the active report lineage.")
  if (decision.accepted_variant !== null &&
    !report.variants.some((variant) => variant.name === decision.accepted_variant)) {
    throw new Error("The accepted variant is not present in the active report.")
  }
}

export async function verifyDecisionFile(
  file: File,
  report: ReliabilityReport,
): Promise<VerifiedDecision> {
  if (file.name !== "decision.json") throw new Error("Select exactly one file named decision.json.")
  if (file.size === 0 || file.size > maxDecisionBytes) {
    throw new Error("The selected decision.json is empty or too large.")
  }
  let parsed: unknown
  try {
    parsed = JSON.parse(await file.text()) as unknown
  } catch {
    throw new Error("The selected decision.json is not valid JSON.")
  }
  const decision = parseDecision(parsed)
  if (!decision) throw new Error("The decision structure or schema version is invalid.")
  const content = { ...parsed as Record<string, unknown> }
  delete content.decision_id
  if (await sha256(content) !== decision.decision_id) {
    throw new Error("The decision fingerprint does not match its content.")
  }
  verifyLineage(decision, report)
  return { decision, filename: file.name }
}
