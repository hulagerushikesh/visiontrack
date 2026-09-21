import type { ReliabilityReport, ReportFailure } from "./types"

export type EvidencePrivacy = "source_pixels" | "redacted" | "synthetic"
export type EvidenceView = "full_frame" | "crop"

export interface EvidenceArtifact {
  relative_path: string
  frame_index: number
  image_sha256: string
  byte_length: number
  media_type: "image/png"
  width: number
  height: number
  view: EvidenceView
  privacy: EvidencePrivacy
  source_image_sha256?: string
  production?: {
    kind: EvidenceView
    crop_bounds: [number, number, number, number] | null
    redaction: "pixelate_max_8x8" | null
  }
  schema_version: 1
}

export interface EvidenceManifest {
  evidence_id: string
  source_id: string
  run_id: string
  event_id: string
  event_frame_index: number
  evidence_frames: { start: number; end: number }
  artifacts: EvidenceArtifact[]
  schema_version: 1
}

export interface VerifiedEvidenceArtifact {
  artifact: EvidenceArtifact
  file: File
}

export interface VerifiedEvidence {
  manifest: EvidenceManifest
  manifestFilename: string
  artifacts: VerifiedEvidenceArtifact[]
}

const hashPattern = /^[a-f0-9]{64}$/
const maxManifestBytes = 1024 * 1024
const maxEvidenceArtifacts = 25
const maxEvidenceImageBytes = 16 * 1024 * 1024
const maxEvidenceImagePixels = 4_194_304
const manifestFields = [
  "artifacts", "event_frame_index", "event_id", "evidence_frames", "evidence_id",
  "run_id", "schema_version", "source_id",
]
const artifactFields = [
  "byte_length", "frame_index", "height", "image_sha256", "media_type", "privacy",
  "relative_path", "schema_version", "view", "width",
]
const producedArtifactFields = [...artifactFields, "production", "source_image_sha256"]

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value)
const isInteger = (value: unknown): value is number => Number.isInteger(value)
const isNonNegativeInteger = (value: unknown): value is number => isInteger(value) && value >= 0
const isPositiveInteger = (value: unknown): value is number => isInteger(value) && value > 0
const isHash = (value: unknown): value is string => typeof value === "string" && hashPattern.test(value)
const hasExactFields = (value: Record<string, unknown>, fields: string[]) => {
  const actual = Object.keys(value).sort()
  const expected = [...fields].sort()
  return actual.length === expected.length && actual.every((field, index) => field === expected[index])
}
const isSafeFilename = (value: unknown): value is string =>
  typeof value === "string" && /^[^/\\]+\.png$/.test(value) && ![".", ".."].includes(value)

function isProduction(value: unknown, artifact: Record<string, unknown>) {
  if (!isRecord(value) || !hasExactFields(value, ["crop_bounds", "kind", "redaction"])) return false
  if (value.kind !== artifact.view || !["crop", "full_frame"].includes(String(value.kind))) return false
  if (!(value.redaction === null || value.redaction === "pixelate_max_8x8")) return false
  if ((artifact.privacy === "redacted") !== (value.redaction !== null)) return false
  if (value.kind === "full_frame") return value.crop_bounds === null
  if (!Array.isArray(value.crop_bounds) || value.crop_bounds.length !== 4 || !value.crop_bounds.every(isInteger)) {
    return false
  }
  const [left, top, right, bottom] = value.crop_bounds
  return left >= 0 && top >= 0 && right > left && bottom > top &&
    right - left === artifact.width && bottom - top === artifact.height
}

