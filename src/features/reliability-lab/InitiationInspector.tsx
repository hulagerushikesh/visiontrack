import { useEffect, useRef, useState, type ChangeEvent } from "react"
import type { ReliabilityReport } from "./types"
import { dispositionLabels, eventLabels, InitiationFileReader, type InitiationFrame, type InitiationTrace, type TraceLoadResult } from "./initiation"

const control = "inline-flex min-h-10 items-center justify-center rounded-xl border border-indigo-200 bg-white px-4 py-2 text-sm font-semibold text-indigo-700 shadow-sm transition hover:bg-indigo-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-600 disabled:cursor-not-allowed disabled:opacity-50"

export function InitiationFrameView({ frame }: { frame: InitiationFrame }) {
  return <div className="mt-6 grid gap-4 lg:grid-cols-3">
    <article className="rounded-2xl border border-slate-200 bg-white p-5"><h4 className="font-semibold">1. Detector proposals</h4><p className="mt-1 text-xs leading-5 text-muted-foreground">A score measures detector confidence, not whether a proposal is true.</p>
      {frame.detections.length === 0 ? <p className="mt-5 text-sm text-muted-foreground">No detections recorded in this frame.</p> : <ul className="mt-5 space-y-3">{frame.detections.map(d => <li className="rounded-xl bg-slate-50 p-3 text-sm" key={d.detection_index}><p className="font-semibold">Detection {d.detection_index} · score {String(d.score)}</p><p className="mt-1">{dispositionLabels[d.disposition]}</p><p className="mt-2 text-xs text-muted-foreground">Class {d.class_id}{d.track_id === null ? " · No track assigned" : ` · Assigned ID ${d.track_id}`}</p></li>)}</ul>}
    </article>
    <article className="rounded-2xl border border-indigo-200 bg-indigo-50/50 p-5"><h4 className="font-semibold">2. Internal track state</h4><p className="mt-1 text-xs leading-5 text-muted-foreground">Tentative births and coasting tracks can exist without a public box.</p>
      {frame.tracks.length === 0 ? <p className="mt-5 text-sm text-muted-foreground">No internal tracks recorded in this frame.</p> : <ul className="mt-5 space-y-3">{frame.tracks.map(t => <li className="rounded-xl border border-indigo-100 bg-white p-3 text-sm" key={t.track_id}><p className="flex flex-wrap items-center justify-between gap-2 font-semibold"><span>ID {t.track_id}</span><span className="rounded-full bg-indigo-50 px-2 py-1 text-xs">{t.state}</span></p><p className="mt-2">{eventLabels[t.event]}</p><p className="mt-2 text-xs text-muted-foreground">Born at {t.birth_frame} · {t.hits} hits · {t.time_since_update} missed frames</p><p className="mt-1 text-xs">{t.public ? "Public in this frame" : "No public box in this frame"}</p></li>)}</ul>}
    </article>
    <article className="rounded-2xl border border-emerald-200 bg-emerald-50/50 p-5"><h4 className="font-semibold">3. Public output</h4><p className="mt-1 text-xs leading-5 text-muted-foreground">Public IDs recorded in this trace. This panel contains metadata, not footage.</p>
      <p className="mt-5 text-lg font-semibold">{frame.public_track_ids.length === 0 ? "No public tracks" : frame.public_track_ids.map(id => `ID ${id}`).join(", ")}</p><p className="mt-3 text-sm leading-6 text-muted-foreground">An empty output does not prove that no object was present. Track IDs are temporary labels within this run, not personal identities.</p>
    </article>
  </div>
}

export function InitiationTimeline({ trace }: { trace: InitiationTrace }) {
  const [offset, setOffset] = useState(0)
  const frame = trace.frames[offset]
  return <div className="mt-6">
    <div className="flex flex-wrap items-start justify-between gap-4"><div><p className="text-sm font-semibold text-emerald-700">Content fingerprint and report/run lineage checked</p><h3 className="mt-2 text-2xl font-semibold">{trace.variant} · Frame {frame.frame_index}</h3><p className="mt-2 text-sm text-muted-foreground">Window {trace.trace_frame_range.start}–{trace.trace_frame_range.end - 1}. Replay began at {trace.replay_frame_range.start}, preserving earlier track history.</p></div></div>
    <div className="mt-6 flex items-center gap-3"><button type="button" className={control} disabled={offset === 0} onClick={() => setOffset(value => value - 1)}>Previous</button><label className="min-w-0 flex-1 text-sm font-medium">Trace frame {frame.frame_index}<input aria-label="Initiation trace frame" type="range" min={trace.trace_frame_range.start} max={trace.trace_frame_range.end - 1} value={frame.frame_index} onChange={e => setOffset(Number(e.target.value) - trace.trace_frame_range.start)} className="mt-2 block w-full accent-indigo-600" /></label><button type="button" className={control} disabled={offset === trace.frames.length - 1} onClick={() => setOffset(value => value + 1)}>Next</button></div>
    <p className="mt-3 text-sm text-muted-foreground" role="status" aria-live="polite">Frame {frame.frame_index}: {frame.detections.length} detections, {frame.tracks.length} internal track rows, {frame.public_track_ids.length} public tracks.</p>
    <InitiationFrameView frame={frame} />
    <details className="mt-5 rounded-2xl border border-slate-200 bg-white p-5"><summary className="cursor-pointer font-semibold">Configuration and provenance</summary><p className="mt-3 text-sm leading-6 text-muted-foreground">The local producer declares exact saved-output replay parity. The browser checks content and lineage; it does not rerun Python, authenticate the producer, verify detections against footage, or establish tracking accuracy.</p><dl className="mt-4 grid gap-3 text-xs sm:grid-cols-2">{[["Trace", trace.trace_id], ["Run", trace.run_id], ["Detections", trace.detection_sha256], ["Public output", trace.track_sha256]].map(([label, value]) => <div key={label}><dt className="font-semibold">{label}</dt><dd className="mt-1 break-all font-mono">{value}</dd></div>)}</dl><p className="mt-4 text-xs text-muted-foreground">Producer: VisionTrack {trace.producer.visiontrack} · Python {trace.producer.python} · NumPy {trace.producer.numpy}. Source hashes are declared, not authenticated here.</p><pre className="mt-4 max-h-64 overflow-auto rounded-xl bg-slate-50 p-4 text-xs"><code>{JSON.stringify(trace.config, null, 2)}</code></pre></details>
  </div>
}

