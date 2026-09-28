import type { ReliabilityReport } from "./types"
import {
  validatePlaybackReportLineage,
  verifyFailurePlayback,
} from "./playback-contract.mjs"

export type PlaybackPrivacy = "source_pixels" | "redacted" | "synthetic"

export interface PlaybackFrame {
  frame_index: number
  offset_ms: number | null
  status: "available" | "missing"
  relative_path: string | null
  image_sha256: string | null
  privacy: PlaybackPrivacy | null
  schema_version: 1
}

export interface PlaybackLane {
  variant: string
  run_id: string
  frames: PlaybackFrame[]
  schema_version: 1
}

export interface FailurePlayback {
  playback_id: string
  experiment_id: string
  source_id: string
  comparison_id: string
  report_id: string
  anchor_event_id: string
  event_frame_index: number
  frame_range: { start: number; end: number }
  baseline: string
  variant: string
  lanes: [PlaybackLane, PlaybackLane]
  schema_version: 1
}

export type PlaybackLoadResult =
  | { kind: "ready"; playback: FailurePlayback }
  | { kind: "invalid"; message: string }

export interface VerifiedPlayback {
  playback: FailurePlayback
  filename: string
}

const maxPlaybackBytes = 2 * 1024 * 1024

export async function parseFailurePlayback(value: unknown): Promise<PlaybackLoadResult> {
  const result = await verifyFailurePlayback(value)
  if (!result.valid) return { kind: "invalid", message: result.error }
  return { kind: "ready", playback: value as FailurePlayback }
}

export async function verifyPlaybackFile(
  file: File,
  report: ReliabilityReport,
): Promise<VerifiedPlayback> {
  if (file.name !== "playback.json") throw new Error("Select exactly one file named playback.json.")
  if (file.size === 0 || file.size > maxPlaybackBytes) {
    throw new Error("The selected playback.json is empty or too large.")
  }
  let parsed: unknown
  try {
    parsed = JSON.parse(await file.text()) as unknown
  } catch {
    throw new Error("The selected playback.json is not valid JSON.")
  }
  const result = await parseFailurePlayback(parsed)
  if (result.kind === "invalid") throw new Error(result.message)
  const lineage = validatePlaybackReportLineage(result.playback, report)
  if (!lineage.valid) throw new Error(lineage.error)
  return { playback: result.playback, filename: file.name }
}
