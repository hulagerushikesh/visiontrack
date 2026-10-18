import type { ReportLoadResult } from "./types"

export const maxReportBytes = 16 * 1024 * 1024

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
    try {
      return this.parseReport(JSON.parse(text) as unknown)
    } catch {
      return { kind: "missing", message: "The selected file is not valid JSON." }
    }
  }
}
