import { useState } from "react"

export const lessonSteps = [
  { label: "Before the pillar", expected: "The visible person has tracking ID 7.", observed: "The tracker shows ID 7. So far, it agrees.", x: 70 },
  { label: "Behind the pillar", expected: "The person is hidden. There is no visible person to draw a box around.", observed: "No visible box here does not, by itself, prove a tracking mistake.", x: 160 },
  { label: "Back in view", expected: "In this teaching example, we know it is the same person. We want ID 7 to continue.", observed: "The tracker now shows ID 12 for that same person. This illustrates an ID switch.", x: 255 },
] as const

function Scene({ step, expected }: { step: number; expected: boolean }) {
  const hidden = step === 1
  const id = !expected && step === 2 ? 12 : 7
  const x = lessonSteps[step].x
  return (
    <svg viewBox="0 0 330 180" className="mt-4 w-full rounded-xl bg-slate-50" aria-hidden="true" focusable="false">
      <path d="M20 151H310" stroke="#cbd5e1" strokeWidth="2" />
      <rect x="130" y="35" width="65" height="116" rx="4" fill="#cbd5e1" />
      <text x="162" y="171" textAnchor="middle" fontSize="12" fill="#475569">Pillar</text>
      {!hidden && <g>
        <circle cx={x} cy="75" r="12" fill="#334155" />
        <path d={`M${x} 89v32m-17-21 17-10 17 10m-17 21-13 26m13-26 13 26`} fill="none" stroke="#334155" strokeWidth="6" strokeLinecap="round" />
        <rect x={x - 28} y="56" width="56" height="94" rx="5" fill="none" stroke={expected ? "#047857" : "#4f46e5"} strokeWidth="2" />
        <text x={x} y="43" textAnchor="middle" fontSize="14" fontWeight="600" fill={expected ? "#047857" : "#4338ca"}>ID {id}</text>
      </g>}
      {hidden && <text x="162" y="97" textAnchor="middle" fontSize="12" fill="#334155">Hidden</text>}
    </svg>
  )
}

export function TrackingLesson({ step }: { step: number }) {
  const current = lessonSteps[step]
  return (
    <div id="tracking-lesson-panel" role="region" aria-label={current.label} aria-live="polite" className="mt-5">
      <div className="grid gap-4 md:grid-cols-2">
        <article className="rounded-2xl border border-emerald-200 bg-white p-5">
          <h3 className="font-semibold text-emerald-800">What we expect</h3>
          <Scene step={step} expected />
          <p className="mt-3 text-sm leading-6 text-slate-700">{current.expected}</p>
        </article>
        <article className="rounded-2xl border border-indigo-200 bg-white p-5">
          <h3 className="font-semibold text-indigo-800">What the example tracker does</h3>
          <Scene step={step} expected={false} />
          <p className="mt-3 text-sm leading-6 text-slate-700">{current.observed}</p>
        </article>
      </div>
      <p className="mt-4 text-xs leading-5 text-slate-600">Illustration only—not footage, a result from your report, or a claim that VisionTrack can recognize people. Tracking IDs are temporary labels, not personal identities. Real evaluation needs independently reviewed reference labels.</p>
    </div>
  )
}

export default function LabGuide() {
  const [step, setStep] = useState(0)
  return (
    <details open className="mb-6 rounded-3xl border border-indigo-100 bg-white p-5 shadow-sm sm:p-7">
      <summary className="cursor-pointer text-xl font-semibold tracking-tight">New here? Start with one simple example.</summary>
      <div className="mt-5 max-w-3xl text-sm leading-7 text-slate-700">
        <p>The Lab helps us test a tracker before trusting a change. It opens saved experiment results; it does not start your webcam or fix the tracker.</p>
        <p className="mt-2">We compare <strong>what should happen</strong> (reference labels, also called ground truth) with <strong>what the tracker outputs</strong>. A variant is one tracker version or settings choice. A frame is one picture in a sequence.</p>
      </div>
      <p className="mt-6 text-xs font-semibold uppercase tracking-wide text-indigo-700">Teaching example · separate from the report below</p>
      <p className="mt-2 text-sm leading-6 text-slate-700">A person walks behind a pillar and comes back. Click each step to see what an ID switch means.</p>
      <div className="mt-4 flex flex-wrap gap-2" role="group" aria-label="Teaching example steps">
        {lessonSteps.map((item, index) => <button key={item.label} type="button" aria-pressed={step === index} aria-controls="tracking-lesson-panel" onClick={() => setStep(index)} className={`rounded-xl border px-4 py-3 text-sm font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-600 focus-visible:ring-offset-2 ${step === index ? "border-indigo-600 bg-indigo-600 text-white" : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50"}`}>{index + 1}. {item.label}</button>)}
      </div>
      <TrackingLesson step={step} />
      <ol className="mt-6 grid gap-4 border-t border-slate-200 pt-6 text-sm leading-6 md:grid-cols-3">
        <li><strong className="block text-slate-900">1. Open a report</strong>Explore the sample below, or import a prepared report.json. No installation is needed to explore the sample.</li>
        <li><strong className="block text-slate-900">2. Understand one mistake</strong>In “Explore tracking mistakes,” choose Inspect. Read the explanation first; technical details are optional.</li>
        <li><strong className="block text-slate-900">3. Review only when ready</strong>A researcher can record a choice after reviewing evidence against agreed criteria. You do not need to make a decision to explore.</li>
      </ol>
      <p className="mt-5 rounded-xl bg-indigo-50 p-4 text-sm leading-6 text-indigo-950">Your first task: explore one mistake and tell us what is unclear. It is fine to stop there. Missing images mean you may not have enough evidence to explain the cause.</p>
      <a href="#lab-title" className="mt-5 inline-block rounded-lg font-semibold text-primary underline underline-offset-4 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-600">Explore the report below ↓</a>
    </details>
  )
}
