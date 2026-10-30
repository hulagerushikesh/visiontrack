import type { ReliabilityReport } from "./types"
import { verifyContentFingerprint } from "./report-import"
import { canonicalJson } from "./decision-contract.mjs"

export const maxTraceBytes = 16 * 1024 * 1024
export const dispositionLabels = {
  below_low_score: "Below the recovery score",
  unmatched_low_score: "Recovery proposal remained unmatched; cannot start a track",
  below_birth_score: "Unmatched high-score proposal below the birth score",
  spawned_tentative: "Started a tentative track",
  matched_confirmed_high: "Updated a confirmed track in the high-score stage",
  matched_confirmed_low: "Recovered a confirmed track in the low-score stage",
  matched_tentative_high: "Matched a tentative track; check its new state below",
} as const
export const eventLabels = {
  born: "Born tentative", tentative_match: "Tentative match", confirmed_now: "Confirmed now",
  updated: "Updated", coasting: "Coasting internally", deleted_unconfirmed: "Tentative track deleted",
  deleted_expired: "Confirmed track expired",
} as const

type State = "tentative" | "confirmed" | "deleted"
export interface InitiationDetection {
  detection_index: number; xyxy: number[]; score: number; class_id: number
  disposition: keyof typeof dispositionLabels; track_id: number | null
}
export interface InitiationTrack {
  track_id: number; previous_state: State | null; state: State; event: keyof typeof eventLabels
  birth_frame: number; hits: number; age: number; time_since_update: number
  public: boolean; detection_index: number | null
}
export interface InitiationFrame {
  frame_index: number; detections: InitiationDetection[]; tracks: InitiationTrack[]; public_track_ids: number[]
}
export interface InitiationTrace {
  schema: "visiontrack.initiation-trace/v1"; trace_id: string; experiment_id: string; source_id: string
  variant: string; run_id: string; detection_sha256: string; track_sha256: string
  replay_frame_range: { start: number; end: number }; trace_frame_range: { start: number; end: number }
  config: Record<string, number | boolean | null>; frames: InitiationFrame[]
  producer: { visiontrack: string; python: string; numpy: string; implementation_sha256: Record<string, string> }
  public_output_parity: "exact_sha256_match"; accuracy_claim: false; physical_identity_verified: false; limits: string[]
}
const object = (v: unknown): v is Record<string, any> => typeof v === "object" && v !== null && !Array.isArray(v)
const integer = (v: unknown): v is number => Number.isSafeInteger(v) && (v as number) >= 0
const positive = (v: unknown): v is number => integer(v) && v > 0
const number = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v)
const hash = (v: unknown): v is string => typeof v === "string" && /^[a-f0-9]{64}$/.test(v)
function require(condition: unknown, message: string): asserts condition {
  if (!condition) throw new Error(message)
}
function keys(value: unknown, expected: string) {
  require(object(value) && Object.keys(value).sort().join(" ") === expected.split(" ").sort().join(" "), "Unsupported or incomplete trace structure. Regenerate the trace from the current source checkout.")
}
const range = (v: unknown) => object(v) && Object.keys(v).sort().join(" ") === "end start" && integer(v.start) && integer(v.end) && v.start < v.end
const same = (a: unknown, b: unknown) => canonicalJson(a) === canonicalJson(b)
const digest = async (text: string) => Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text))), b => b.toString(16).padStart(2, "0")).join("")

/** Reject duplicate keys at every depth; retain exact numeric bytes for Python hashes. */
function parseDocument(text: string): { value: any; raw: Map<string, string> } {
  const value: unknown = JSON.parse(text)
  const raw = new Map<string, string>()
  const stack: Array<{ keys: Set<string>; key: boolean } | null> = []
  let rootKey: string | null = null
  let start = 0
  // JSON.parse has already validated grammar; this token walk adds uniqueness/depth checks.
  const tokens = /"(?:\\[\s\S]|[^"\\])*"|[{}\[\],:]|true|false|null|-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?/g
  for (const match of text.matchAll(tokens)) {
    const token = match[0], at = match.index!
    const top = stack.at(-1)
    if (top?.key && token.startsWith('"')) {
      const key = JSON.parse(token) as string
      require(!top.keys.has(key), "Duplicate JSON keys are not accepted.")
      top.keys.add(key); top.key = false
      if (stack.length === 1) rootKey = key
    } else if (token === ":" && stack.length === 1) start = at + 1
    else if (token === "," || token === "}" || token === "]") {
      if (stack.length === 1 && rootKey !== null) {
        raw.set(rootKey, text.slice(start, at)); rootKey = null
      }
      if (token === ",") { if (top) top.key = true }
      else stack.pop()
    }
    if (token === "{" || token === "[") {
      stack.push(token === "{" ? { keys: new Set(), key: true } : null)
      require(stack.length <= 32, "Trace JSON is nested too deeply.")
    }
  }
  return { value, raw }
}

