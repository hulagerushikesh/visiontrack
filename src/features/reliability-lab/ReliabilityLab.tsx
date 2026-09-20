import { useEffect, useState, type ChangeEvent } from "react"
import { motion, useReducedMotion } from "motion/react"
import {
  AlertTriangle,
  ArrowUpRight,
  CheckCircle2,
  CircleOff,
  Database,
  FileCheck2,
  FileJson2,
  Fingerprint,
  FlaskConical,
  Info,
  LockKeyhole,
  RotateCcw,
  ScanSearch,
  Search,
  ShieldCheck,
  Upload,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { reliabilityReportFixture } from "./fixture"
import {
  parseReportModel,
  type FailureType,
  type ReliabilityReport,
  type ReportLoadResult,
} from "./types"

const failureLabels: Record<FailureType, string> = {
  id_switch: "ID switches",
  fragmentation: "Fragmentations",
  miss: "Misses",
  false_positive: "False positives",
}

const failureOrder = Object.keys(failureLabels) as FailureType[]

type ReportOrigin =
  | { kind: "sample" }
  | { kind: "file"; filename: string }

function number(value: number, signed = false) {
  const rendered = Number.isInteger(value) ? String(value) : value.toFixed(4).replace(/0+$/, "").replace(/\.$/, "")
  return signed && value > 0 ? `+${rendered}` : rendered
}

function short(value: string) {
  return `${value.slice(0, 8)}…${value.slice(-6)}`
}

function LoadingState() {
  return (
    <div className="mx-auto max-w-7xl px-5 pb-28 pt-36 lg:px-8" role="status" aria-live="polite">
      <span className="sr-only">Loading Reliability Lab report</span>
      <div className="h-6 w-40 animate-pulse rounded-full bg-indigo-100" />
      <div className="mt-8 h-16 max-w-3xl animate-pulse rounded-2xl bg-slate-200/70" />
      <div className="mt-12 grid gap-4 sm:grid-cols-3">
        {[0, 1, 2].map((item) => <div key={item} className="h-36 animate-pulse rounded-3xl bg-white shadow-sm" />)}
      </div>
    </div>
  )
}

function ImportControls({
  origin,
  reportId,
  onImport,
  onSample,
}: {
  origin: ReportOrigin
  reportId?: string
  onImport: (event: ChangeEvent<HTMLInputElement>) => void
  onSample: () => void
}) {
  return (
    <section className="rounded-3xl border border-indigo-100 bg-white/90 p-5 shadow-lg shadow-slate-200/50 backdrop-blur sm:p-6" aria-label="Report source">
      <div className="flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex min-w-0 items-start gap-3">
          <div className="grid size-10 shrink-0 place-items-center rounded-2xl bg-indigo-50 text-primary"><FileJson2 className="size-5" /></div>
          <div className="min-w-0">
            <p className="text-sm font-semibold">{origin.kind === "sample" ? "Illustrative sample report" : origin.filename}</p>
            <p className="mt-1 text-xs leading-5 text-muted-foreground">
              {reportId ? `Report ${short(reportId)} · ` : ""}Processed only in this browser tab. Nothing is uploaded.
            </p>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          {origin.kind === "file" && <Button type="button" variant="outline" onClick={onSample}><RotateCcw className="size-4" />Return to sample</Button>}
          <label className="inline-flex h-9 cursor-pointer items-center justify-center gap-2 whitespace-nowrap rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground shadow-xs transition hover:bg-primary/90 focus-within:outline-none focus-within:ring-2 focus-within:ring-ring focus-within:ring-offset-2">
            <Upload className="size-4" />Import report.json
            <input className="sr-only" type="file" accept="application/json,.json" onChange={onImport} />
          </label>
        </div>
      </div>
    </section>
  )
}

function ReportError({ state }: { state: Exclude<ReportLoadResult, { kind: "ready" }> }) {
  const unsupported = state.kind === "unsupported"
  return (
    <div className="mx-auto grid min-h-[78vh] max-w-3xl place-items-center px-5 pb-24 pt-32 text-center">
      <div className="rounded-[2rem] border border-amber-200 bg-white p-8 shadow-xl shadow-slate-200/60 sm:p-12" role="alert">
        {unsupported ? <CircleOff className="mx-auto size-10 text-amber-500" /> : <AlertTriangle className="mx-auto size-10 text-amber-500" />}
        <p className="mt-6 font-mono text-xs font-semibold uppercase tracking-[.18em] text-amber-700">Report unavailable</p>
        <h1 className="mt-3 text-3xl font-semibold tracking-tight">{unsupported ? "Unsupported report version" : "Verified evidence is missing"}</h1>
        <p className="mt-4 leading-7 text-muted-foreground">
          {unsupported
            ? `This screen reads schema version 1. Received ${String(state.schemaVersion)}.`
            : state.message}
        </p>
        <Button asChild variant="outline" className="mt-7"><a href="/docs/">Read the Lab contract <ArrowUpRight className="size-4" /></a></Button>
      </div>
    </div>
  )
}

function MetricTable({ report }: { report: ReliabilityReport }) {
  const metrics = Object.keys(report.variants[0].metrics)
  return (
    <div className="overflow-x-auto rounded-3xl border border-border bg-white shadow-sm">
      <table className="w-full min-w-[680px] border-collapse text-left">
        <caption className="px-6 py-5 text-left text-sm text-muted-foreground">Value and delta relative to {report.experiment.baseline}</caption>
        <thead className="border-y border-border bg-slate-50/80 text-xs uppercase tracking-[.12em] text-muted-foreground">
          <tr><th scope="col" className="px-6 py-4">Metric</th>{report.variants.map((variant) => <th scope="col" className="px-6 py-4" key={variant.name}>{variant.name}{variant.baseline && <span className="ml-2 rounded-full bg-indigo-100 px-2 py-1 text-[9px] text-indigo-700">baseline</span>}</th>)}</tr>
        </thead>
        <tbody>{metrics.map((metric) => <tr className="border-b border-border last:border-0" key={metric}><th scope="row" className="px-6 py-4 font-mono text-sm">{metric}</th>{report.variants.map((variant) => <td className="px-6 py-4" key={variant.name}><span className="font-semibold">{number(variant.metrics[metric])}</span><span className="ml-2 text-xs text-muted-foreground">{number(variant.metric_deltas[metric], true)} Δ</span></td>)}</tr>)}</tbody>
      </table>
    </div>
  )
}

function FailureExplorer({ report }: { report: ReliabilityReport }) {
  const [variant, setVariant] = useState("all")
  const [failureType, setFailureType] = useState<FailureType | "all">("all")
  const [frame, setFrame] = useState("")
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null)
  const frameNumber = frame === "" ? null : Number(frame)
  const filteredFailures = report.failures.filter((failure) =>
    (variant === "all" || failure.variant === variant) &&
    (failureType === "all" || failure.event_type === failureType) &&
    (frameNumber === null || failure.frame_index === frameNumber),
  )
  const selectedEvent = report.failures.find((failure) => failure.event_id === selectedEventId) ?? null
  const filtersActive = variant !== "all" || failureType !== "all" || frame !== ""
  const clearSelection = () => setSelectedEventId(null)
  const resetFilters = () => {
    setVariant("all")
    setFailureType("all")
    setFrame("")
    clearSelection()
  }

  return (
    <section className="mt-20" aria-labelledby="events-title">
      <div className="mb-8">
        <p className="font-mono text-xs font-semibold uppercase tracking-[.16em] text-primary">Frame-level evidence</p>
        <h2 id="events-title" className="mt-3 text-4xl font-semibold tracking-[-.04em]">Inspect the failure set.</h2>
        <p className="mt-4 max-w-3xl leading-7 text-muted-foreground">Filter the events already present in this verified report. These controls never recalculate metrics or change the source artifacts.</p>
      </div>

      {report.failures.length === 0 ? (
        <div className="rounded-3xl border border-emerald-200 bg-emerald-50 p-8 text-center">
          <CheckCircle2 className="mx-auto size-8 text-emerald-600" />
          <h3 className="mt-4 text-xl font-semibold">No measured failures</h3>
          <p className="mt-2 text-sm text-emerald-800">The verified artifact contains an empty failure set.</p>
        </div>
      ) : (
        <div className="space-y-5">
          <div className="rounded-3xl border border-indigo-100 bg-white p-5 shadow-sm sm:p-6">
            <div className="grid gap-4 md:grid-cols-[1fr_1fr_1fr_auto] md:items-end">
              <label className="grid gap-2 text-sm font-medium" htmlFor="failure-variant">
                Variant
                <select id="failure-variant" value={variant} onChange={(event) => { setVariant(event.target.value); clearSelection() }} className="h-10 rounded-xl border border-input bg-white px-3 text-sm outline-none focus:ring-2 focus:ring-ring">
                  <option value="all">All variants</option>
                  {report.variants.map((item) => <option value={item.name} key={item.name}>{item.name}</option>)}
                </select>
              </label>
              <label className="grid gap-2 text-sm font-medium" htmlFor="failure-type">
                Failure type
                <select id="failure-type" value={failureType} onChange={(event) => { setFailureType(event.target.value as FailureType | "all"); clearSelection() }} className="h-10 rounded-xl border border-input bg-white px-3 text-sm outline-none focus:ring-2 focus:ring-ring">
                  <option value="all">All failure types</option>
                  {failureOrder.map((type) => <option value={type} key={type}>{failureLabels[type]}</option>)}
                </select>
              </label>
              <label className="grid gap-2 text-sm font-medium" htmlFor="failure-frame">
                Exact frame
                <span className="relative"><Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" /><input id="failure-frame" type="number" min={report.experiment.frame_range.start} max={report.experiment.frame_range.end - 1} inputMode="numeric" value={frame} onChange={(event) => { setFrame(event.target.value); clearSelection() }} placeholder={`${report.experiment.frame_range.start}–${report.experiment.frame_range.end - 1}`} className="h-10 w-full rounded-xl border border-input bg-white pl-9 pr-3 text-sm outline-none placeholder:text-muted-foreground focus:ring-2 focus:ring-ring" /></span>
              </label>
              <Button type="button" variant="outline" onClick={resetFilters} disabled={!filtersActive}><RotateCcw className="size-4" />Reset</Button>
            </div>
            <p className="mt-5 text-sm text-muted-foreground" role="status" aria-live="polite">
              Showing <strong className="text-foreground">{filteredFailures.length}</strong> matching displayed {filteredFailures.length === 1 ? "event" : "events"} · {report.failure_event_displayed} displayed · {report.failure_event_total} verified total
            </p>
          </div>

          {filteredFailures.length === 0 ? (
            <div className="rounded-3xl border border-dashed border-slate-300 bg-slate-50/70 p-8 text-center">
              <Search className="mx-auto size-8 text-slate-400" />
              <h3 className="mt-4 text-xl font-semibold">No events match these filters</h3>
              <p className="mt-2 text-sm text-muted-foreground">The report is unchanged. Reset the filters to inspect all displayed evidence.</p>
              <Button type="button" variant="outline" className="mt-5" onClick={resetFilters}>Reset filters</Button>
            </div>
          ) : (
            <div className="overflow-x-auto rounded-3xl border border-border bg-white">
              <table className="w-full min-w-[860px] border-collapse text-left">
                <caption className="px-6 py-5 text-left text-sm text-muted-foreground">Read-only failure events from the active report</caption>
                <thead className="border-y border-border bg-slate-50/80 text-xs uppercase tracking-[.12em] text-muted-foreground"><tr><th scope="col" className="px-6 py-4">Type</th><th scope="col" className="px-6 py-4">Variant</th><th scope="col" className="px-6 py-4">Frame</th><th scope="col" className="px-6 py-4">Tracks</th><th scope="col" className="px-6 py-4">Ground truth</th><th scope="col" className="px-6 py-4">Evidence range</th><th scope="col" className="px-6 py-4"><span className="sr-only">Inspect</span></th></tr></thead>
                <tbody>{filteredFailures.map((failure) => <tr className="border-b border-border last:border-0" key={failure.event_id}><td className="px-6 py-4"><span className="rounded-full bg-indigo-50 px-2.5 py-1 text-xs font-semibold capitalize text-indigo-700">{failure.event_type.replace("_", " ")}</span></td><td className="px-6 py-4 text-sm">{failure.variant}</td><td className="px-6 py-4 font-mono text-sm">{failure.frame_index}</td><td className="px-6 py-4 text-sm">{failure.track_ids.join(", ") || "—"}</td><td className="px-6 py-4 text-sm">{failure.ground_truth_ids.join(", ") || "—"}</td><td className="px-6 py-4 text-sm">{failure.evidence_frames.start}–{failure.evidence_frames.end - 1}</td><td className="px-6 py-4 text-right"><Button type="button" size="sm" variant={selectedEventId === failure.event_id ? "default" : "outline"} aria-pressed={selectedEventId === failure.event_id} aria-controls="failure-event-detail" onClick={() => setSelectedEventId(failure.event_id)}>Inspect</Button></td></tr>)}</tbody>
              </table>
            </div>
          )}

          {selectedEvent && (
            <aside id="failure-event-detail" className="rounded-[1.75rem] border border-indigo-100 bg-indigo-50/70 p-6 sm:p-8" aria-labelledby="failure-detail-title">
              <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                <div><p className="font-mono text-xs font-semibold uppercase tracking-[.16em] text-primary">Selected evidence</p><h3 id="failure-detail-title" className="mt-2 text-2xl font-semibold tracking-tight">{failureLabels[selectedEvent.event_type]} at frame {selectedEvent.frame_index}</h3></div>
                <Button type="button" variant="outline" onClick={clearSelection}>Close details</Button>
              </div>
              <dl className="mt-7 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
                <div><dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Variant</dt><dd className="mt-2 text-sm font-semibold">{selectedEvent.variant}</dd></div>
                <div><dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Evidence range</dt><dd className="mt-2 font-mono text-sm">{selectedEvent.evidence_frames.start}–{selectedEvent.evidence_frames.end - 1}</dd></div>
                <div><dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Event fingerprint</dt><dd className="mt-2 font-mono text-sm">{short(selectedEvent.event_id)}</dd></div>
                <div><dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Run fingerprint</dt><dd className="mt-2 font-mono text-sm">{short(selectedEvent.run_id)}</dd></div>
              </dl>
              <div className="mt-6 rounded-2xl border border-indigo-100 bg-white/80 p-5"><p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Recorded context</p><pre className="mt-3 overflow-x-auto whitespace-pre-wrap break-words font-mono text-xs leading-6 text-slate-700">{JSON.stringify(selectedEvent.context, null, 2)}</pre></div>
              <p className="mt-5 text-xs leading-5 text-muted-foreground">Track IDs shown here are local to this run. This panel displays report evidence and does not infer a persistent person identity.</p>
            </aside>
          )}
        </div>
      )}
    </section>
  )
}

