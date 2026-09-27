import { AlertTriangle, ArrowRight, BarChart3, CheckCircle2, Database, FileCheck2, FlaskConical, ScanSearch } from "lucide-react"

import { Button } from "@/components/ui/button"
import { validateBenchmarkReport } from "./contract.mjs"
import sample from "./sample.json"
import type { BenchmarkMetric, BenchmarkReport, BenchmarkResult } from "./types"

const validation = validateBenchmarkReport(sample)
const report = validation.valid ? sample as BenchmarkReport : null

function formatMean(result: BenchmarkResult, metric: BenchmarkMetric) {
  const digits = metric.format === "count" ? 3 : 3
  return `${result.mean.toFixed(digits)} ± ${result.std.toFixed(digits)}`
}

function formatDelta(value: number) {
  if (value === 0) return "±0.000"
  return `${value > 0 ? "+" : "−"}${Math.abs(value).toFixed(3)}`
}

function ErrorState({message}:{message:string}) {
  return <div className="mx-auto grid min-h-[70vh] max-w-3xl place-items-center px-5 pt-24 text-center"><div className="rounded-3xl border border-amber-200 bg-amber-50 p-10"><AlertTriangle className="mx-auto size-9 text-amber-600"/><h1 className="mt-5 text-3xl font-semibold">Benchmark report unavailable</h1><p className="mt-3 leading-7 text-amber-900/70">{message}</p></div></div>
}

export default function BenchmarkExplorer() {
  if (!report) return <ErrorState message={validation.valid ? "Unknown validation error." : validation.error}/>
  return <div className="mx-auto max-w-7xl px-5 pb-28 pt-32 lg:px-8 lg:pt-40">
    <section className="grid gap-10 lg:grid-cols-[1.1fr_.9fr] lg:items-end">
      <div><p className="mb-5 inline-flex items-center gap-2 rounded-full border border-emerald-100 bg-emerald-50 px-3 py-1.5 font-mono text-[10px] font-semibold uppercase tracking-[.16em] text-emerald-700"><BarChart3 className="size-3"/>Read-only benchmark explorer</p><h1 className="text-balance text-5xl font-semibold tracking-[-.05em] sm:text-7xl">Measured results.<br/><span className="text-muted-foreground">Visible protocol.</span></h1><p className="mt-7 max-w-2xl text-lg leading-8 text-muted-foreground">{report.summary}</p></div>
      <div className="rounded-3xl border border-indigo-100 bg-gradient-to-br from-indigo-50 to-cyan-50 p-7"><div className="flex items-center gap-3"><FileCheck2 className="size-5 text-primary"/><p className="font-semibold">Validated checked-in artifact</p></div><dl className="mt-6 grid gap-4 text-sm"><div><dt className="text-muted-foreground">Source</dt><dd className="mt-1 font-mono text-xs">{report.provenance.source_document}</dd></div><div><dt className="text-muted-foreground">Config hash</dt><dd className="mt-1 font-mono text-xs">{report.provenance.config_hash}</dd></div><div><dt className="text-muted-foreground">Contract</dt><dd className="mt-1">schema v{report.schema_version} · {report.report_id}</dd></div></dl></div>
    </section>

    <section className="mt-14 grid gap-4 sm:grid-cols-2 lg:grid-cols-5" aria-label="Benchmark protocol">
      {[[Database,"Dataset",`${report.dataset.name} · ${report.dataset.split}`],[ScanSearch,"Detector",report.dataset.detector],[FlaskConical,"Protocol",report.dataset.protocol],[BarChart3,"Runs",`${report.dataset.runs_per_variant} per variant`],[CheckCircle2,"Baseline",report.baseline]].map(([Icon,label,value])=><div key={String(label)} className="rounded-2xl border border-border bg-card p-5"><Icon className="size-5 text-primary"/><p className="mt-5 text-xs font-semibold uppercase tracking-wider text-muted-foreground">{String(label)}</p><p className="mt-2 text-sm font-semibold leading-6">{String(value)}</p></div>)}
    </section>

    <section className="mt-14 overflow-hidden rounded-3xl border border-border bg-white shadow-sm">
      <div className="border-b border-border px-6 py-6 sm:px-8"><h2 className="text-2xl font-semibold tracking-tight">Variant evidence</h2><p className="mt-2 text-sm leading-6 text-muted-foreground">Mean ± standard deviation. Δ and Wilcoxon p-values compare each variant with {report.baseline}. No winner is selected automatically.</p></div>
      <div className="overflow-x-auto"><table className="w-full min-w-[980px] border-collapse text-left text-sm"><caption className="sr-only">Tracker metrics and paired significance results</caption><thead><tr className="bg-slate-50 text-xs uppercase tracking-wider text-muted-foreground"><th scope="col" className="px-6 py-4 sm:px-8">Variant</th>{report.metrics.map(metric=><th scope="col" className="px-5 py-4" key={metric.key}>{metric.label}<span className="mt-1 block font-normal normal-case tracking-normal">{metric.direction} is better</span></th>)}</tr></thead><tbody>{report.variants.map(variant=><tr key={variant.name} className="border-t border-border align-top"><th scope="row" className="px-6 py-5 font-mono text-xs sm:px-8">{variant.name}{variant.baseline&&<span className="ml-2 rounded-full bg-indigo-50 px-2 py-1 font-sans text-[10px] font-semibold uppercase text-primary">baseline</span>}</th>{report.metrics.map(metric=>{const result=variant.values[metric.key];return <td className="px-5 py-5" key={metric.key}><p className="font-semibold tabular-nums">{formatMean(result,metric)}</p><p className="mt-2 font-mono text-[11px] text-muted-foreground">Δ {formatDelta(result.delta)} · p={result.p_value.toFixed(2)}{result.significant&&<span className="ml-2 rounded bg-emerald-50 px-1.5 py-0.5 font-sans font-semibold text-emerald-700">p&lt;0.05</span>}</p></td>})}</tr>)}</tbody></table></div>
    </section>

    <section className="mt-10 grid gap-6 lg:grid-cols-[1fr_auto] lg:items-start"><div className="rounded-2xl border border-amber-200 bg-amber-50 p-6"><div className="flex items-center gap-2 font-semibold text-amber-900"><AlertTriangle className="size-5"/>Read the limits first</div><ul className="mt-4 grid gap-3 text-sm leading-6 text-amber-950/70">{report.limitations.map(limit=><li className="flex gap-3" key={limit}><span aria-hidden="true">—</span><span>{limit}</span></li>)}</ul></div><Button asChild variant="outline"><a href="/benchmark">Open full generated benchmark <ArrowRight className="size-4"/></a></Button></section>
  </div>
}