function validateShape(t: any): asserts t is InitiationTrace {
  keys(t, "schema trace_id experiment_id source_id variant run_id detection_sha256 track_sha256 replay_frame_range trace_frame_range config frames producer public_output_parity accuracy_claim physical_identity_verified limits")
  require(t.schema === "visiontrack.initiation-trace/v1", "Unsupported initiation trace version.")
  for (const key of ["trace_id", "experiment_id", "source_id", "run_id", "detection_sha256", "track_sha256"]) require(hash(t[key]), "Invalid trace identifier.")
  require(typeof t.variant === "string" && /^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$/.test(t.variant), "Invalid trace variant.")
  require(range(t.replay_frame_range) && range(t.trace_frame_range), "Invalid trace frame range.")
  const { start, end } = t.trace_frame_range
  require(start >= t.replay_frame_range.start && end <= t.replay_frame_range.end && end - start <= 200, "Trace window must contain 1–200 frames inside the original run.")
  require(t.public_output_parity === "exact_sha256_match" && t.accuracy_claim === false && t.physical_identity_verified === false, "Trace must retain its diagnostic-only boundaries.")
  require(Array.isArray(t.limits) && t.limits.length > 0 && t.limits.length <= 16 && t.limits.every((s: unknown) => typeof s === "string" && s.length > 0 && s.length <= 1024), "Invalid diagnostic limitations.")
  keys(t.producer, "visiontrack python numpy implementation_sha256")
  require([t.producer.visiontrack, t.producer.python, t.producer.numpy].every(s => typeof s === "string" && s.length > 0 && s.length <= 128), "Invalid producer versions.")
  require(object(t.producer.implementation_sha256), "Missing producer source hashes.")
  const sources = Object.entries(t.producer.implementation_sha256)
  require(sources.length > 0 && sources.length <= 512 && sources.every(([p, h]) => p.length <= 256 && !p.startsWith("/") && !p.includes("\\") && p.split("/").every(part => part !== ".." && part !== "." && part !== "") && p.endsWith(".py") && hash(h)), "Invalid producer source hashes.")
  const c = t.config
  keys(c, "appearance_ema_alpha class_aware high_score_thresh kf_noise_scale low_score_thresh match_iou_thresh max_age motion_residual_path n_init new_track_thresh ocm_delta_t recovery_iou_thresh use_giou use_gmc use_mahalanobis_gating use_oru w_app w_iou w_ocm w_unc")
  for (const key of ["class_aware", "use_giou", "use_gmc", "use_mahalanobis_gating", "use_oru"]) require(typeof c[key] === "boolean", "Invalid tracker switch.")
  for (const key of ["high_score_thresh", "low_score_thresh", "new_track_thresh", "match_iou_thresh", "recovery_iou_thresh", "appearance_ema_alpha", "kf_noise_scale", "w_iou", "w_app", "w_unc", "w_ocm"]) require(number(c[key]), "Invalid numeric tracker configuration.")
  require(c.low_score_thresh >= 0 && c.low_score_thresh <= c.high_score_thresh && c.high_score_thresh <= 1 && positive(c.n_init) && positive(c.max_age) && positive(c.ocm_delta_t), "Invalid tracker thresholds or lifecycle settings.")
  require(c.motion_residual_path === null && c.w_app === 0 && c.use_gmc === false, "Trace requires unsupported external features.")
  require(Array.isArray(t.frames) && t.frames.length === end - start, "Trace frames do not cover the selected window.")
  let rows = 0
  let previous: Map<number, InitiationTrack> | null = null
  const seenIds = new Set<number>()
  for (const [offset, f] of t.frames.entries()) {
    keys(f, "frame_index detections tracks public_track_ids")
    require(f.frame_index === start + offset && Array.isArray(f.detections) && Array.isArray(f.tracks) && Array.isArray(f.public_track_ids), "Invalid or non-contiguous trace frames.")
    rows += f.detections.length + f.tracks.length
    require(rows <= 20_000, "Trace exceeds 20,000 detection/track rows.")
    const detections = new Map<number, InitiationDetection>()
    const assigned = new Set<number>()
    for (const d of f.detections) {
      keys(d, "detection_index xyxy score class_id disposition track_id")
      require(integer(d.detection_index) && !detections.has(d.detection_index) && integer(d.class_id) && number(d.score) && d.score >= 0 && d.score <= 1, "Invalid detection key, class or score.")
      require(Array.isArray(d.xyxy) && d.xyxy.length === 4 && d.xyxy.every(number) && d.xyxy[2] > d.xyxy[0] && d.xyxy[3] > d.xyxy[1], "Invalid detection box.")
      require(Object.hasOwn(dispositionLabels, d.disposition), "Unknown detection disposition.")
      const linked = d.disposition === "spawned_tentative" || d.disposition.startsWith("matched_")
      require(linked ? positive(d.track_id) && !assigned.has(d.track_id) : d.track_id === null, "Detection/track links are inconsistent.")
      const low = d.score < c.low_score_thresh, high = d.score >= c.high_score_thresh
      require(d.disposition === "below_low_score" ? low : d.disposition === "unmatched_low_score" || d.disposition === "matched_confirmed_low" ? !low && !high : high, "Disposition conflicts with score admission.")
      if (d.disposition === "below_birth_score") require(d.score < c.new_track_thresh, "Birth rejection conflicts with its threshold.")
      if (d.disposition === "spawned_tentative") require(d.score >= c.new_track_thresh, "Birth conflicts with its threshold.")
      if (linked) assigned.add(d.track_id)
      detections.set(d.detection_index, d)
    }
    const tracks = new Map<number, InitiationTrack>()
    let lastId = 0
    for (const row of f.tracks) {
      keys(row, "track_id previous_state state event birth_frame hits age time_since_update public detection_index")
      require(positive(row.track_id) && row.track_id > lastId, "Track IDs must be unique and sorted.")
      lastId = row.track_id
      require(["tentative", "confirmed", "deleted"].includes(row.state) && (row.previous_state === null || ["tentative", "confirmed"].includes(row.previous_state)) && Object.hasOwn(eventLabels, row.event), "Invalid track lifecycle state.")
      require(integer(row.birth_frame) && row.birth_frame >= t.replay_frame_range.start && row.birth_frame <= f.frame_index && positive(row.age) && row.age === f.frame_index - row.birth_frame + 1 && positive(row.hits) && row.hits <= row.age && integer(row.time_since_update) && row.time_since_update <= row.age && typeof row.public === "boolean", "Invalid track lifecycle counters.")
      require(row.public === (row.state === "confirmed" && row.time_since_update === 0), "Internal state and public output disagree.")
      require((row.event === "born") === (row.birth_frame === f.frame_index), "Track birth and history disagree.")
      if (row.event === "born") require(!seenIds.has(row.track_id), "A deleted track ID cannot be reused in the trace.")
      const linked = row.detection_index !== null
      require(linked ? integer(row.detection_index) && detections.get(row.detection_index)?.track_id === row.track_id && row.time_since_update === 0 : row.time_since_update > 0, "Track/detection correspondence is inconsistent.")
      const disposition = linked ? detections.get(row.detection_index)!.disposition : null
      const expected = row.event === "born" ? row.previous_state === null && row.state === "tentative" && disposition === "spawned_tentative" && row.birth_frame === f.frame_index && row.hits === 1 :
        row.event === "tentative_match" || row.event === "confirmed_now" ? row.previous_state === "tentative" && row.state === (row.event === "confirmed_now" ? "confirmed" : "tentative") && disposition === "matched_tentative_high" :
        row.event === "updated" ? row.previous_state === "confirmed" && row.state === "confirmed" && (disposition === "matched_confirmed_high" || disposition === "matched_confirmed_low") :
        row.event === "coasting" ? row.previous_state === "confirmed" && row.state === "confirmed" && !linked && row.time_since_update <= c.max_age :
        row.event === "deleted_unconfirmed" ? row.previous_state === "tentative" && row.state === "deleted" && !linked :
        row.previous_state === "confirmed" && row.state === "deleted" && !linked && row.time_since_update > c.max_age
      require(expected, "Track event conflicts with its state or association stage.")
      if (previous) {
        const prior = previous.get(row.track_id)
        require(prior ? prior.state !== "deleted" && prior.state === row.previous_state && prior.birth_frame === row.birth_frame && row.hits === prior.hits + (linked ? 1 : 0) && row.time_since_update === (linked ? 0 : prior.time_since_update + 1) : row.event === "born", "Track history is inconsistent across selected frames.")
      }
      seenIds.add(row.track_id)
      tracks.set(row.track_id, row)
    }
    require([...assigned].every(id => tracks.has(id)) && [...detections.values()].every(d => d.track_id === null || tracks.get(d.track_id)?.detection_index === d.detection_index), "A detection references an absent or different track row.")
    if (previous) require([...previous.values()].every(row => row.state === "deleted" || tracks.has(row.track_id)), "A surviving track disappeared from the trace.")
    require(same(f.public_track_ids, [...tracks.values()].filter(row => row.public).map(row => row.track_id)), "Public IDs disagree with track rows.")
    previous = tracks
  }
}

