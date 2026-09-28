import type { FailurePlayback } from "./playback"

export function nextPlaybackFrame(
  frameRange: { start: number; end: number },
  frameIndex: number,
): number
export function playbackStepDelay(
  playback: FailurePlayback,
  frameIndex: number,
  rate: number,
): number