function parseArtifact(value: unknown, start: number, end: number): EvidenceArtifact | null {
  if (!isRecord(value)) return null
  const produced = "production" in value || "source_image_sha256" in value
  if (!hasExactFields(value, produced ? producedArtifactFields : artifactFields)) return null
  if (
    !isSafeFilename(value.relative_path) || !isNonNegativeInteger(value.frame_index) ||
    value.frame_index < start || value.frame_index >= end || !isHash(value.image_sha256) ||
    !isPositiveInteger(value.byte_length) || value.byte_length > maxEvidenceImageBytes ||
    value.media_type !== "image/png" ||
    !isPositiveInteger(value.width) || !isPositiveInteger(value.height) ||
    value.width * value.height > maxEvidenceImagePixels ||
    !["full_frame", "crop"].includes(String(value.view)) ||
    !["source_pixels", "redacted", "synthetic"].includes(String(value.privacy)) ||
    value.schema_version !== 1
  ) return null
  if (produced && (!isHash(value.source_image_sha256) || !isProduction(value.production, value))) return null
  return value as unknown as EvidenceArtifact
}

function parseManifest(value: unknown): EvidenceManifest | null {
  if (!isRecord(value) || !hasExactFields(value, manifestFields)) return null
  const bounds = value.evidence_frames
  if (
    value.schema_version !== 1 || !isHash(value.evidence_id) || !isHash(value.source_id) ||
    !isHash(value.run_id) || !isHash(value.event_id) || !isNonNegativeInteger(value.event_frame_index) ||
    !isRecord(bounds) || !hasExactFields(bounds, ["end", "start"]) ||
    !isNonNegativeInteger(bounds.start) || !isPositiveInteger(bounds.end) ||
    bounds.start >= bounds.end || value.event_frame_index < bounds.start || value.event_frame_index >= bounds.end ||
    !Array.isArray(value.artifacts) || value.artifacts.length > maxEvidenceArtifacts
  ) return null
  const artifacts = value.artifacts.map((artifact) => parseArtifact(artifact, bounds.start as number, bounds.end as number))
  if (artifacts.some((artifact) => artifact === null)) return null
  const typed = artifacts as EvidenceArtifact[]
  const paths = typed.map((artifact) => artifact.relative_path)
  const frameViews = typed.map((artifact) => `${artifact.frame_index}:${artifact.view}`)
  if (new Set(paths).size !== paths.length || new Set(frameViews).size !== frameViews.length) return null
  const sorted = [...typed].sort((left, right) =>
    left.frame_index - right.frame_index || (left.view < right.view ? -1 : left.view > right.view ? 1 : 0) ||
    (left.relative_path < right.relative_path ? -1 : left.relative_path > right.relative_path ? 1 : 0),
  )
  if (typed.some((artifact, index) => artifact !== sorted[index])) return null
  return value as unknown as EvidenceManifest
}

