import { useEffect, useState } from "react"
import { motion, useReducedMotion } from "motion/react"
import {
  AlertTriangle,
  ArrowUpRight,
  CheckCircle2,
  CircleOff,
  Database,
  FileCheck2,
  Fingerprint,
  FlaskConical,
  Info,
  LockKeyhole,
  ScanSearch,
  ShieldCheck,
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

function LabReport({ report }: { report: ReliabilityReport }) {
  const reduce = useReducedMotion()
  const frameCount = report.experiment.frame_range.end - report.experiment.frame_range.start
  return (
    <div className="relative pb-28 pt-32 lg:pt-40">
      <div className="orb -left-56 -top-32 bg-indigo-300/30" /><div className="orb -right-64 top-72 bg-emerald-200/30" />
      <div className="relative mx-auto max-w-7xl px-5 lg:px-8">
        <motion.section initial={reduce ? false : { opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: .5 }} aria-labelledby="lab-title">
          <div className="flex flex-wrap items-center gap-3"><span className="inline-flex items-center gap-2 rounded-full border border-indigo-100 bg-indigo-50 px-3 py-1.5 font-mono text-[10px] font-semibold uppercase tracking-[.16em] text-primary"><FlaskConical className="size-3" />Reliability Lab</span><span className="rounded-full bg-amber-50 px-3 py-1.5 text-xs font-semibold text-amber-700">Demonstration fixture · illustrative data</span></div>
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

        <section className="mt-20" aria-labelledby="events-title"><div className="mb-8"><p className="font-mono text-xs font-semibold uppercase tracking-[.16em] text-primary">Frame-level evidence</p><h2 id="events-title" className="mt-3 text-4xl font-semibold tracking-[-.04em]">Inspectable events.</h2></div>{report.failures.length === 0 ? <div className="rounded-3xl border border-emerald-200 bg-emerald-50 p-8 text-center"><CheckCircle2 className="mx-auto size-8 text-emerald-600" /><h3 className="mt-4 text-xl font-semibold">No measured failures</h3><p className="mt-2 text-sm text-emerald-800">The verified artifact contains an empty failure set.</p></div> : <div className="overflow-x-auto rounded-3xl border border-border bg-white"><table className="w-full min-w-[760px] border-collapse text-left"><caption className="px-6 py-5 text-left text-sm text-muted-foreground">Showing {report.failure_event_displayed} of {report.failure_event_total} events from the fixture</caption><thead className="border-y border-border bg-slate-50/80 text-xs uppercase tracking-[.12em] text-muted-foreground"><tr><th scope="col" className="px-6 py-4">Type</th><th scope="col" className="px-6 py-4">Variant</th><th scope="col" className="px-6 py-4">Frame</th><th scope="col" className="px-6 py-4">Tracks</th><th scope="col" className="px-6 py-4">Ground truth</th><th scope="col" className="px-6 py-4">Evidence range</th></tr></thead><tbody>{report.failures.map((failure) => <tr className="border-b border-border last:border-0" key={failure.event_id}><td className="px-6 py-4"><span className="rounded-full bg-indigo-50 px-2.5 py-1 text-xs font-semibold capitalize text-indigo-700">{failure.event_type.replace("_", " ")}</span></td><td className="px-6 py-4 text-sm">{failure.variant}</td><td className="px-6 py-4 font-mono text-sm">{failure.frame_index}</td><td className="px-6 py-4 text-sm">{failure.track_ids.join(", ") || "—"}</td><td className="px-6 py-4 text-sm">{failure.ground_truth_ids.join(", ") || "—"}</td><td className="px-6 py-4 text-sm">{failure.evidence_frames.start}–{failure.evidence_frames.end - 1}</td></tr>)}</tbody></table></div>}</section>

        <section className="mt-20 grid gap-5 lg:grid-cols-[1.1fr_.9fr]" aria-label="Evidence provenance and limitations"><div className="rounded-[1.75rem] bg-slate-950 p-7 text-white sm:p-9"><Fingerprint className="size-6 text-cyan-300" /><h2 className="mt-7 text-3xl font-semibold tracking-tight">Traceable provenance</h2><dl className="mt-7 grid gap-5 text-sm"><div><dt className="text-white/45">Report</dt><dd className="mt-1 break-all font-mono text-white/80">{short(report.report_id)}</dd></div><div><dt className="text-white/45">Experiment</dt><dd className="mt-1 break-all font-mono text-white/80">{short(report.experiment.experiment_id)}</dd></div><div><dt className="text-white/45">Detections</dt><dd className="mt-1 break-all font-mono text-white/80">{short(report.source.detection_sha256)}</dd></div><div><dt className="text-white/45">Ground truth</dt><dd className="mt-1 break-all font-mono text-white/80">{short(report.source.ground_truth_sha256)}</dd></div></dl></div><div className="rounded-[1.75rem] border border-indigo-100 bg-indigo-50/70 p-7 sm:p-9"><Info className="size-6 text-indigo-600" /><h2 className="mt-7 text-3xl font-semibold tracking-tight">Boundaries stay visible</h2><ul className="mt-6 space-y-4">{report.limitations.map((limitation) => <li className="flex gap-3 text-sm leading-6 text-slate-700" key={limitation}><CheckCircle2 className="mt-1 size-4 shrink-0 text-indigo-500" />{limitation}</li>)}</ul><Button disabled className="mt-8 w-full">Variant selection is not enabled</Button><p className="mt-3 text-center text-xs text-muted-foreground">A future step will record an explicit, auditable human decision.</p></div></section>
      </div>
    </div>
  )
}

export default function ReliabilityLab() {
  const [state, setState] = useState<ReportLoadResult | { kind: "loading" }>({ kind: "loading" })
  useEffect(() => {
    let active = true
    queueMicrotask(() => { if (active) setState(parseReportModel(reliabilityReportFixture)) })
    return () => { active = false }
  }, [])
  if (state.kind === "loading") return <LoadingState />
  if (state.kind !== "ready") return <ReportError state={state} />
  return <LabReport report={state.report} />
}
