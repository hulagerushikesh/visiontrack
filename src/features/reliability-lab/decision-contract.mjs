export function canonicalJson(value) {
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(",")}]`
  if (typeof value === "object" && value !== null) {
    return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${canonicalJson(value[key])}`).join(",")}}`
  }
  const rendered = JSON.stringify(value)
  if (rendered === undefined) throw new Error("The selected record contains a value that cannot be hashed.")
  return rendered
}

export async function sha256Canonical(value) {
  const bytes = new TextEncoder().encode(canonicalJson(value))
  const digest = await globalThis.crypto.subtle.digest("SHA-256", bytes)
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("")
}

export async function createDecisionRecord(content) {
  return { decision_id: await sha256Canonical(content), ...content }
}

export function serializeDecision(decision) {
  return `${canonicalJson(decision)}\n`
}
