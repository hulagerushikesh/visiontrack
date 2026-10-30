import { useState } from "react"
import rain from "./rain.json"

const evidenceUrl = "https://github.com/hulagerushikesh/visiontrack/blob/main/docs/HVSD_RAIN_REVIEW.md"
const stages = ["Detector", "Association", "Confirmation", "Counting"]
const notes: Record<number, { title: string; summary: string; stages: string[]; next: string }> = {
  27: {
    title: "A public track crosses the line",
    summary: "The saved counting rule emits one crossing between frames 27 and 28, next to the owner's mark at 27.",
    stages: ["Proposals are present on both sides of the line.", "Public ID 3 continues across the two frames. The tentative-only probe does not record its association calls.", "ID 3 is already confirmed, so it is included in the public output.", "The same public ID moves from left to right in consecutive frames and meets the line rule."],
    next: "Use this as a working example for comparison with the other four marks.",
  },
  37: {
    title: "A proposal gap spans the apparent crossing",
    summary: "Source inspection suggests a crossing around frames 36–39. A nearby proposal is recorded at 35, then again at 39, when tentative ID 4 begins beyond the line.",
    stages: ["The nearby proposal at x=478.9 in frame 35 is followed by a gap. A proposal at x=504.6 appears at 39. Other vehicles still have proposals in this window.", "The saved tentative probe records a successful match for ID 4 at frame 40. It does not establish the physical correspondence across the earlier gap.", "ID 4 starts after the line and is still tentative at frame 40. Continuing public ID 3 belongs to an earlier crossing candidate.", "No public crossing is emitted near this mark. Creating a track after the line cannot reconstruct an earlier crossing under this rule."],
    next: "Check detection availability around the passage before proposing an association or counting change.",
  },
  57: {
    title: "Detection alone does not guarantee a counted track",
    summary: "Proposals bracket the line at frames 57–58, but no public track spans that crossing. This is the clearest threshold lead in the saved evidence.",
    stages: ["Proposal centers move from x=494.8 to x=500.3. Their scores, 0.577 and 0.597, are below the baseline's 0.60 new-track threshold.", "The probe does not record a tentative match at frames 57–58. That alone cannot establish why every possible association was absent.", "Tentative ID 10 starts at frame 59, beyond the line. New tracks need three consecutive matches before entering the public output.", "The baseline emits no nearby crossing. The exploratory 0.55 threshold replay emits one at approximately frame 57.85, but its wider effects remain unvalidated."],
    next: "Evaluate the benefit and cost of earlier initiation on fresh controlled inputs, including misleading detections.",
  },
  92: {
    title: "No retained detector proposal near the line",
    summary: "The saved frames 88–96 contain no retained near-line road-class proposal or track. Source inspection suggests a visible crossing around 91–94.",
    stages: ["No retained near-line proposal is recorded by the pinned model and class filter in this window.", "The tentative probe has no candidate pairs here. A tracker needs observations to associate.", "No nearby internal or public track is recorded in this window.", "Neither replay emits a crossing near this mark. Lowering the new-track threshold did not supply the missing observation."],
    next: "Investigate the detector and filtering stages. This trace does not establish why the model failed to propose a box.",
  },
  160: {
    title: "Candidate matches fail the motion gate",
    summary: "Repeated proposals cross the line around frames 161–162 while tentative IDs change. A saved candidate pair passes overlap and class checks but fails the motion gate.",
    stages: ["Proposal centers move from x=493.9 at frame 161 to x=501.4 at frame 162.", "At frame 162, tentative ID 16 has overlap 0.5561, above the 0.3 minimum. Its motion distance 33.107 exceeds 9.4877, and the pair is rejected.", "Nearby tentative tracks start and expire without a public track spanning the crossing. The vehicle's visual class and exact box correspondence remain uncertain.", "Neither replay emits a nearby crossing. The earlier controlled gate-off experiment found safety regressions, so this pair does not justify disabling that gate."],
    next: "Test a specific motion-model hypothesis with safety controls; retain uncertainty about physical object correspondence.",
  },
}

type Frame = (typeof rain.cases)[number]["frames"][number]

