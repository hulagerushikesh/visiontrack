import { type ChangeEvent, useRef, useState } from "react"
import { AlertTriangle, ArrowRight, BarChart3, CheckCircle2, Database, FileCheck2, FlaskConical, ScanSearch } from "lucide-react"

import { Button } from "@/components/ui/button"
import { validateBenchmarkReport } from "./contract.mjs"
import sample from "./sample.json"
import type { BenchmarkMetric, BenchmarkReport, BenchmarkResult } from "./types"
import { ALL_BENCHMARK_METRICS, ALL_BENCHMARK_VARIANTS, benchmarkView } from "./view.mjs"

const MAX_REPORT_BYTES = 1_000_000
const bundledValidation = validateBenchmarkReport(sample)

type ReportSource = {kind:"sample"} | {kind:"file"; filename:string}
type ReportState =
  | {kind:"ready"; report:BenchmarkReport; source:ReportSource}
  | {kind:"error"; message:string; filename:string|null}

function bundledState():ReportState {
  return bundledValidation.valid
    ? {kind:"ready",report:sample as BenchmarkReport,source:{kind:"sample"}}
    : {kind:"error",message:bundledValidation.error,filename:null}
}

function formatMean(result: BenchmarkResult, metric: BenchmarkMetric) {
  const digits = metric.format === "count" ? 3 : 3
  return result.std === null ? result.mean.toFixed(digits) : `${result.mean.toFixed(digits)} ± ${result.std.toFixed(digits)}`
}

function formatDelta(value: number) {
  if (value === 0) return "±0.000"
  return `${value > 0 ? "+" : "−"}${Math.abs(value).toFixed(3)}`
}

function FileSelector({onSelect,label="Select report JSON"}:{onSelect:(event:ChangeEvent<HTMLInputElement>)=>void;label?:string}) {
  return <label className="inline-flex h-11 cursor-pointer items-center justify-center gap-2 rounded-xl bg-primary px-5 text-sm font-semibold text-primary-foreground shadow-[0_10px_30px_-12px_var(--primary)] transition hover:-translate-y-0.5 hover:bg-primary/90 focus-within:ring-2 focus-within:ring-primary focus-within:ring-offset-2"><FileCheck2 className="size-4"/>{label}<input className="sr-only" type="file" accept="application/json,.json" onChange={onSelect}/></label>
}

function ErrorState({message,filename,onSelect,onSample}:{message:string;filename:string|null;onSelect:(event:ChangeEvent<HTMLInputElement>)=>void;onSample:()=>void}) {
  return <div className="mx-auto grid min-h-[78vh] max-w-3xl place-items-center px-5 pb-24 pt-32 text-center"><div className="rounded-[2rem] border border-amber-200 bg-white p-8 shadow-xl shadow-slate-200/60 sm:p-12" role="alert"><AlertTriangle className="mx-auto size-10 text-amber-600"/><p className="mt-6 font-mono text-xs font-semibold uppercase tracking-[.18em] text-amber-700">Local report rejected</p><h1 className="mt-3 text-3xl font-semibold">Benchmark report unavailable</h1>{filename&&<p className="mt-3 break-all font-mono text-xs text-muted-foreground">{filename}</p>}<p className="mt-4 leading-7 text-amber-900/70">{message}</p><p className="mt-3 text-sm leading-6 text-muted-foreground">No values from this file were rendered or retained.</p><div className="mt-7 flex flex-wrap justify-center gap-3"><Button type="button" variant="outline" onClick={onSample}><ArrowRight className="size-4 rotate-180"/>Return to bundled sample</Button><FileSelector onSelect={onSelect} label="Choose another JSON"/></div></div></div>
}

