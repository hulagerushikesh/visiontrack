import { verifyFailurePlayback } from "./playback-contract.mjs"

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

export async function parseFailurePlayback(value: unknown): Promise<PlaybackLoadResult> {
  const result = await verifyFailurePlayback(value)
  if (!result.valid) return { kind: "invalid", message: result.error }
  return { kind: "ready", playback: value as FailurePlayback }
}