export function StagePlot({ frame }: { frame: Frame }) {
  const lanes = [
    { name: "Proposals", color: "#4f46e5", points: frame.near_line_detections.map(d => ({ x: d.center_x, label: `${d.score}` })) },
    { name: "Internal tracks", color: "#b45309", points: frame.near_line_internal_tracks.map(t => ({ x: t.center_x, label: `ID ${t.track_id}` })) },
    { name: "Public outputs", color: "#047857", points: frame.near_line_public_tracks.map(t => ({ x: t.center_x, label: `ID ${t.track_id}` })) },
  ]
  const x = (center: number) => 160 + (center - 375) / 250 * 470
  return <figure className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
    <svg viewBox="0 0 680 225" className="w-full" role="img" aria-label={`Frame ${frame.frame}: horizontal centers of nearby proposals and tracks; dashed line at x=500`}>
      <line x1={x(500)} x2={x(500)} y1="15" y2="185" stroke="#94a3b8" strokeDasharray="5 5" />
      {lanes.map((lane, i) => <g key={lane.name}>
        <text x="0" y={50 + i * 60} fontSize="13" fill="#475569">{lane.name}</text>
        <line x1="160" x2="630" y1={47 + i * 60} y2={47 + i * 60} stroke="#cbd5e1" />
        {lane.points.map((p, index) => <g key={index}><circle cx={x(p.x)} cy={47 + i * 60} r="6" fill={lane.color}><title>{`${p.label}, center x=${p.x}`}</title></circle><text x={x(p.x)} y={32 + i * 60} textAnchor="middle" fontSize="11" fill={lane.color}>{p.label}</text></g>)}
        {lane.points.length === 0 && <text x="170" y={36 + i * 60} fontSize="12" fill="#64748b">None recorded nearby</text>}
      </g>)}
      {[375, 500, 625].map(value => <text key={value} x={x(value)} y="213" textAnchor="middle" fontSize="12" fill="#475569">{value === 500 ? "Counting line · x=500" : `x=${value}`}</text>)}
    </svg>
    <figcaption className="text-xs leading-5 text-muted-foreground">Numeric schematic of saved horizontal positions, not video or object matches. Nearby rows may represent different vehicles. Internal positions include predicted tracks; public outputs are shown separately.</figcaption>
  </figure>
}

export function CaseExplanation({ mark, stage }: { mark: number; stage: number }) {
  const note = notes[mark]
  return <div id="crossing-stage" role="region" aria-label={`${stages[stage]} explanation`} aria-live="polite" className="mt-4 rounded-2xl bg-indigo-50 p-5 text-sm leading-7 text-indigo-950">
    <h3 className="font-semibold">{stages[stage]}: what the saved evidence tells us</h3>
    <p className="mt-1">{note.stages[stage]}</p>
  </div>
}