export default function BenchmarkExplorer() {
  const [state,setState]=useState<ReportState>(bundledState)
  const [metricFocus,setMetricFocus]=useState(ALL_BENCHMARK_METRICS)
  const [variantFocus,setVariantFocus]=useState(ALL_BENCHMARK_VARIANTS)
  const loadId=useRef(0)

  const resetView=()=>{setMetricFocus(ALL_BENCHMARK_METRICS);setVariantFocus(ALL_BENCHMARK_VARIANTS)}

  const selectReport=async(event:ChangeEvent<HTMLInputElement>)=>{
    const input=event.currentTarget
    const file=input.files?.[0]
    if(!file)return
    const requestId=++loadId.current
    try{
      if(file.size>MAX_REPORT_BYTES){
        throw new Error("The selected file exceeds the 1 MB local report limit.")
      }
      let parsed:unknown
      try{parsed=JSON.parse(await file.text())}
      catch{throw new Error("The selected file is not valid JSON.")}
      const validation=validateBenchmarkReport(parsed)
      if(!validation.valid)throw new Error(validation.error)
      if(loadId.current===requestId){resetView();setState({kind:"ready",report:parsed as BenchmarkReport,source:{kind:"file",filename:file.name}})}
    }catch(error){
      if(loadId.current===requestId)setState({kind:"error",message:error instanceof Error?error.message:"The selected report could not be read.",filename:file.name})
    }finally{
      input.value=""
    }
  }
  const showSample=()=>{loadId.current+=1;resetView();setState(bundledState())}

  if(state.kind==="error")return <ErrorState message={state.message} filename={state.filename} onSelect={selectReport} onSample={showSample}/>
  const {report,source}=state
  const view=benchmarkView(report,metricFocus,variantFocus) as {metrics:BenchmarkMetric[];variants:BenchmarkReport["variants"]}
  const viewFiltered=view.metrics.length!==report.metrics.length||view.variants.length!==report.variants.length
  return <div className="mx-auto max-w-7xl px-5 pb-28 pt-32 lg:px-8 lg:pt-40">
    <section className="mb-10 rounded-3xl border border-indigo-100 bg-white/90 p-5 shadow-lg shadow-slate-200/50 backdrop-blur sm:p-6" aria-label="Benchmark report source"><div className="flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between"><div className="flex min-w-0 items-start gap-3"><div className="grid size-10 shrink-0 place-items-center rounded-2xl bg-indigo-50 text-primary"><FileCheck2 className="size-5"/></div><div className="min-w-0"><p className="truncate text-sm font-semibold">{source.kind==="sample"?"Bundled checked-in sample":source.filename}</p><p className="mt-1 text-xs leading-5 text-muted-foreground">Validated schema v{report.schema_version} · Processed only in this browser tab. Nothing is uploaded.</p></div></div><div className="flex flex-wrap gap-2">{source.kind==="file"&&<Button type="button" variant="outline" onClick={showSample}><ArrowRight className="size-4 rotate-180"/>Return to sample</Button>}<FileSelector onSelect={selectReport}/></div></div></section>
    <section className="grid gap-10 lg:grid-cols-[1.1fr_.9fr] lg:items-end">
      <div><p className="mb-5 inline-flex items-center gap-2 rounded-full border border-emerald-100 bg-emerald-50 px-3 py-1.5 font-mono text-[10px] font-semibold uppercase tracking-[.16em] text-emerald-700"><BarChart3 className="size-3"/>Read-only benchmark explorer</p><h1 className="text-balance text-5xl font-semibold tracking-[-.05em] sm:text-7xl">Measured results.<br/><span className="text-muted-foreground">Visible protocol.</span></h1><p className="mt-7 max-w-2xl text-lg leading-8 text-muted-foreground">{report.summary}</p></div>
      <div className="rounded-3xl border border-indigo-100 bg-gradient-to-br from-indigo-50 to-cyan-50 p-7"><div className="flex items-center gap-3"><FileCheck2 className="size-5 text-primary"/><p className="font-semibold">{source.kind==="sample"?"Validated checked-in artifact":"Validated local report"}</p></div><dl className="mt-6 grid gap-4 text-sm"><div><dt className="text-muted-foreground">Source</dt><dd className="mt-1 break-all font-mono text-xs">{report.provenance.source_document}</dd></div><div><dt className="text-muted-foreground">Origin</dt><dd className="mt-1 font-mono text-xs">{report.provenance.source_kind.replaceAll("_"," ")}</dd></div><div><dt className="text-muted-foreground">Config hash</dt><dd className="mt-1 font-mono text-xs">{report.provenance.config_hash}</dd></div><div><dt className="text-muted-foreground">Contract</dt><dd className="mt-1 break-all">schema v{report.schema_version} · {report.report_id}</dd></div></dl></div>
    </section>

    <section className="mt-14 grid gap-4 sm:grid-cols-2 lg:grid-cols-5" aria-label="Benchmark protocol">
      {[[Database,"Dataset",`${report.dataset.name} · ${report.dataset.split}`],[ScanSearch,"Detector",report.dataset.detector],[FlaskConical,"Protocol",report.dataset.protocol],[BarChart3,"Runs",`${report.dataset.runs_per_variant} per variant`],[CheckCircle2,"Baseline",report.baseline]].map(([Icon,label,value])=><div key={String(label)} className="rounded-2xl border border-border bg-card p-5"><Icon className="size-5 text-primary"/><p className="mt-5 text-xs font-semibold uppercase tracking-wider text-muted-foreground">{String(label)}</p><p className="mt-2 text-sm font-semibold leading-6">{String(value)}</p></div>)}
    </section>

    <section className="mt-14 overflow-hidden rounded-3xl border border-border bg-white shadow-sm">
      <div className="border-b border-border px-6 py-6 sm:px-8"><h2 className="text-2xl font-semibold tracking-tight">Variant evidence</h2><p className="mt-2 text-sm leading-6 text-muted-foreground">Means, published spread, paired Δ, and Wilcoxon significance compare each variant with {report.baseline}. Unpublished values remain visibly absent. No winner is selected automatically.</p><div className="mt-6 grid gap-4 rounded-2xl border border-indigo-100 bg-indigo-50/50 p-4 sm:grid-cols-[1fr_1fr_auto] sm:items-end" aria-label="Evidence view controls"><label className="grid gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Metric focus<select value={metricFocus} onChange={event=>setMetricFocus(event.target.value)} className="h-10 rounded-xl border border-input bg-white px-3 text-sm font-medium normal-case tracking-normal text-foreground"><option value={ALL_BENCHMARK_METRICS}>All metrics</option>{report.metrics.map(metric=><option key={metric.key} value={metric.key}>{metric.label}</option>)}</select></label><label className="grid gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Variant focus<select value={variantFocus} onChange={event=>setVariantFocus(event.target.value)} className="h-10 rounded-xl border border-input bg-white px-3 text-sm font-medium normal-case tracking-normal text-foreground"><option value={ALL_BENCHMARK_VARIANTS}>All variants</option>{report.variants.filter(variant=>!variant.baseline).map(variant=><option key={variant.name} value={variant.name}>{variant.name}</option>)}</select></label><Button type="button" size="sm" variant="outline" disabled={!viewFiltered} onClick={resetView}>Reset evidence view</Button></div><p className="mt-3 text-xs text-muted-foreground" role="status" aria-live="polite">Showing {view.variants.length} of {report.variants.length} variants and {view.metrics.length} of {report.metrics.length} metrics. The baseline remains visible in every focused comparison.</p></div>
      <div className="overflow-x-auto"><table className="w-full min-w-[980px] border-collapse text-left text-sm"><caption className="sr-only">Tracker metrics and paired significance results for the active evidence view</caption><thead><tr className="bg-slate-50 text-xs uppercase tracking-wider text-muted-foreground"><th scope="col" className="px-6 py-4 sm:px-8">Variant</th>{view.metrics.map(metric=><th scope="col" className="px-5 py-4" key={metric.key}>{metric.label}<span className="mt-1 block font-normal normal-case tracking-normal">{metric.direction} is better</span></th>)}</tr></thead><tbody>{view.variants.map(variant=><tr key={variant.name} className="border-t border-border align-top"><th scope="row" className="px-6 py-5 font-mono text-xs sm:px-8">{variant.name}{variant.baseline&&<span className="ml-2 rounded-full bg-indigo-50 px-2 py-1 font-sans text-[10px] font-semibold uppercase text-primary">baseline</span>}</th>{view.metrics.map(metric=>{const result=variant.values[metric.key];const significance=result.p_value===null?(variant.baseline?"reference":result.significant?"p<0.05":"n.s."):`p=${result.p_value.toFixed(2)}`;return <td className="px-5 py-5" key={metric.key}><p className="font-semibold tabular-nums">{formatMean(result,metric)}</p><p className="mt-2 font-mono text-[11px] text-muted-foreground">Δ {formatDelta(result.delta)} · {significance}{result.significant&&<span className="ml-2 rounded bg-emerald-50 px-1.5 py-0.5 font-sans font-semibold text-emerald-700">significant</span>}</p></td>})}</tr>)}</tbody></table></div>
    </section>

    <section className="mt-10 grid gap-6 lg:grid-cols-[1fr_auto] lg:items-start"><div className="rounded-2xl border border-amber-200 bg-amber-50 p-6"><div className="flex items-center gap-2 font-semibold text-amber-900"><AlertTriangle className="size-5"/>Read the limits first</div><ul className="mt-4 grid gap-3 text-sm leading-6 text-amber-950/70">{report.limitations.map(limit=><li className="flex gap-3" key={limit}><span aria-hidden="true">—</span><span>{limit}</span></li>)}</ul></div><Button asChild variant="outline"><a href="/benchmark/synthetic">Open full generated benchmark <ArrowRight className="size-4"/></a></Button></section>
  </div>
}
