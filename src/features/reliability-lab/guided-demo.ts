import { InitiationFileReader, type InitiationTrace } from "./initiation"
import { ReportFileReader } from "./report-import"
import { parseReportModel, type ReliabilityReport } from "./types"

export interface GuidedDemo {
  report: ReliabilityReport
  trace: InitiationTrace
}
type DemoTexts = { reportText: string; traceText: string }
type DemoResult = { kind: "ready"; demo: GuidedDemo } | { kind: "error"; message: string }

const textFile = (text: string) => ({
  size: new TextEncoder().encode(text).length,
  text: async () => text,
})

/** Publish a complete checked pair, or nothing. Selection changes cancel all stages. */
export class GuidedDemoReader {
  private requestId = 0
  private reportReader = new ReportFileReader(parseReportModel)
  private traceReader = new InitiationFileReader()

  cancel() {
    this.requestId += 1
    this.reportReader.cancel()
    this.traceReader.cancel()
  }

  async read(load: () => Promise<DemoTexts>): Promise<DemoResult | null> {
    this.cancel()
    const requestId = this.requestId
    try {
      const { reportText, traceText } = await load()
      if (requestId !== this.requestId) return null
      const report = await this.reportReader.read(textFile(reportText))
      if (requestId !== this.requestId || report === null) return null
      if (report.kind !== "ready") throw new Error("The bundled demo report could not be verified.")
      // Teaching text describes this fixed public 0.4.0 example, not arbitrary input.
      if (report.report.report_id !== "512a7a79db0535b4c26321def12cb8be514581d7a9f48c73206c5ebb147f2d17") {
        throw new Error("The bundled report does not match the guided example.")
      }
      const trace = await this.traceReader.read(textFile(traceText), report.report)
      if (requestId !== this.requestId || trace === null) return null
      if (trace.kind !== "ready") throw new Error("The bundled demo trace could not be verified against its report.")
      if (trace.trace.trace_id !== "630449be5bc03e231d4bd666ba662c68ba2235dd138854dc619d482e63636a0a") {
        throw new Error("The bundled trace does not match the guided example.")
      }
      return { kind: "ready", demo: { report: report.report, trace: trace.trace } }
    } catch (error) {
      return requestId === this.requestId
        ? { kind: "error", message: error instanceof Error ? error.message : "The guided demo could not be loaded." }
        : null
    }
  }
}
