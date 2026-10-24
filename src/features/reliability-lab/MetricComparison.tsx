import type { ReliabilityReport } from "./types"

type MetricMeaning = { label: string; meaning: string; direction: "Higher" | "Lower" | "Context" }

// Match the values exported by eval/mot.py and eval/hota.py; never rescale them.
export const metricMeanings: Record<string, MetricMeaning> = {
  HOTA: { label: "Detection and association balance", meaning: "Balances finding reference objects with keeping their tracks associated across frames.", direction: "Higher" },
  IDF1: { label: "Tracking-ID consistency", meaning: "Balances identity precision and recall using a sequence-wide matching of tracking IDs to reference IDs.", direction: "Higher" },
  MOTA: { label: "Combined tracking error score", meaning: "Penalizes misses, extra outputs, and ID switches relative to reference boxes. It can be negative.", direction: "Higher" },
  IDSW: { label: "Tracking-ID changes", meaning: "Counts reference objects matched to a different tracking ID than before.", direction: "Lower" },
  Frag: { label: "Tracking interruptions", meaning: "Counts transitions from a matched reference object to an unmatched one under this evaluator.", direction: "Lower" },
  MOTP: { label: "Matched-box overlap", meaning: "Average intersection-over-union of matched boxes in this implementation; this is not a distance error.", direction: "Higher" },
  FP: { label: "Extra outputs", meaning: "Tracker boxes without a matching reference box under the evaluation rules.", direction: "Lower" },
  FN: { label: "Missed reference boxes", meaning: "Reference boxes without a matching tracker output under the evaluation rules.", direction: "Lower" },
  TP: { label: "Matched reference boxes", meaning: "Reference boxes matched to tracker outputs under the evaluation rules.", direction: "Higher" },
  precision: { label: "Output match precision", meaning: "Fraction of evaluated tracker boxes matched to reference boxes.", direction: "Higher" },
  recall: { label: "Reference-box recall", meaning: "Fraction of reference boxes matched to tracker outputs.", direction: "Higher" },
  MT: { label: "Mostly tracked trajectories", meaning: "Reference trajectories matched for at least 80% of their evaluated lifetime.", direction: "Higher" },
  ML: { label: "Mostly lost trajectories", meaning: "Reference trajectories matched for less than 20% of their evaluated lifetime.", direction: "Lower" },
  PT: { label: "Partially tracked trajectories", meaning: "Reference trajectories between the mostly-tracked and mostly-lost categories; interpret with both categories.", direction: "Context" },
  frames: { label: "Evaluated frames", meaning: "Number of pictures evaluated, not elapsed seconds or a quality score.", direction: "Context" },
  gt_boxes: { label: "Reference boxes", meaning: "Number of evaluated reference boxes across frames, not distinct people.", direction: "Context" },
  unique_gt: { label: "Reference trajectories", meaning: "Distinct reference IDs in this evaluation, not persistent personal identities.", direction: "Context" },
  DetA: { label: "Detection accuracy component", meaning: "HOTA detection component across its overlap thresholds.", direction: "Higher" },
  AssA: { label: "Association accuracy component", meaning: "HOTA association component across its overlap thresholds.", direction: "Higher" },
  DetRe: { label: "HOTA detection recall", meaning: "Detection recall averaged across HOTA overlap thresholds.", direction: "Higher" },
  DetPr: { label: "HOTA detection precision", meaning: "Detection precision averaged across HOTA overlap thresholds.", direction: "Higher" },
  AssRe: { label: "HOTA association recall", meaning: "Association recall averaged across HOTA overlap thresholds.", direction: "Higher" },
  AssPr: { label: "HOTA association precision", meaning: "Association precision averaged across HOTA overlap thresholds.", direction: "Higher" },
  IDP: { label: "Identity precision", meaning: "Precision under the sequence-wide matching of tracking IDs to reference IDs.", direction: "Higher" },
  IDR: { label: "Identity recall", meaning: "Recall under the sequence-wide matching of tracking IDs to reference IDs.", direction: "Higher" },
  IDTP: { label: "Identity-matched boxes", meaning: "Correctly matched boxes under sequence-wide identity matching.", direction: "Higher" },
  IDFP: { label: "Identity false-positive boxes", meaning: "Extra boxes under sequence-wide identity matching.", direction: "Lower" },
  IDFN: { label: "Identity false-negative boxes", meaning: "Missed boxes under sequence-wide identity matching.", direction: "Lower" },
}

function number(value: number, signed = false) {
  const rendered = Number.isInteger(value) ? String(value) : value.toFixed(4).replace(/0+$/, "").replace(/\.$/, "")
  return signed && value > 0 ? `+${rendered}` : rendered
}

