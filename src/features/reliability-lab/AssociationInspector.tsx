import { useEffect, useRef, useState, type ChangeEvent } from "react"
import type { ReliabilityReport } from "./types"
import type { InitiationFrame, InitiationTrace } from "./initiation"
import { AssociationFileReader, associationCommand, availableAssociationTracks, outcomeLabels, stageLabels, type AssociationExplanation, type AssociationLoadResult, type AssociationPair, type AssociationSelection } from "./association"

const control = "inline-flex min-h-10 items-center justify-center rounded-xl border border-indigo-200 bg-white px-4 py-2 text-sm font-semibold text-indigo-700 shadow-sm transition hover:bg-indigo-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-600"
// Keep full recorded precision visible; rounding a boundary can make a failure look like a pass.
const numeric = (value: number) => String(value)

function PairFacts({ pair: p }: { pair: AssociationPair }) {
  const failed = p.failed_gates.length > 0
  return <div className="mt-4">
    <p className={`font-semibold ${failed || !p.cost_eligible ? "text-amber-900" : "text-indigo-800"}`}>{outcomeLabels[p.outcome]}</p>
    <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
      <div><dt className="font-semibold">Box overlap (IoU)</dt><dd className="mt-1 break-words">{numeric(p.iou)} ≥ {numeric(p.minimum_iou)} required · {p.failed_gates.includes("iou") ? "Failed" : "Passed"}</dd></div>
      <div><dt className="font-semibold">Object class</dt><dd className="mt-1">{!p.class_gate_enabled ? "Class gate disabled" : p.class_mismatch ? "Different classes · Failed" : "Compatible classes · Passed"}</dd></div>
      <div><dt className="font-semibold">Motion consistency (Kalman)</dt><dd className="mt-1 break-words">{p.mahalanobis_limit === null ? "Hard Kalman gate disabled" : `${numeric(p.mahalanobis_squared!)} ≤ ${numeric(p.mahalanobis_limit)} required · ${p.failed_gates.includes("mahalanobis") ? "Failed" : "Passed"}`}</dd>{p.mahalanobis_limit === null && p.mahalanobis_squared !== null && <dd className="mt-1 text-xs text-muted-foreground">Distance {numeric(p.mahalanobis_squared)} was recorded for the soft uncertainty cost.</dd>}</div>
      <div><dt className="font-semibold">Actual solver cost</dt><dd className="mt-1 break-words">{numeric(p.solver_cost)} ≤ {numeric(p.maximum_cost)} required · {p.cost_eligible ? "Eligible" : "Ineligible"}</dd><dd className="mt-1 text-xs text-muted-foreground">A failed hard gate also makes this cost ineligible.</dd></div>
    </dl>
    <p className="mt-4 text-sm leading-6">{p.outcome === "selected" ? "The saved solver selected this pair. Confirmation and public output are separate lifecycle steps." : p.outcome === "blocked_by_gate" ? "The recorded pair failed one or more hard tests above. This does not show that disabling a test would improve tracking." : p.outcome === "above_cost_limit" ? "The pair passed its hard gates, but its cost exceeded the acceptance limit." : "The pair was allowed, but the one-to-one assignment did not select it. The returned partners below do not prove a counterfactual cause."}</p>
    <p className="mt-3 text-sm text-muted-foreground">This track’s returned partner: {p.track_matched_detection_index === null ? "none" : `detection ${p.track_matched_detection_index}`}. This detection’s returned partner: {p.detection_matched_track_id === null ? "none" : `ID ${p.detection_matched_track_id}`}.</p>
    <details className="mt-3 text-xs text-muted-foreground"><summary className="cursor-pointer font-semibold">Predicted track geometry</summary><p className="mt-2 break-words">Box: {p.predicted_xyxy.map(numeric).join(", ")} · Class: {p.track_class_id}</p></details>
  </div>
}

export function AssociationExplanationView({ explanation: e }: { explanation: AssociationExplanation }) {
  return <div className="mt-5" aria-label="Checked association explanation">
    <p className="text-sm font-semibold text-emerald-700">Content fingerprint, report/run and selected trace pair checked</p>
    <h4 className="mt-2 text-xl font-semibold">Frame {e.frame_index} · ID {e.track_id} + detection {e.detection_index}</h4>
    <p className="mt-2 text-sm leading-6 text-muted-foreground">These are saved numeric observations from a Python replay. The browser does not run the tracker or authenticate the producer. A match does not establish a person’s identity or tracking accuracy.</p>
    <ol className="mt-5 space-y-4">{e.stages.map(stage => <li key={stage.stage} className="rounded-2xl border border-slate-200 bg-white p-4 sm:p-5">
      <h5 className="font-semibold">{stageLabels[stage.stage]}</h5><p className="mt-2 text-xs text-muted-foreground">{stage.track_count} track inputs · {stage.detection_count} detection inputs</p>
      {stage.pair ? <PairFacts pair={stage.pair} /> : <><p className="mt-3 font-semibold text-slate-700">Pair not offered in this stage</p><p className="mt-2 text-sm leading-6">Track {stage.track_offered ? "was" : "was not"} offered; detection {stage.detection_offered ? "was" : "was not"} offered. No gate result exists for this pair here. Score admission, track state and earlier assignments determine stage inputs.</p></>}
    </li>)}</ol>
    <details className="mt-4 rounded-xl border border-slate-200 bg-white p-4"><summary className="cursor-pointer text-sm font-semibold">Explanation provenance and limitations</summary><p className="mt-3 text-xs leading-6 text-muted-foreground">The producer declares exact saved-output replay parity. Source fingerprints are declared, not authenticated. The report and trace can have been exported by an older producer; the saved run, settings, source, output and selected detection must agree.</p><dl className="mt-3 space-y-3 text-xs">{[["Explanation", e.explanation_id], ["Run", e.run_id], ["Public output", e.track_sha256]].map(([label, value]) => <div key={label}><dt className="font-semibold">{label}</dt><dd className="mt-1 break-all font-mono">{value}</dd></div>)}</dl><p className="mt-3 text-xs">Producer: VisionTrack {e.producer.visiontrack} · Python {e.producer.python} · NumPy {e.producer.numpy}</p><ul className="mt-3 list-disc space-y-2 pl-5 text-xs leading-5">{e.limits.map(limit => <li key={limit}>{limit}</li>)}</ul></details>
  </div>
}