export default function InitiationInspector({ report, enabled }: { report: ReliabilityReport; enabled: boolean }) {
  const [state, setState] = useState<TraceLoadResult | { kind: "idle" | "loading" }>({ kind: "idle" })
  const reader = useRef(new InitiationFileReader())
  useEffect(() => { const current = reader.current; return () => current.cancel() }, [report])
  const close = () => { reader.current.cancel(); setState({ kind: "idle" }) }
  const select = async (event: ChangeEvent<HTMLInputElement>) => {
    const input = event.currentTarget, file = input.files?.[0]
    input.value = ""
    if (!file || !enabled) return
    setState({ kind: "loading" })
    const result = await reader.current.read(file, report)
    if (result) setState(result)
  }
  return <section className="mt-20 rounded-3xl border border-indigo-100 bg-white/90 p-5 sm:p-8" aria-labelledby="initiation-title">
    <p className="font-mono text-xs font-semibold uppercase tracking-[.16em] text-primary">Optional local diagnosis</p><h2 id="initiation-title" className="mt-3 text-3xl font-semibold tracking-tight">Why did a detection become a track?</h2><p className="mt-3 max-w-3xl text-sm leading-7 text-muted-foreground">Follow score admission, tentative births, confirmation and internal survival in one saved run. Import a separate numeric trace; your report and tracker settings stay unchanged. Files stay in this tab’s memory. Nothing is uploaded or saved to disk.</p>
    {!enabled ? <p className="mt-5 rounded-xl bg-amber-50 p-4 text-sm text-amber-900">Import your local report.json first. The illustrative sample cannot establish trace lineage.</p> : <><p className="mt-5 text-sm leading-6 text-muted-foreground">Using the demo with <code>--with-initiation</code>? Select <code>initiation-trace.json</code> from the same <code>try-in-browser</code> folder as your report. No second command is needed.</p><details className="mt-5 rounded-xl border border-slate-200 p-4"><summary className="cursor-pointer text-sm font-semibold">Create a trace for another saved run</summary><p className="mt-3 text-sm leading-6 text-muted-foreground">From your current source checkout, use the bundle path printed by lab-demo, not report.json or a GitHub URL. Choose a declared variant and 1–200 frames inside the report range. Export to a new file outside the bundle.</p><pre className="mt-3 overflow-x-auto rounded-xl bg-slate-950 p-4 text-xs leading-6 text-slate-100"><code>{`visiontrack lab-initiation "BUNDLE_PATH" --variant ${report.variants[0].name} --start ${report.experiment.frame_range.start} --end ${Math.min(report.experiment.frame_range.start + 10, report.experiment.frame_range.end)} --json > initiation-trace.json`}</code></pre><a className="mt-3 inline-block text-sm font-semibold text-primary underline underline-offset-4" href="/docs/INITIATION_DIAGNOSTIC/">Read the walkthrough</a></details><div className="mt-5 flex flex-wrap gap-3"><label className={`${control} cursor-pointer focus-within:ring-2 focus-within:ring-indigo-600`}>Import initiation trace<input className="sr-only" type="file" accept="application/json,.json" onChange={select} /></label>{state.kind !== "idle" && <button type="button" className={control} onClick={close}>Close trace</button>}</div></>}
    <div role="status" aria-live="polite" className="mt-4 text-sm">{state.kind === "loading" && <p className="text-indigo-700">Checking content, frame history and exact report/run lineage…</p>}{state.kind === "error" && <p className="rounded-xl bg-amber-50 p-4 text-amber-900"><strong>Trace rejected:</strong> {state.message}</p>}</div>
    {enabled && state.kind === "ready" && <InitiationTimeline key={state.trace.trace_id} trace={state.trace} />}
    <p className="mt-5 text-xs leading-6 text-muted-foreground">Unmatched does not reveal which gate or competing assignment rejected a pair. These states do not establish physical identity, a better tracker, or traffic-count accuracy.</p>
  </section>
}
