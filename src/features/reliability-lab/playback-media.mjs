const maxPlaybackImages = 301
const maxImageBytes = 16 * 1024 * 1024
const maxImagePixels = 4_194_304

const basename = (path) => path.slice(path.lastIndexOf("/") + 1)

async function sha256(bytes) {
  const digest = await globalThis.crypto.subtle.digest("SHA-256", bytes)
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("")
}

function pngDimensions(bytes) {
  const signature = [137, 80, 78, 71, 13, 10, 26, 10]
  if (bytes.length < 33 || signature.some((byte, index) => bytes[index] !== byte)) return null
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength)
  if (view.getUint32(8) !== 13 || String.fromCharCode(...bytes.slice(12, 16)) !== "IHDR") return null
  const width = view.getUint32(16)
  const height = view.getUint32(20)
  if (width === 0 || height === 0 || width * height > maxImagePixels) return null
  return [width, height]
}

export async function verifyPlaybackLaneFiles(files, lane) {
  const expected = lane.frames.filter((frame) => frame.status === "available")
  if (expected.length === 0) throw new Error("This playback lane declares no available PNG files.")
  if (expected.length > maxPlaybackImages || files.length > maxPlaybackImages) {
    throw new Error("Too many playback PNG files were selected.")
  }
  const byName = new Map()
  for (const frame of expected) {
    const name = basename(frame.relative_path)
    if (!name.endsWith(".png") || byName.has(name)) {
      throw new Error("The playback lane does not define unique safe PNG filenames.")
    }
    byName.set(name, frame)
  }
  const selected = new Map()
  for (const file of files) {
    if (!file.name.endsWith(".png") || (file.type && file.type !== "image/png")) {
      throw new Error("Only the playback lane's declared PNG files may be selected.")
    }
    if (selected.has(file.name)) throw new Error(`The selected PNG filename is duplicated: ${file.name}.`)
    selected.set(file.name, file)
  }
  if (selected.size !== byName.size || [...byName.keys()].some((name) => !selected.has(name))) {
    throw new Error("The selected PNG filenames do not exactly match this playback lane.")
  }

  const verified = new Map()
  for (const [name, frame] of byName) {
    const file = selected.get(name)
    if (file.size === 0 || file.size > maxImageBytes) throw new Error(`${name} is empty or too large.`)
    const bytes = new Uint8Array(await file.arrayBuffer())
    if (await sha256(bytes) !== frame.image_sha256) throw new Error(`${name} failed SHA-256 verification.`)
    if (!pngDimensions(bytes)) throw new Error(`${name} is not a bounded PNG image.`)
    verified.set(frame.relative_path, file)
  }
  return { runId: lane.run_id, files: verified }
}