function AssociationImport({ report, trace, selection }: { report: ReliabilityReport; trace: InitiationTrace; selection: AssociationSelection }) {
  const [state, setState] = useState<AssociationLoadResult | { kind: "idle" | "loading" }>({ kind: "idle" })
  const reader = useRef(new AssociationFileReader())
  useEffect(() => { const current = reader.current; return () => current.cancel() }, [])
  const select = async (event: ChangeEvent<HTMLInputElement>) => {
    const input = event.currentTarget, file = input.files?.[0]
    input.value = ""
    if (!file) return
    setState({ kind: "loading" })
    const result = await reader.current.read(file, report, trace, selection)
    if (result) setState(result)
  }
  return <div className="mt-5">
    <p className="text-sm leading-6 text-muted-foreground">From a current local source checkout, export this exact pair from the original bundle. This command is newer than the published 0.4.0 package. Save to a new file outside the sealed bundle, then select that file below.</p>
    <pre className="mt-3 overflow-x-auto rounded-xl bg-slate-950 p-4 text-xs leading-6 text-slate-100"><code>{associationCommand(trace.variant, selection)}</code></pre>
    <p className="mt-3 text-xs leading-6 text-muted-foreground">Replace BUNDLE_PATH with your local saved experiment folder. The command replays the full saved run read-only; it does not use a camera or footage.</p>
    <div className="mt-4 flex flex-wrap gap-3"><label className={`${control} cursor-pointer focus-within:ring-2 focus-within:ring-indigo-600`}>Import association explanation<input className="sr-only" type="file" accept="application/json,.json" onChange={select} /></label>{state.kind !== "idle" && <button type="button" className={control} onClick={() => { reader.current.cancel(); setState({ kind: "idle" }) }}>Clear explanation</button>}</div>
    <div role="status" aria-live="polite" className="mt-4 text-sm">{state.kind === "loading" && <p>Checking the fingerprint, run and selected pair…</p>}{state.kind === "error" && <p className="rounded-xl bg-amber-50 p-4 text-amber-900"><strong>Explanation rejected:</strong> {state.message}</p>}{state.kind === "ready" && <p className="text-emerald-700">Explanation ready for frame {selection.frame}, ID {selection.trackId}, detection {selection.detectionIndex}.</p>}</div>
    {state.kind === "ready" && <AssociationExplanationView explanation={state.explanation} />}
  </div>
}

export function AssociationPairSelector({ report, trace, frame }: { report: ReliabilityReport; trace: InitiationTrace; frame: InitiationFrame }) {
  const tracks = availableAssociationTracks(frame)
  const [trackId, setTrackId] = useState(tracks[0]?.track_id ?? 0)
  const [detectionIndex, setDetectionIndex] = useState(frame.detections[0]?.detection_index ?? -1)
  if (!tracks.length || !frame.detections.length) return <p className="mt-4 text-sm leading-6">This frame has no pre-existing track/detection pair to inspect. Newly born tracks did not exist before association. Choose another frame in the timeline above.</p>
  const selection = { frame: frame.frame_index, trackId, detectionIndex }
  return <><div className="mt-5 grid gap-4 sm:grid-cols-2"><label className="text-sm font-semibold">Track ID before association<select value={trackId} onChange={e => setTrackId(Number(e.target.value))} className="mt-2 block min-h-11 w-full rounded-xl border border-slate-300 bg-white p-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-600">{tracks.map(t => <option key={t.track_id} value={t.track_id}>ID {t.track_id} · previously {t.previous_state}</option>)}</select></label><label className="text-sm font-semibold">Original detection key<select value={detectionIndex} onChange={e => setDetectionIndex(Number(e.target.value))} className="mt-2 block min-h-11 w-full rounded-xl border border-slate-300 bg-white p-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-600">{frame.detections.map(d => <option key={d.detection_index} value={d.detection_index}>Detection {d.detection_index} · score {d.score}</option>)}</select></label></div><AssociationImport key={`${trackId}:${detectionIndex}`} report={report} trace={trace} selection={selection} /></>
}

export default function AssociationInspector({ report, trace, frame }: { report: ReliabilityReport; trace: InitiationTrace; frame: InitiationFrame }) {
  const [open, setOpen] = useState(false)
  return <aside className="mt-5 rounded-2xl border border-indigo-200 bg-indigo-50/40 p-4 sm:p-5" aria-label="Optional pair association diagnosis"><button type="button" className={control} aria-expanded={open} onClick={() => setOpen(value => !value)}>{open ? "Close pair diagnosis" : "Why did this pair match or fail?"}</button><p className="mt-3 text-sm leading-6 text-muted-foreground">Optional: inspect one track and detection at frame {frame.frame_index}. An unmatched detection alone cannot tell you which gate failed. Imports stay in this tab’s memory; nothing is uploaded.</p>{open && <AssociationPairSelector report={report} trace={trace} frame={frame} />}</aside>
}
