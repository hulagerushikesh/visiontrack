import type { ReportLoadResult } from "./types"

export const maxReportBytes = 16 * 1024 * 1024

/**
 * Python hashes its sorted, compact JSON before adding its fingerprint field. Verify the
 * original text rather than JSON.stringify(JSON.parse(text)): JavaScript turns
 * Python's 1.0 into 1 and would reject an otherwise valid report.
 */
export async function verifyContentFingerprint(text: string, contentId: string, field: "report_id" | "trace_id"): Promise<boolean> {
  const document = text.endsWith("\n") ? text.slice(0, -1) : text
  if (!document.startsWith("{") || !document.endsWith("}")) return false
  const key = `,"${field}":`
  const member = `${key}"${contentId}"`
  let depth = 0
  let inString = false
  let escaped = false
  let position = -1
  for (let index = 0; index < document.length; index += 1) {
    const character = document[index]
    if (inString) {
      if (escaped) escaped = false
      else if (character === "\\") escaped = true
      else if (character === '"') inString = false
      continue
    }
    if (character === '"') {
      inString = true
      continue
    }
    if (character === "{" || character === "[") depth += 1
    else if (character === "}" || character === "]") depth -= 1
    else if (character === "," && depth === 1 && document.startsWith(key, index)) {
      if (position !== -1 || !document.startsWith(member, index)) return false
      position = index
    }
  }
  if (position === -1 || depth !== 0 || inString) return false
  const content = document.slice(0, position) + document.slice(position + member.length)
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(content))
  const actual = Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("")
  return actual === contentId
}

export const verifyReportFingerprint = (text: string, reportId: string) =>
  verifyContentFingerprint(text, reportId, "report_id")

/** Read the latest explicit file selection; canceled reads never publish results. */
export class ReportFileReader {
  private requestId = 0

  constructor(private readonly parseReport: (value: unknown) => ReportLoadResult) {}

  cancel() {
    this.requestId += 1
  }

  async read(file: Pick<File, "size" | "text">): Promise<ReportLoadResult | null> {
    const requestId = ++this.requestId
    if (file.size === 0) return { kind: "missing", message: "The selected report is empty." }
    if (file.size > maxReportBytes) {
      return { kind: "missing", message: "The selected report exceeds the 16 MiB browser import limit." }
    }
    let text: string
    try {
      text = await file.text()
    } catch {
      return this.requestId === requestId
        ? { kind: "missing", message: "The selected report could not be read. Select the file again." }
        : null
    }
    if (this.requestId !== requestId) return null
    let parsed: unknown
    try {
      parsed = JSON.parse(text) as unknown
    } catch {
      return { kind: "missing", message: "The selected file is not valid JSON." }
    }
    let result: ReportLoadResult
    try {
      result = this.parseReport(parsed)
    } catch {
      return { kind: "missing", message: "The selected report could not be validated." }
    }
    if (result.kind !== "ready") return result
    try {
      const verified = await verifyReportFingerprint(text, result.report.report_id)
      if (this.requestId !== requestId) return null
      return verified ? result : {
        kind: "missing",
        message: "The report fingerprint does not match its contents. Regenerate report.json from the original bundle.",
      }
    } catch {
      return this.requestId === requestId
        ? { kind: "missing", message: "The report fingerprint could not be checked in this browser." }
        : null
    }
  }
}