function canonicalJson(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(",")}]`
  if (isRecord(value)) {
    return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${canonicalJson(value[key])}`).join(",")}}`
  }
  const rendered = JSON.stringify(value)
  if (rendered === undefined) throw new Error("The manifest contains a value that cannot be hashed.")
  return rendered
}

async function sha256(payload: ArrayBuffer | Uint8Array | string) {
  const bytes = typeof payload === "string" ? new TextEncoder().encode(payload) : payload
  const digest = await crypto.subtle.digest("SHA-256", bytes)
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("")
}

function pngDimensions(bytes: Uint8Array): [number, number] | null {
  const signature = [137, 80, 78, 71, 13, 10, 26, 10]
  if (bytes.length < 33 || signature.some((byte, index) => bytes[index] !== byte)) return null
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength)
  if (view.getUint32(8) !== 13 || String.fromCharCode(...bytes.slice(12, 16)) !== "IHDR") return null
  const width = view.getUint32(16)
  const height = view.getUint32(20)
  return width > 0 && height > 0 ? [width, height] : null
}

function sameSet<T>(left: T[], right: T[]) {
  return left.length === right.length && left.every((value) => right.includes(value))
}

function verifyLineage(manifest: EvidenceManifest, report: ReliabilityReport, failure: ReportFailure) {
  const media = failure.media_evidence
  if (!media || media.status !== "available" || media.evidence_id === null) {
    throw new Error("The selected report event does not declare available image evidence.")
  }
  if (
    manifest.evidence_id !== media.evidence_id || manifest.source_id !== report.source.source_id ||
    manifest.run_id !== failure.run_id || manifest.event_id !== failure.event_id ||
    manifest.event_frame_index !== failure.frame_index ||
    manifest.evidence_frames.start !== failure.evidence_frames.start ||
    manifest.evidence_frames.end !== failure.evidence_frames.end
  ) throw new Error("The manifest does not match the selected report event and source lineage.")
  if (manifest.artifacts.length !== media.artifact_count) {
    throw new Error("The manifest artifact count does not match the verified report metadata.")
  }
  if (
    !sameSet([...new Set(manifest.artifacts.map((item) => item.frame_index))], media.frame_indices) ||
    !sameSet([...new Set(manifest.artifacts.map((item) => item.view))], media.views) ||
    !sameSet([...new Set(manifest.artifacts.map((item) => item.privacy))], media.privacy)
  ) throw new Error("The manifest frame, view, or privacy metadata does not match the report.")
  for (const artifact of manifest.artifacts) {
    if (artifact.width > report.source.width || artifact.height > report.source.height) {
      throw new Error(`The dimensions declared for ${artifact.relative_path} exceed the source.`)
    }
    if (artifact.view === "full_frame" &&
      (artifact.width !== report.source.width || artifact.height !== report.source.height)) {
      throw new Error(`Full-frame evidence ${artifact.relative_path} does not match the source dimensions.`)
    }
  }
}

export async function verifyEvidenceSelection(
  files: File[], report: ReliabilityReport, failure: ReportFailure,
): Promise<VerifiedEvidence> {
  if (files.length === 0) throw new Error("Select one manifest.json and every PNG it declares.")
  if (files.length > maxEvidenceArtifacts + 1) throw new Error("Too many evidence files were selected.")
  const manifests = files.filter((file) => file.name === "manifest.json")
  if (manifests.length !== 1) throw new Error("Select exactly one file named manifest.json.")
  const manifestFile = manifests[0]
  if (manifestFile.size > maxManifestBytes) throw new Error("The selected manifest.json is too large.")
  if (files.some((file) => file !== manifestFile && file.type !== "image/png" && !file.name.endsWith(".png"))) {
    throw new Error("Only manifest.json and its declared PNG files may be selected.")
  }
  let parsed: unknown
  try {
    parsed = JSON.parse(await manifestFile.text()) as unknown
  } catch {
    throw new Error("The selected manifest.json is not valid JSON.")
  }
  const manifest = parseManifest(parsed)
  if (!manifest) throw new Error("The evidence manifest structure is invalid or unsupported.")
  const identity = { ...parsed as Record<string, unknown> }
  delete identity.evidence_id
  if (await sha256(canonicalJson(identity)) !== manifest.evidence_id) {
    throw new Error("The evidence fingerprint does not match the manifest content.")
  }
  verifyLineage(manifest, report, failure)

  const imageFiles = files.filter((file) => file !== manifestFile)
  const byName = new Map<string, File>()
  for (const file of imageFiles) {
    if (byName.has(file.name)) throw new Error(`The selected PNG filename is duplicated: ${file.name}.`)
    byName.set(file.name, file)
  }
  if (imageFiles.length !== manifest.artifacts.length ||
    manifest.artifacts.some((artifact) => !byName.has(artifact.relative_path))) {
    throw new Error("The selected PNG filenames do not exactly match the manifest.")
  }

  const artifacts: VerifiedEvidenceArtifact[] = []
  for (const artifact of manifest.artifacts) {
    const file = byName.get(artifact.relative_path) as File
    if (file.size !== artifact.byte_length) throw new Error(`${artifact.relative_path} has the wrong byte length.`)
    const bytes = new Uint8Array(await file.arrayBuffer())
    if (await sha256(bytes) !== artifact.image_sha256) throw new Error(`${artifact.relative_path} failed SHA-256 verification.`)
    const dimensions = pngDimensions(bytes)
    if (!dimensions || dimensions[0] !== artifact.width || dimensions[1] !== artifact.height) {
      throw new Error(`${artifact.relative_path} is not a PNG with the declared dimensions.`)
    }
    artifacts.push({ artifact, file })
  }
  return { manifest, manifestFilename: manifestFile.name, artifacts }
}
