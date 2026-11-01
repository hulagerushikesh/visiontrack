import type { ReliabilityReport } from "./types"
import { canonicalJson } from "./decision-contract.mjs"
import { verifyContentFingerprint } from "./report-import"
import { parseDiagnosticDocument, validateDiagnosticMetadata, verifyDiagnosticLineage, type InitiationDetection, type InitiationFrame, type InitiationTrace } from "./initiation"

export const maxAssociationBytes = 1024 * 1024
export const stageLabels = {
  confirmed_high: "1. Confirmed tracks · high scores",
  confirmed_low: "2. Unmatched confirmed tracks · recovery scores",
  tentative_high: "3. Tentative tracks · remaining high scores",
} as const
export const outcomeLabels = {
  selected: "Pair selected",
  blocked_by_gate: "Pair blocked by a gate",
  above_cost_limit: "Pair exceeded the cost limit",
  eligible_not_selected: "Pair eligible, but not selected",
} as const
export interface AssociationSelection { frame: number; trackId: number; detectionIndex: number }
export interface AssociationPair {
  predicted_xyxy: number[]; track_class_id: number; iou: number; minimum_iou: number
  class_gate_enabled: boolean; class_mismatch: boolean
  mahalanobis_squared: number | null; mahalanobis_limit: number | null
  failed_gates: Array<"iou" | "class" | "mahalanobis">
  solver_cost: number; maximum_cost: number; cost_eligible: boolean
  outcome: keyof typeof outcomeLabels
  track_matched_detection_index: number | null; detection_matched_track_id: number | null
}
export interface AssociationStage {
  stage: keyof typeof stageLabels; track_count: number; detection_count: number
  track_offered: boolean; detection_offered: boolean; pair: AssociationPair | null
}
export interface AssociationExplanation extends Pick<InitiationTrace, "experiment_id" | "source_id" | "variant" | "run_id" | "detection_sha256" | "track_sha256" | "replay_frame_range" | "config" | "producer" | "public_output_parity" | "accuracy_claim" | "physical_identity_verified" | "limits"> {
  schema: "visiontrack.association-explanation/v1"; explanation_id: string
  frame_index: number; track_id: number; detection_index: number
  detection: InitiationDetection; stages: AssociationStage[]
}
const object = (v: unknown): v is Record<string, any> => typeof v === "object" && v !== null && !Array.isArray(v)
const integer = (v: unknown): v is number => Number.isSafeInteger(v) && (v as number) >= 0
const finite = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v)
const same = (a: unknown, b: unknown) => canonicalJson(a) === canonicalJson(b)
function require(condition: unknown, message: string): asserts condition { if (!condition) throw new Error(message) }
function keys(value: unknown, expected: string) {
  require(object(value) && Object.keys(value).sort().join(" ") === expected.split(" ").sort().join(" "), "Unsupported or incomplete association structure.")
}

