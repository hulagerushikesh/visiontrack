import { AssociationFileReader, type AssociationExplanation } from "./association"
import { InitiationFileReader, type InitiationTrace } from "./initiation"
import { ReportFileReader } from "./report-import"
import { parseReportModel, type ReliabilityReport } from "./types"

export interface AssociationDemo {
  report: ReliabilityReport
  trace: InitiationTrace
  explanation: AssociationExplanation
}
export type AssociationDemoTexts = { reportText: string; traceText: string; explanationText: string }
type Result = { kind: "ready"; demo: AssociationDemo } | { kind: "error"; message: string }
const file = (text: string) => ({ size: new TextEncoder().encode(text).length, text: async () => text })

/** A fixed, synthetic lesson: publish all three checked records, or none. */
export class AssociationDemoReader {
  private requestId = 0
  private reports = new ReportFileReader(parseReportModel)
  private traces = new InitiationFileReader()
  private explanations = new AssociationFileReader()

  cancel() {
    this.requestId += 1
    this.reports.cancel()
    this.traces.cancel()
    this.explanations.cancel()
  }

  async read(load: () => Promise<AssociationDemoTexts>): Promise<Result | null> {
    this.cancel()
    const id = this.requestId
    try {
      const texts = await load()
      if (id !== this.requestId) return null
      const report = await this.reports.read(file(texts.reportText))
      if (id !== this.requestId || report === null) return null
      if (report.kind !== "ready" || report.report.report_id !== "1019387f240d98a7fbd3b221c8d18c6eefdc3b06d01323d43398830f422595ed") throw new Error("The prepared lesson report could not be verified.")
      const trace = await this.traces.read(file(texts.traceText), report.report)
      if (id !== this.requestId || trace === null) return null
      if (trace.kind !== "ready" || trace.trace.trace_id !== "ff982927f10e05fb0893d9df2a0e187232c04125844869f8856cf5871e27f14e") throw new Error("The prepared lesson timeline could not be verified against its report.")
      const explanation = await this.explanations.read(file(texts.explanationText), report.report, trace.trace, { frame: 1, trackId: 1, detectionIndex: 7 })
      if (id !== this.requestId || explanation === null) return null
      if (explanation.kind !== "ready" || explanation.explanation.explanation_id !== "ddb2964f6d4291810546a1b7bdb9a1bcfdaef86dbf302ed63c1b11c8fbba614d") throw new Error("The prepared pair explanation could not be verified against its timeline.")
      return { kind: "ready", demo: { report: report.report, trace: trace.trace, explanation: explanation.explanation } }
    } catch (error) {
      return id === this.requestId ? { kind: "error", message: error instanceof Error ? error.message : "The prepared lesson could not be loaded." } : null
    }
  }
}
