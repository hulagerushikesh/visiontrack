import { useEffect, useRef, useState } from "react"
import { AssociationDemoReader, type AssociationDemo } from "./association-demo"
import { AssociationExplanationView } from "./AssociationInspector"
import { InitiationFrameView } from "./InitiationInspector"

const control = "inline-flex min-h-11 items-center justify-center rounded-xl border border-indigo-200 bg-white px-4 py-2 text-sm font-semibold text-indigo-700 shadow-sm hover:bg-indigo-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-600 disabled:cursor-not-allowed disabled:opacity-50"

export function AssociationLessonStep({ demo, step }: { demo: AssociationDemo; step: number }) {
  const p = demo.explanation.stages[2].pair!
  const lessons = [
    { title: "1. The boxes overlap, so why no match?", text: "At frame 0, detection 7 started tentative ID 1. At frame 1, the next detection is only one pixel to the right. Overlap and object class both pass their tests. That makes the pair a candidate, but overlap is only one test.", fact: `Overlap ${p.iou} ≥ ${p.minimum_iou} required · Passed` },
    { title: "2. The motion test rejects this pair", text: "This deliberately strict example uses a very small Kalman noise scale (0.001). The filter expects very little variation, so even this small shift is too large relative to its predicted uncertainty. The number below is a squared, uncertainty-normalized distance; it is not a distance in pixels.", fact: `Motion distance ${p.mahalanobis_squared} > ${p.mahalanobis_limit} allowed · Failed` },
    { title: "3. A new internal ID appears", text: "The saved timeline shows tentative ID 1 deleted without confirmation. The unmatched high-score detection starts tentative ID 2. Neither ID has a public box at this frame. Two internal IDs do not mean two people were identified.", fact: `Frame ${demo.trace.frames[0].frame_index} · ID 1 deleted · ID 2 tentative · ${demo.trace.frames[0].public_track_ids.length} public tracks` },
  ]
  const lesson = lessons[step]
  return <div className="mt-5 rounded-2xl border border-indigo-100 bg-white p-5" role="status" aria-live="polite" aria-atomic="true">
    <p className="text-xs font-semibold uppercase tracking-wide text-indigo-700">Match failure · Step {step + 1} of 3</p>
    <h3 className="mt-3 text-xl font-semibold">{lesson.title}</h3>
    <p className="mt-3 max-w-3xl text-sm leading-7 text-slate-700">{lesson.text}</p>
    <p className="mt-4 break-words rounded-xl bg-indigo-50 p-4 text-sm font-semibold leading-7 text-indigo-950">{lesson.fact}</p>
    {step === 2 && <p className="mt-4 text-sm leading-7 text-slate-700">You can finish here. This explains a saved software decision, not a verified real-world identity failure. It does not show that disabling the motion test or changing a threshold would improve tracking. No Human review decision is required.</p>}
  </div>
}

export function AssociationLessonContent({ demo }: { demo: AssociationDemo }) {
  const [step, setStep] = useState(0)
  return <>
    <p className="mt-5 text-sm font-semibold text-emerald-700">Prepared report, timeline and explanation checked together</p>
    <AssociationLessonStep demo={demo} step={step} />
    <nav aria-label="Match failure lesson steps" className="mt-4 flex flex-wrap items-center gap-3">
      <button type="button" className={control} disabled={step === 0} onClick={() => setStep(value => value - 1)}>Previous step</button>
      <span className="text-sm text-muted-foreground">Step {step + 1} of 3</span>
      <button type="button" className={control} disabled={step === 2} onClick={() => setStep(value => value + 1)}>Next step</button>
    </nav>
    <details className="mt-5 rounded-2xl border border-indigo-100 bg-white p-5"><summary className="cursor-pointer font-semibold">Optional: inspect the saved numbers and timeline</summary><p className="mt-3 text-sm leading-7 text-muted-foreground">This is the fixed synthetic “kalman” test case, exported from source-checkout tooling after public package 0.4.0. No footage or personal data is included. The browser checks content and lineage; it does not run Python or authenticate the producer. These records belong to this lesson, separate from your selected Lab report.</p><AssociationExplanationView explanation={demo.explanation} /><InitiationFrameView frame={demo.trace.frames[0]} /></details>
  </>
}

export default function AssociationLesson() {
  const [state, setState] = useState<{ kind: "closed" | "loading" } | { kind: "error"; message: string } | { kind: "ready"; demo: AssociationDemo }>({ kind: "closed" })
  const reader = useRef(new AssociationDemoReader())
  useEffect(() => { const current = reader.current; return () => current.cancel() }, [])
  const open = async () => {
    setState({ kind: "loading" })
    const result = await reader.current.read(() => import("./association-demo-assets"))
    if (result) setState(result)
  }
  const expanded = state.kind !== "closed"
  return <section className="mb-6 rounded-3xl border border-indigo-100 bg-indigo-50/60 p-5 sm:p-6" aria-label="Optional prepared match failure lesson">
    <h2 className="text-lg font-semibold">Why can overlapping boxes fail to match?</h2>
    <p className="mt-2 max-w-3xl text-sm leading-7 text-slate-700">An optional three-step synthetic lesson. See the saved overlap test, motion rejection and new internal ID. No install, files or camera needed; this does not change your selected report or show real-world accuracy.</p>
    <div className="mt-4 flex flex-wrap gap-3"><button type="button" className={control} aria-expanded={expanded} aria-controls="association-lesson-content" disabled={state.kind === "loading"} onClick={open}>{state.kind === "loading" ? "Checking prepared lesson…" : state.kind === "closed" ? "Explain a match failure" : "Restart lesson"}</button>{expanded && <button type="button" className={control} onClick={() => { reader.current.cancel(); setState({ kind: "closed" }) }}>Close lesson</button>}</div>
    <div id="association-lesson-content">
      {state.kind === "loading" && <p role="status" className="mt-4 text-sm">Checking the three prepared records…</p>}
      {state.kind === "error" && <p role="alert" className="mt-4 rounded-xl bg-amber-50 p-4 text-sm text-amber-900">Lesson unavailable: {state.message} Your selected report is unchanged. You can retry or close this lesson.</p>}
      {state.kind === "ready" && <AssociationLessonContent demo={state.demo} />}
    </div>
  </section>
}
