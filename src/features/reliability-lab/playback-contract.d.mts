export type PlaybackValidation = { valid: true } | { valid: false; error: string }
export function validateFailurePlayback(value: unknown): PlaybackValidation
export function verifyFailurePlayback(value: unknown): Promise<PlaybackValidation>
export function validatePlaybackReportLineage(playback: unknown, report: unknown): PlaybackValidation
export function serializePlayback(value: unknown): string
export function sha256Text(value: string): Promise<string>