function LabReport({ report, origin }: { report: ReliabilityReport; origin: ReportOrigin }) {
  const reduce = useReducedMotion()
  const frameCount = report.experiment.frame_range.end - report.experiment.frame_range.start
  return (
    <div className="relative pb-28 pt-14 lg:pt-16">
      <div className="orb -left-56 -top-32 bg-indigo-300/30" /><div className="orb -right-64 top-72 bg-emerald-200/30" />
      <div className="relative mx-auto max-w-7xl px-5 lg:px-8">
        <motion.section initial={reduce ? false : { opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: .5 }} aria-labelledby="lab-title">
          <div className="flex flex-wrap items-center gap-3"><span className="inline-flex items-center gap-2 rounded-full border border-indigo-100 bg-indigo-50 px-3 py-1.5 font-mono text-[10px] font-semibold uppercase tracking-[.16em] text-primary"><FlaskConical className="size-3" />Reliability Lab</span><span className={origin.kind === "sample" ? "rounded-full bg-amber-50 px-3 py-1.5 text-xs font-semibold text-amber-700" : "rounded-full bg-emerald-50 px-3 py-1.5 text-xs font-semibold text-emerald-700"}>{origin.kind === "sample" ? "Demonstration fixture · illustrative data" : "Private local import · verified schema"}</span></div>
          <div className="mt-7 grid gap-8 lg:grid-cols-[1.1fr_.9fr] lg:items-end"><div><h1 id="lab-title" className="max-w-4xl text-balance text-5xl font-semibold leading-[.98] tracking-[-.055em] sm:text-7xl">Evidence before <span className="gradient-text">confidence.</span></h1><p className="mt-6 max-w-2xl text-lg leading-8 text-muted-foreground">Compare tracker configurations on identical detections, inspect measured failures, and trace every claim to immutable evidence.</p></div><div className="rounded-3xl border border-white bg-white/85 p-6 shadow-xl shadow-slate-200/60 backdrop-blur"><div className="flex items-start gap-4"><div className="grid size-11 shrink-0 place-items-center rounded-2xl bg-emerald-50 text-emerald-600"><ShieldCheck className="size-5" /></div><div><p className="font-semibold">Verified, read-only report</p><p className="mt-1 text-sm leading-6 text-muted-foreground">The Python pipeline remains the source of truth. This screen does not edit results or choose a winner.</p></div></div></div></div>
        </motion.section>

        <section className="mt-14 grid gap-4 sm:grid-cols-2 xl:grid-cols-4" aria-label="Experiment overview">
          {[
            ["Source", report.source.name, Database],
            ["Frame range", `${report.experiment.frame_range.start}–${report.experiment.frame_range.end - 1} · ${frameCount} frames`, ScanSearch],
            ["Evidence", `${report.variants.length} variants · ${report.failure_event_total} failures`, FileCheck2],
            ["Decision", "No variant selected", LockKeyhole],
          ].map(([label, value, Icon]) => <div className="rounded-3xl border border-white bg-white/90 p-6 shadow-[0_18px_55px_-38px_rgba(30,41,59,.45)] ring-1 ring-slate-200/70" key={String(label)}><Icon className="size-5 text-primary" /><p className="mt-8 font-mono text-[10px] font-semibold uppercase tracking-[.16em] text-muted-foreground">{String(label)}</p><p className="mt-2 font-semibold">{String(value)}</p></div>)}
        </section>

        <section className="mt-20" aria-labelledby="metrics-title"><div className="mb-8 max-w-3xl"><p className="font-mono text-xs font-semibold uppercase tracking-[.16em] text-primary">Paired measurement</p><h2 id="metrics-title" className="mt-3 text-4xl font-semibold tracking-[-.04em]">Same evidence. Controlled change.</h2><p className="mt-4 leading-7 text-muted-foreground">Every variant consumed the same immutable detection stream and frame range. Deltas are descriptive; acceptance remains a human decision.</p></div><MetricTable report={report} /></section>

        <section className="mt-20" aria-labelledby="failures-title"><div className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between"><div><p className="font-mono text-xs font-semibold uppercase tracking-[.16em] text-primary">Failure taxonomy</p><h2 id="failures-title" className="mt-3 text-4xl font-semibold tracking-[-.04em]">Where tracking breaks.</h2></div><p className="max-w-md text-sm leading-6 text-muted-foreground">Counts use the same correspondence as the published metrics—not a second UI-only calculation.</p></div><div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">{failureOrder.map((failure) => <article className="rounded-3xl border border-border bg-white p-6" key={failure}><p className="text-sm font-medium text-muted-foreground">{failureLabels[failure]}</p><div className="mt-5 space-y-3">{report.variants.map((variant) => <div className="flex items-center justify-between" key={variant.name}><span className="text-sm">{variant.name}</span><strong className="text-2xl">{variant.failure_counts[failure]}</strong></div>)}</div></article>)}</div></section>

        <FailureExplorer key={report.report_id} report={report} />

        <section className="mt-20 grid gap-5 lg:grid-cols-[1.1fr_.9fr]" aria-label="Evidence provenance and limitations"><div className="rounded-[1.75rem] bg-slate-950 p-7 text-white sm:p-9"><Fingerprint className="size-6 text-cyan-300" /><h2 className="mt-7 text-3xl font-semibold tracking-tight">Traceable provenance</h2><dl className="mt-7 grid gap-5 text-sm"><div><dt className="text-white/45">Report</dt><dd className="mt-1 break-all font-mono text-white/80">{short(report.report_id)}</dd></div><div><dt className="text-white/45">Experiment</dt><dd className="mt-1 break-all font-mono text-white/80">{short(report.experiment.experiment_id)}</dd></div><div><dt className="text-white/45">Detections</dt><dd className="mt-1 break-all font-mono text-white/80">{short(report.source.detection_sha256)}</dd></div><div><dt className="text-white/45">Ground truth</dt><dd className="mt-1 break-all font-mono text-white/80">{short(report.source.ground_truth_sha256)}</dd></div></dl></div><div className="rounded-[1.75rem] border border-indigo-100 bg-indigo-50/70 p-7 sm:p-9"><Info className="size-6 text-indigo-600" /><h2 className="mt-7 text-3xl font-semibold tracking-tight">Boundaries stay visible</h2><ul className="mt-6 space-y-4">{report.limitations.map((limitation) => <li className="flex gap-3 text-sm leading-6 text-slate-700" key={limitation}><CheckCircle2 className="mt-1 size-4 shrink-0 text-indigo-500" />{limitation}</li>)}</ul><Button disabled className="mt-8 w-full">Variant selection is not enabled</Button><p className="mt-3 text-center text-xs text-muted-foreground">A future step will record an explicit, auditable human decision.</p></div></section>
      </div>
    </div>
  )
}