function MetricTable({ report, metrics }: { report: ReliabilityReport; metrics: string[] }) {
  return (
    <div className="overflow-x-auto rounded-3xl border border-border bg-white shadow-sm">
      <table className="w-full min-w-[680px] border-collapse text-left">
        <caption className="px-6 py-5 text-left text-sm text-muted-foreground">Recorded value and change from {report.experiment.baseline}. Values retain the report&apos;s original units.</caption>
        <thead className="border-y border-border bg-slate-50/80 text-xs uppercase tracking-[.12em] text-muted-foreground">
          <tr><th scope="col" className="px-6 py-4">What is measured</th>{report.variants.map((variant) => <th scope="col" className="px-6 py-4" key={variant.name}>{variant.name}{variant.baseline && <span className="ml-2 rounded-full bg-indigo-100 px-2 py-1 text-[9px] text-indigo-700">baseline</span>}</th>)}</tr>
        </thead>
        <tbody>{metrics.map((metric) => {
          let info = Object.hasOwn(metricMeanings, metric) ? metricMeanings[metric] : undefined
          if (report.evaluator === "visiontrack.metrics/v2") {
            if (metric === "Frag") info = { ...metricMeanings.Frag, label: "Tracking resumptions after interruptions", meaning: "Counts resumed matches after a previously matched reference object went unmatched; terminal losses are not fragmentations under evaluator v2." }
            if (metric === "MT") info = { ...metricMeanings.MT, meaning: "Reference trajectories matched for more than 80% of their evaluated lifetime under evaluator v2." }
          }
          return <tr className="border-b border-border last:border-0" key={metric}><th scope="row" className="max-w-sm px-6 py-4 text-sm font-normal"><span className="font-semibold">{info?.label ?? metric} <span className="font-mono text-xs text-muted-foreground">({metric})</span></span><span className="mt-1 block text-xs leading-5 text-muted-foreground">{info?.meaning ?? "Additional metric supplied by this report; consult its evaluation protocol before interpreting it."}</span><span className="mt-1 block text-xs font-medium text-slate-700">{info ? info.direction === "Context" ? "Context only · no preferred direction" : `${info.direction} is preferred for this metric alone` : "Direction not specified"}</span></th>{report.variants.map((variant) => <td className="px-6 py-4" key={variant.name}><span className="block font-semibold">{number(variant.metrics[metric])}</span><span className="mt-1 block text-xs text-muted-foreground">Change: {number(variant.metric_deltas[metric], true)}</span></td>)}</tr>
        })}</tbody>
      </table>
    </div>
  )
}

export default function MetricComparison({ report }: { report: ReliabilityReport }) {
  const metrics = Object.keys(report.variants[0].metrics)
  const core = metrics.filter((key) => ["HOTA", "IDF1", "MOTA", "IDSW", "Frag"].includes(key))
  const other = core.length ? metrics.filter((key) => !core.includes(key)) : []
  return (
    <div>
      <div className="mb-6 rounded-3xl border border-indigo-100 bg-indigo-50/60 p-6 text-sm leading-6 text-slate-700">
        <h3 className="text-lg font-semibold text-slate-900">How to read this comparison</h3>
        <ol className="mt-4 grid gap-4 md:grid-cols-3">
          <li><strong className="block text-slate-900">1. Compare configurations, not people</strong>A variant is one tracker version or settings choice. <strong>{report.experiment.baseline}</strong> is the baseline: the reference configuration, not a guaranteed best tracker.</li>
          <li><strong className="block text-slate-900">2. Read one row at a time</strong>Each cell shows a recorded value and its change from the baseline. For example only, 2 ID switches becoming 1 gives a change of −1: one fewer switch, not a negative error count.</li>
          <li><strong className="block text-slate-900">3. Look for trade-offs</strong>Fewer ID switches can still come with more missed objects. Read several metrics and inspect events; no single number proves a tracker is best.</li>
        </ol>
        <p className="mt-4">Scores are shown as recorded, not automatically converted to percentages. For example only, an IDF1 value of 0.68 is 68% on that metric&apos;s scale, not a claim of 68% real-world accuracy.</p>
        <p className="mt-3">These are summaries over this report&apos;s evaluated frame range, not just the failure event you opened. Changes are descriptive, not a statistical significance test. Synthetic or illustrative results do not establish real-world performance. No decision is required to explore.</p>
        <p className="mt-3"><strong>Evaluation rules:</strong> metric evaluator {report.evaluator === "visiontrack.metrics/v2" ? "v2" : "v1 (historical)"}; input filtering {report.preprocessing ? "MOT17 v2" : "v1 (historical Lab policy)"}. Filtering decides which reference objects and tracker outputs enter scoring; it does not change tracking. Reports using different rules are not directly comparable.</p>
      </div>
      <details className="mb-6 rounded-2xl border border-border bg-white p-5">
        <summary className="cursor-pointer text-sm font-semibold">Which settings were actually recorded? (optional)</summary>
        <p className="mt-3 text-sm leading-6 text-muted-foreground">Names alone do not explain a configuration. These are the settings recorded in this report; they do not prove which setting caused a result.</p>
        <div className="mt-4 grid gap-4 md:grid-cols-2">{report.variants.map((variant) => <div className="min-w-0 rounded-xl bg-slate-50 p-4" key={variant.name}><h4 className="text-sm font-semibold">{variant.name}{variant.baseline ? " · baseline" : ""}</h4><pre className="mt-3 overflow-x-auto whitespace-pre-wrap break-words font-mono text-xs leading-6">{JSON.stringify(variant.configuration, null, 2)}</pre></div>)}</div>
      </details>
      <MetricTable report={report} metrics={core.length ? core : metrics} />
      {other.length > 0 && <details className="mt-5 rounded-3xl border border-border bg-white p-4"><summary className="cursor-pointer p-2 text-sm font-semibold">More recorded metrics and evaluation counts ({other.length})</summary><div className="mt-4"><MetricTable report={report} metrics={other} /></div></details>}
    </div>
  )
}