/** Checks content and declared lineage, not the truth or authenticity of a submitted record. */
export async function verifyInitiationTrace(text: string, report: ReliabilityReport): Promise<InitiationTrace> {
  const { value: trace, raw } = parseDocument(text)
  validateShape(trace)
  require(await verifyContentFingerprint(text, trace.trace_id, "trace_id"), "Trace fingerprint does not match its contents. Export the original canonical JSON again.")
  const variant = report.variants.find(v => v.name === trace.variant)
  require(variant && trace.experiment_id === report.experiment.experiment_id && trace.source_id === report.source.source_id && trace.detection_sha256 === report.source.detection_sha256 && trace.run_id === variant.run_id && trace.track_sha256 === variant.failure_set.track_sha256 && same(trace.replay_frame_range, report.experiment.frame_range), "This trace does not belong to the active report/run. Import its matching report.json first.")
  const count = variant.diagnostics.observation_count
  require(integer(count), "This report lacks the saved observation count needed to verify the trace configuration.")
  const rawConfig = raw.get("config")!
  const configHash = await digest(rawConfig)
  const content = { schema_version: 1, experiment_id: trace.experiment_id, source_id: trace.source_id, variant: trace.variant, config: trace.config, config_sha256: configHash, detection_sha256: trace.detection_sha256, frame_range: trace.replay_frame_range, track_sha256: trace.track_sha256, observation_count: count }
  // Preserve Python's exact 1.0/0.0 numeric tokens instead of reserializing them as JS integers.
  const runBytes = canonicalJson(content).replace(`"config":${canonicalJson(trace.config)},`, `"config":${rawConfig},`)
  require(await digest(runBytes) === trace.run_id, "Trace configuration does not reproduce the active report's run ID.")
  return trace
}

export type TraceLoadResult = { kind: "ready"; trace: InitiationTrace } | { kind: "error"; message: string }
export class InitiationFileReader {
  private requestId = 0
  cancel() { this.requestId += 1 }
  async read(file: Pick<File, "size" | "text">, report: ReliabilityReport): Promise<TraceLoadResult | null> {
    const id = ++this.requestId
    try {
      require(file.size > 0 && file.size <= maxTraceBytes, "Select a nonempty trace JSON file of at most 16 MiB.")
      const text = await file.text()
      if (id !== this.requestId) return null
      const trace = await verifyInitiationTrace(text, report)
      return id === this.requestId ? { kind: "ready", trace } : null
    } catch (error) {
      return id === this.requestId ? { kind: "error", message: error instanceof Error ? error.message : "The selected trace could not be checked." } : null
    }
  }
}