export default function ReliabilityLab() {
  const [state, setState] = useState<ReportLoadResult | { kind: "loading" }>({ kind: "loading" })
  const [origin, setOrigin] = useState<ReportOrigin>({ kind: "sample" })
  useEffect(() => {
    let active = true
    queueMicrotask(() => { if (active) setState(parseReportModel(reliabilityReportFixture)) })
    return () => { active = false }
  }, [])
  if (state.kind === "loading") return <LoadingState />

  const loadSample = () => {
    setOrigin({ kind: "sample" })
    setState(parseReportModel(reliabilityReportFixture))
  }
  const importReport = async (event: ChangeEvent<HTMLInputElement>) => {
    const input = event.currentTarget
    const file = input.files?.[0]
    if (!file) return
    setOrigin({ kind: "file", filename: file.name })
    setState({ kind: "loading" })
    try {
      const report = JSON.parse(await file.text()) as unknown
      setState(parseReportModel(report))
    } catch {
      setState({ kind: "missing", message: "The selected file is not valid JSON." })
    } finally {
      input.value = ""
    }
  }

  return (
    <div>
      <div className="relative z-10 mx-auto max-w-7xl px-5 pt-28 lg:px-8">
        <ImportControls origin={origin} reportId={state.kind === "ready" ? state.report.report_id : undefined} onImport={importReport} onSample={loadSample} />
      </div>
      {state.kind === "ready" ? <LabReport report={state.report} origin={origin} /> : <ReportError state={state} />}
    </div>
  )
}