export default function CrossingDiagnosis() {
  const [mark, setMark] = useState(57)
  const [offset, setOffset] = useState(4)
  const [stage, setStage] = useState(0)
  const selected = rain.cases.find(c => c.mark_frame === mark)!
  const frame = selected.frames[offset]
  const note = notes[mark]
  const pairs = selected.association_pairs.filter(p => p.frame === frame.frame)
  const control = "rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm font-medium transition hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-600 disabled:opacity-40"
  return <div className="mx-auto max-w-7xl px-5 pb-24 pt-32 lg:px-8">
    <a href="/lab" className="text-sm font-semibold text-primary underline underline-offset-4">← Back to Reliability Lab</a>
    <header className="mt-7 max-w-4xl">
      <p className="text-xs font-semibold uppercase tracking-widest text-primary">Crossing diagnosis · exploratory research</p>
      <h1 className="mt-4 text-4xl font-semibold tracking-tight sm:text-6xl">Why wasn't it counted?</h1>
      <p className="mt-5 text-lg leading-8 text-muted-foreground">Follow one saved observation through detection, association, confirmation and counting. A vehicle can be visible in the footage while one of these stages prevents a count.</p>
      <p className="mt-3 text-sm leading-6 text-slate-600">HVSD rain · 194 frames · YOLOX nano + ByteTrack. This separate case study uses saved numeric observations. It does not use your imported Lab report or run a new tracker.</p>
    </header>
    <div className="mt-8 grid gap-3 sm:grid-cols-3">
      {[[rain.cases.length, "owner crossing marks"], [rain.baseline.public_crossings.length, "baseline rule-defined crossing"], [rain.candidate.public_crossings.length, "exploratory candidate crossings"]].map(([value, label]) => <div key={label} className="rounded-2xl border border-indigo-100 bg-white p-5"><p className="text-3xl font-semibold text-primary">{value}</p><p className="mt-1 text-sm text-muted-foreground">{label}</p></div>)}
    </div>
    <p className="mt-3 text-sm leading-6 text-slate-600">These are observed counts, not accuracy percentages. Owner marks are sparse event references; physical identity and complete false-positive coverage are unverified.</p>

    <section className="mt-10 rounded-3xl border border-indigo-100 bg-white p-5 shadow-sm sm:p-8" aria-labelledby="choose-crossing">
      <h2 id="choose-crossing" className="text-xl font-semibold">1. Choose a crossing mark</h2>
      <p className="mt-2 text-sm leading-6 text-muted-foreground">Frame numbers start at 0. A mark is the owner's approximate crossing time, not an exact tracker match.</p>
      <div role="group" aria-label="Crossing marks" className="mt-4 flex flex-wrap gap-2">{rain.cases.map(c => <button key={c.mark_frame} type="button" className={`${control} ${mark === c.mark_frame ? "border-indigo-600 bg-indigo-50 text-indigo-700" : ""}`} aria-pressed={mark === c.mark_frame} aria-controls="crossing-details" onClick={() => { setMark(c.mark_frame); setOffset(4) }}>Frame {c.mark_frame}</button>)}</div>
      <div id="crossing-details" className="mt-6" aria-live="polite">
        <h3 className="text-2xl font-semibold tracking-tight">{note.title}</h3>
        <p className="mt-3 max-w-4xl text-sm leading-7 text-slate-700">{note.summary}</p>
        <p className="mt-3 text-sm font-medium text-slate-800">Within ±4 frames of this mark: {selected.baseline_crossings.length} baseline event · {selected.candidate_crossings.length} exploratory candidate event</p>
      </div>

      <h2 className="mt-8 border-t border-slate-200 pt-7 text-xl font-semibold">2. Follow the four stages</h2>
      <div className="mt-4 grid grid-cols-2 gap-2 lg:grid-cols-4" role="group" aria-label="Pipeline stages">{stages.map((name, index) => <button key={name} className={`${control} text-left ${stage === index ? "border-indigo-600 bg-indigo-50 text-indigo-700" : ""}`} type="button" aria-pressed={stage === index} aria-controls="crossing-stage" onClick={() => setStage(index)}>{index + 1}. {name}</button>)}</div>
      <CaseExplanation mark={mark} stage={stage} />

      <h2 className="mt-8 border-t border-slate-200 pt-7 text-xl font-semibold">3. Inspect the saved frame observations</h2>
      <p className="mt-2 text-sm leading-6 text-muted-foreground">Baseline only. Explore the nine recorded frames around this mark. Association rows cover tentative-track candidates only; an empty list does not mean all matching failed.</p>
      <div className="my-5 flex flex-wrap items-center gap-3">
        <button type="button" className={control} disabled={offset === 0} onClick={() => setOffset(offset - 1)}>← Previous frame</button>
        <label className="text-sm font-semibold">Frame <select aria-label="Saved frame" value={offset} onChange={e => setOffset(Number(e.target.value))} className="ml-2 rounded-lg border border-slate-200 bg-white px-3 py-2">{selected.frames.map((f, index) => <option key={f.frame} value={index}>{f.frame}{f.frame === mark ? " (owner mark)" : ""}</option>)}</select></label>
        <button type="button" className={control} disabled={offset === selected.frames.length - 1} onClick={() => setOffset(offset + 1)}>Next frame →</button>
      </div>
      <StagePlot frame={frame} />
      <details className="mt-5 rounded-2xl border border-slate-200 p-4">
        <summary className="cursor-pointer text-sm font-semibold">Exact frame data and tentative association checks</summary>
        <p className="mt-3 text-sm leading-6 text-muted-foreground">Scores describe detector confidence, not tracking accuracy. A tentative track is provisional; confirmed public output is what the counter uses.</p>
        <pre className="mt-3 max-h-96 overflow-auto rounded-xl bg-slate-50 p-4 text-xs leading-6">{JSON.stringify({ ...frame, tentative_association_pairs: pairs }, null, 2)}</pre>
      </details>
      <div className="mt-6 rounded-2xl border border-slate-200 p-5"><h3 className="font-semibold">What should we investigate next?</h3><p className="mt-2 text-sm leading-7 text-muted-foreground">{note.next}</p></div>
    </section>

    <section className="mt-8 rounded-3xl border border-amber-200 bg-amber-50/70 p-6 sm:p-8" aria-labelledby="threshold-tradeoff">
      <h2 id="threshold-tradeoff" className="text-xl font-semibold">One extra crossing is a lead to test</h2>
      <p className="mt-3 max-w-4xl text-sm leading-7 text-slate-700">After inspecting the frame-57 gap, we replayed identical detections with only the new-track threshold changed from 0.60 to 0.55. This produced another nearby crossing. It also changed outputs elsewhere in the clip.</p>
      <div className="mt-5 overflow-x-auto"><table className="w-full text-left text-sm"><caption className="sr-only">Whole-clip exploratory threshold comparison</caption><thead><tr className="border-b border-amber-200"><th scope="col" className="py-3 pr-4">Saved observation</th><th scope="col" className="p-3">Baseline · 0.60</th><th scope="col" className="p-3">Candidate · 0.55</th></tr></thead><tbody>{([
        ["Rule-defined crossings", rain.baseline.public_crossings.length, rain.candidate.public_crossings.length],
        ["Public track boxes", rain.baseline.public_track_boxes, rain.candidate.public_track_boxes],
        ["Unique public IDs", rain.baseline.unique_public_track_ids, rain.candidate.unique_public_track_ids],
        ["Tentative births", rain.baseline.tentative_births, rain.candidate.tentative_births],
      ]).map(([label, baseline, candidate]) => <tr key={label} className="border-b border-amber-100"><th scope="row" className="py-3 pr-4 font-medium">{label}</th><td className="p-3">{baseline}</td><td className="p-3">{candidate}</td></tr>)}</tbody></table></div>
      <p className="mt-5 text-sm font-semibold leading-7 text-amber-950">The candidate was chosen after seeing this clip. These results cannot establish accuracy or justify a default change. Fresh evaluation must examine misleading detections and changes elsewhere as well as recovered crossings.</p>
    </section>

    <details className="mt-8 rounded-2xl border border-slate-200 bg-white p-5">
      <summary className="cursor-pointer font-semibold">Evidence source, scope and reproduction</summary>
      <p className="mt-4 text-sm leading-7 text-muted-foreground">This page contains a generated projection of three pinned research records, with no footage, model weights or participant contact information. Numeric observations are recorded evidence; the written stage explanations are interpretations. The owner attested a full 194-frame review. Dense reference boxes and identities are unavailable.</p>
      <p className="mt-3 text-sm leading-7 text-muted-foreground">Nearby means centers within 125 pixels of x=500 and y ≥ 205. Counting additionally requires y ≤ 432, the same public ID and consecutive frames. The plot's internal-track positions may include predictions. The saved receipt checks consistency with the original run; it does not verify physical identity or accuracy.</p>
      <a href={evidenceUrl} className="mt-4 inline-block text-sm font-semibold text-primary underline underline-offset-4">Read the full diagnosis and reproduction commands →</a>
      <pre className="mt-4 overflow-auto rounded-xl bg-slate-50 p-4 text-xs leading-6">{JSON.stringify({ schema: rain.schema, source_record_sha256: rain.source_record_sha256, source_video_sha256: rain.source_video_sha256, model_sha256: rain.model_sha256, baseline_receipt: rain.baseline_receipt }, null, 2)}</pre>
    </details>
  </div>
}
