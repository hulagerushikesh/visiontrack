export function nextPlaybackFrame(frameRange, frameIndex) {
  return Math.min(Math.max(frameIndex + 1, frameRange.start), frameRange.end - 1)
}

export function playbackStepDelay(playback, frameIndex, rate) {
  if (![0.5, 1, 2].includes(rate)) throw new Error("The playback rate is unsupported.")
  const position = frameIndex - playback.frame_range.start
  const frames = playback.lanes[0].frames
  const currentOffset = frames[position]?.offset_ms
  const nextOffset = frames[position + 1]?.offset_ms
  const sourceDelay = currentOffset === null || currentOffset === undefined ||
    nextOffset === null || nextOffset === undefined ? 250 : nextOffset - currentOffset
  return Math.max(16, Math.min(2000, sourceDelay / rate))
}