/** The caller supplies the already verified active trace, never an unrelated file. */
export async function verifyAssociationExplanation(text: string, report: ReliabilityReport, trace: InitiationTrace, selection: AssociationSelection): Promise<AssociationExplanation> {
  require(new TextEncoder().encode(text).byteLength <= maxAssociationBytes, "Explanation exceeds the 1 MiB import limit.")
  const { value: e, raw } = parseDiagnosticDocument(text)
  keys(e, "schema explanation_id experiment_id source_id variant run_id detection_sha256 track_sha256 replay_frame_range config producer public_output_parity accuracy_claim physical_identity_verified limits frame_index track_id detection_index detection stages")
  require(e.schema === "visiontrack.association-explanation/v1", "Unsupported association explanation version.")
  require(typeof e.explanation_id === "string" && /^[a-f0-9]{64}$/.test(e.explanation_id), "Invalid explanation identifier.")
  validateDiagnosticMetadata(e)
  require(integer(e.frame_index) && integer(e.track_id) && e.track_id > 0 && integer(e.detection_index), "Invalid pair selectors.")
  require(e.frame_index === selection.frame && e.track_id === selection.trackId && e.detection_index === selection.detectionIndex, "This explanation is for a different frame or pair. Select its exact frame, track and detection first.")
  for (const key of ["experiment_id", "source_id", "variant", "run_id", "detection_sha256", "track_sha256", "config", "replay_frame_range"] as const) require(same(e[key], trace[key]), "Explanation does not belong to the active initiation trace/run.")
  const frame = trace.frames.find(f => f.frame_index === e.frame_index)
  const track = frame?.tracks.find(t => t.track_id === e.track_id && t.previous_state !== null)
  const detection = frame?.detections.find(d => d.detection_index === e.detection_index)
  require(frame && track && detection, "Select an existing pre-association track and an original detection key in the active trace frame.")
  require(same(e.detection, detection), "Explanation detection differs from the active trace.")
  require(await verifyContentFingerprint(text, e.explanation_id, "explanation_id"), "Explanation fingerprint does not match its contents. Export the original canonical JSON again.")
  await verifyDiagnosticLineage(e, raw.get("config")!, report)
  const c = e.config
  const detectionsByKey = new Map(frame.detections.map(d => [d.detection_index, d]))
  const stages = Object.keys(stageLabels) as Array<keyof typeof stageLabels>
  require(Array.isArray(e.stages) && e.stages.length === 3, "Explanation must contain all three association stages.")
  for (const [offset, stage] of e.stages.entries()) {
    keys(stage, "stage track_count detection_count track_offered detection_offered pair")
    require(stage.stage === stages[offset], "Association stages must retain production order.")
    const name = stages[offset]
    const assignedInStage = (key: number | null) => key !== null && detectionsByKey.get(key)?.disposition === `matched_${name}`
    const offeredTracks = frame.tracks.filter(t => name === "tentative_high" ? t.previous_state === "tentative" : t.previous_state === "confirmed" && (name !== "confirmed_low" || t.detection_index === null || detectionsByKey.get(t.detection_index)?.disposition !== "matched_confirmed_high"))
    const offeredDetections = frame.detections.filter(d => name === "confirmed_low" ? d.score >= c.low_score_thresh && d.score < c.high_score_thresh : d.score >= c.high_score_thresh && (name !== "tentative_high" || d.disposition !== "matched_confirmed_high"))
    require(stage.track_count === offeredTracks.length && stage.detection_count === offeredDetections.length && stage.track_offered === offeredTracks.some(t => t.track_id === e.track_id) && stage.detection_offered === offeredDetections.some(d => d.detection_index === e.detection_index), "Stage inputs disagree with the active trace.")
    const offered = stage.track_offered && stage.detection_offered
    if (!offered) { require(stage.pair === null, "A pair not offered cannot declare a gate result."); continue }
    const p = stage.pair
    keys(p, "predicted_xyxy track_class_id iou minimum_iou class_gate_enabled class_mismatch mahalanobis_squared mahalanobis_limit failed_gates solver_cost maximum_cost cost_eligible outcome track_matched_detection_index detection_matched_track_id")
    require(Array.isArray(p.predicted_xyxy) && p.predicted_xyxy.length === 4 && p.predicted_xyxy.every(finite) && p.predicted_xyxy[2] > p.predicted_xyxy[0] && p.predicted_xyxy[3] > p.predicted_xyxy[1], "Invalid predicted track box.")
    require(Number.isSafeInteger(p.track_class_id) && p.track_class_id >= -1 && finite(p.iou) && p.iou >= 0 && p.iou <= 1, "Invalid pair geometry or class.")
    require(p.minimum_iou === (name === "confirmed_low" ? c.recovery_iou_thresh : c.match_iou_thresh) && p.class_gate_enabled === c.class_aware && p.class_mismatch === (c.class_aware && p.track_class_id !== -1 && detection.class_id !== -1 && p.track_class_id !== detection.class_id), "Pair gate settings disagree with its configuration.")
    const gated = name !== "confirmed_low" && c.use_mahalanobis_gating
    require(gated ? finite(p.mahalanobis_limit) && p.mahalanobis_limit > 0 : p.mahalanobis_limit === null, "Invalid hard Kalman gate state.")
    require(gated || c.w_unc > 0 ? finite(p.mahalanobis_squared) && p.mahalanobis_squared >= 0 : p.mahalanobis_squared === null, "Invalid Kalman distance availability.")
    const failures = [p.iou < p.minimum_iou && "iou", p.class_mismatch && "class", gated && p.mahalanobis_squared > p.mahalanobis_limit && "mahalanobis"].filter(Boolean)
    require(same(p.failed_gates, failures), "Failed gates disagree with the recorded numeric comparisons.")
    require(finite(p.solver_cost) && finite(p.maximum_cost) && p.cost_eligible === (p.solver_cost <= p.maximum_cost), "Invalid cost eligibility.")
    require(failures.length === 0 || !p.cost_eligible, "A hard-blocked pair cannot be cost eligible.")
    const trackPartner = assignedInStage(track.detection_index) ? track.detection_index : null
    const detectionPartner = detection.disposition === `matched_${name}` ? detection.track_id : null
    require(p.track_matched_detection_index === trackPartner && p.detection_matched_track_id === detectionPartner, "Returned partners disagree with the active trace.")
    const selected = trackPartner === e.detection_index && detectionPartner === e.track_id
    require(!selected || p.cost_eligible, "A selected pair must be cost eligible.")
    const outcome = selected ? "selected" : failures.length ? "blocked_by_gate" : !p.cost_eligible ? "above_cost_limit" : "eligible_not_selected"
    require(p.outcome === outcome, "Pair outcome contradicts its gates, cost or assignment.")
  }
  return e as AssociationExplanation
}

export function associationCommand(variant: string, selection: AssociationSelection) {
  return `visiontrack lab-association "BUNDLE_PATH" --variant ${variant} --frame ${selection.frame} --track-id ${selection.trackId} --detection-index ${selection.detectionIndex} --json > association.json`
}
export function availableAssociationTracks(frame: InitiationFrame) { return frame.tracks.filter(t => t.previous_state !== null) }
export type AssociationLoadResult = { kind: "ready"; explanation: AssociationExplanation } | { kind: "error"; message: string }
export class AssociationFileReader {
  private requestId = 0
  cancel() { this.requestId += 1 }
  async read(file: Pick<File, "size" | "text">, report: ReliabilityReport, trace: InitiationTrace, selection: AssociationSelection): Promise<AssociationLoadResult | null> {
    const id = ++this.requestId
    try {
      require(file.size > 0 && file.size <= maxAssociationBytes, "Select a nonempty explanation JSON file of at most 1 MiB.")
      const text = await file.text()
      if (id !== this.requestId) return null
      const explanation = await verifyAssociationExplanation(text, report, trace, selection)
      return id === this.requestId ? { kind: "ready", explanation } : null
    } catch (error) {
      return id === this.requestId ? { kind: "error", message: error instanceof Error ? error.message : "The explanation could not be checked." } : null
    }
  }
}
