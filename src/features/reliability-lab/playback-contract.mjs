import { canonicalJson, sha256Canonical } from "./decision-contract.mjs"

const hashPattern = /^[a-f0-9]{64}$/
const variantPattern = /^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$/
const privacyClasses = new Set(["source_pixels", "redacted", "synthetic"])
const topFields = [
  "anchor_event_id", "baseline", "comparison_id", "event_frame_index", "experiment_id",
  "frame_range", "lanes", "playback_id", "report_id", "schema_version", "source_id", "variant",
]
const laneFields = ["frames", "run_id", "schema_version", "variant"]
const frameFields = [
  "frame_index", "image_sha256", "offset_ms", "privacy", "relative_path", "schema_version", "status",
]

const isRecord = (value) => typeof value === "object" && value !== null && !Array.isArray(value)
const isHash = (value) => typeof value === "string" && hashPattern.test(value)
const isInteger = (value) => Number.isSafeInteger(value)
const hasExactFields = (value, fields) =>
  isRecord(value) && Object.keys(value).length === fields.length && fields.every((field) => field in value)
const isSafePath = (value) => {
  if (typeof value !== "string" || value.length === 0 || value.startsWith("/") || value.includes("\\")) return false
  const parts = value.split("/")
  return !parts[0].includes(":") && parts.every((part) => part !== "" && part !== "." && part !== "..")
}

function validateFrame(value) {
  if (!hasExactFields(value, frameFields) || value.schema_version !== 1 ||
      !isInteger(value.frame_index) || value.frame_index < 0 ||
      !(value.offset_ms === null || (isInteger(value.offset_ms) && value.offset_ms >= 0)) ||
      !["available", "missing"].includes(value.status)) return false
  if (value.status === "missing") {
    return value.relative_path === null && value.image_sha256 === null && value.privacy === null
  }
  return isSafePath(value.relative_path) && isHash(value.image_sha256) && privacyClasses.has(value.privacy)
}

function validateLane(value) {
  if (!hasExactFields(value, laneFields) || value.schema_version !== 1 ||
      typeof value.variant !== "string" || !variantPattern.test(value.variant) ||
      !isHash(value.run_id) || !Array.isArray(value.frames) || value.frames.length === 0 ||
      !value.frames.every(validateFrame)) return false
  const indices = value.frames.map((frame) => frame.frame_index)
  if (indices.some((index, position) => position > 0 && index <= indices[position - 1])) return false
  const offsets = value.frames.map((frame) => frame.offset_ms)
  const unknown = offsets.some((offset) => offset === null)
  if (unknown) return offsets.every((offset) => offset === null)
  return offsets[0] === 0 && offsets.every(
    (offset, position) => position === 0 || offset > offsets[position - 1],
  )
}

export function validateFailurePlayback(value) {
  const fail = (error) => ({ valid: false, error })
  if (!hasExactFields(value, topFields)) return fail("The playback structure is invalid.")
  if (value.schema_version !== 1) return fail("The playback schema version is unsupported.")
  if (!isHash(value.playback_id) || !isHash(value.experiment_id) || !isHash(value.source_id) ||
      !isHash(value.comparison_id) || !isHash(value.report_id) || !isHash(value.anchor_event_id)) {
    return fail("The playback lineage fingerprints are invalid.")
  }
  if (!isInteger(value.event_frame_index) || value.event_frame_index < 0 ||
      !hasExactFields(value.frame_range, ["end", "start"]) ||
      !isInteger(value.frame_range.start) || !isInteger(value.frame_range.end) ||
      value.frame_range.start < 0 || value.frame_range.end <= value.frame_range.start ||
      value.event_frame_index < value.frame_range.start || value.event_frame_index >= value.frame_range.end ||
      value.frame_range.end - value.frame_range.start > 301) {
    return fail("The playback frame window is invalid or unbounded.")
  }
  if (typeof value.baseline !== "string" || !variantPattern.test(value.baseline) ||
      typeof value.variant !== "string" || !variantPattern.test(value.variant) ||
      value.baseline === value.variant || !Array.isArray(value.lanes) || value.lanes.length !== 2 ||
      !value.lanes.every(validateLane) || value.lanes[0].variant !== value.baseline ||
      value.lanes[1].variant !== value.variant || value.lanes[0].run_id === value.lanes[1].run_id) {
    return fail("The playback lanes do not define one distinct baseline/variant pair.")
  }
  const expectedIndices = Array.from(
    { length: value.frame_range.end - value.frame_range.start },
    (_, index) => value.frame_range.start + index,
  )
  const timing = value.lanes[0].frames.map((frame) => frame.offset_ms)
  for (const lane of value.lanes) {
    if (lane.frames.length !== expectedIndices.length || lane.frames.some(
      (frame, index) => frame.frame_index !== expectedIndices[index] || frame.offset_ms !== timing[index],
    )) return fail("The playback lanes are not synchronized over the complete frame window.")
  }
  return { valid: true }
}

export async function verifyFailurePlayback(value) {
  const validation = validateFailurePlayback(value)
  if (!validation.valid) return validation
  const content = { ...value }
  delete content.playback_id
  if (await sha256Canonical(content) !== value.playback_id) {
    return { valid: false, error: "The playback fingerprint does not match its content." }
  }
  return { valid: true }
}

export function serializePlayback(value) {
  return `${canonicalJson(value)}\n`
}

export async function sha256Text(value) {
  const bytes = new TextEncoder().encode(value)
  const digest = await globalThis.crypto.subtle.digest("SHA-256", bytes)
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("")
}
