import type { PlaybackLane } from "./playback"

export interface VerifiedPlaybackLaneMedia {
  runId: string
  files: Map<string, File>
}

export function verifyPlaybackLaneFiles(
  files: File[],
  lane: PlaybackLane,
): Promise<VerifiedPlaybackLaneMedia>
