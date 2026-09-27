import { useEffect, useState, type ReactNode } from "react"
import { ArrowRight, BookOpen, CheckCircle2, FlaskConical, Link2, Minus, TrendingDown } from "lucide-react"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

const sections = [
  ["setup", "The setup"],
  ["appearance", "RQ1 · Appearance"],
  ["motion", "RQ2 · Learned motion"],
  ["uncertainty", "RQ3 · Uncertainty"],
  ["takeaway", "Why negatives matter"],
] as const

function SectionHeading({ id, label, children }: { id: string; label?: string; children: ReactNode }) {
  return <h2 id={id} className="group scroll-mt-28 text-balance text-3xl font-semibold leading-tight tracking-[-.035em] text-slate-950 sm:text-4xl">
    {label && <span className="mb-3 block font-mono text-xs font-semibold uppercase tracking-[.16em] text-indigo-600">{label}</span>}
    {children}<a href={`#${id}`} aria-label={`Link to ${String(children)}`} className="ml-2 inline-flex align-middle text-slate-300 opacity-0 transition hover:text-indigo-600 group-hover:opacity-100 focus:opacity-100"><Link2 className="size-4" /></a>
  </h2>
}

function Callout({ label, negative = false, children }: { label: string; negative?: boolean; children: ReactNode }) {
  return <aside className={cn("my-10 rounded-3xl border p-6 sm:p-8", negative ? "border-amber-200 bg-amber-50/80" : "border-indigo-200 bg-indigo-50/75")}>
    <div className={cn("flex items-center gap-2 font-mono text-[11px] font-semibold uppercase tracking-[.16em]", negative ? "text-amber-700" : "text-indigo-700")}>
      {negative ? <TrendingDown className="size-4" /> : <CheckCircle2 className="size-4" />}{label}
    </div>
    <div className="mt-4 text-[1.03rem] leading-8 text-slate-700">{children}</div>
  </aside>
}

function ResearchTable({ children, label }: { children: ReactNode; label: string }) {
  return <div className="my-9 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm" role="region" aria-label={label} tabIndex={0}>
    <div className="overflow-x-auto"><table className="w-full min-w-[620px] border-collapse text-left text-sm">{children}</table></div>
  </div>
}

const Th = ({ children, right = false }: { children: ReactNode; right?: boolean }) => <th className={cn("border-b border-slate-200 bg-slate-50 px-5 py-4 font-semibold text-slate-700", right && "text-right")}>{children}</th>
const Td = ({ children, right = false, good = false, warn = false }: { children: ReactNode; right?: boolean; good?: boolean; warn?: boolean }) => <td className={cn("border-b border-slate-100 px-5 py-4 text-slate-700 last:border-b-0", right && "text-right font-mono text-xs", good && "font-semibold text-emerald-700", warn && "font-semibold text-amber-700")}>{children}</td>

function Figure({ src, alt, caption, width, height }: { src: string; alt: string; caption: string; width: number; height: number }) {
  return <figure className="my-11 overflow-hidden rounded-3xl border border-slate-200 bg-white p-3 shadow-[0_24px_70px_-45px_rgba(30,41,59,.5)] sm:p-5">
    <img src={src} alt={alt} loading="lazy" width={width} height={height} className="h-auto w-full rounded-2xl" />
    <figcaption className="px-2 pb-1 pt-4 text-center text-sm leading-6 text-slate-500">{caption}</figcaption>
  </figure>
}

function ReadingProgress() {
  const [progress, setProgress] = useState(0)
  useEffect(() => {
    const update = () => {
      const article = document.getElementById("research-article")
      if (!article) return
      const start = article.offsetTop
      const distance = Math.max(article.offsetHeight - window.innerHeight, 1)
      setProgress(Math.min(100, Math.max(0, ((window.scrollY - start) / distance) * 100)))
    }
    update()
    window.addEventListener("scroll", update, { passive: true })
    window.addEventListener("resize", update)
    return () => { window.removeEventListener("scroll", update); window.removeEventListener("resize", update) }
  }, [])
  return <div className="fixed inset-x-0 top-0 z-[60] h-1 bg-transparent" aria-hidden="true"><div className="h-full bg-gradient-to-r from-indigo-600 via-sky-500 to-emerald-500 transition-[width] duration-100" style={{ width: `${progress}%` }} /></div>
}

function Contents() {
  const [active, setActive] = useState("setup")
  useEffect(() => {
    const observer = new IntersectionObserver(entries => {
      const visible = entries.filter(entry => entry.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)
      if (visible[0]) setActive(visible[0].target.id)
    }, { rootMargin: "-20% 0px -68% 0px" })
    sections.forEach(([id]) => { const node = document.getElementById(id); if (node) observer.observe(node) })
    return () => observer.disconnect()
  }, [])
  return <aside className="hidden xl:block"><div className="sticky top-28 rounded-2xl border border-slate-200 bg-white/80 p-5 shadow-sm backdrop-blur">
    <p className="font-mono text-[10px] font-semibold uppercase tracking-[.16em] text-slate-400">In this article</p>
    <nav aria-label="Article sections" className="mt-4 grid gap-1">{sections.map(([id, label], index) => <a key={id} href={`#${id}`} className={cn("flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition", active === id ? "bg-indigo-50 font-semibold text-indigo-700" : "text-slate-500 hover:bg-slate-50 hover:text-slate-900")}><span className="font-mono text-[10px] text-slate-400">0{index + 1}</span>{label}</a>)}</nav>
    <div className="mt-5 border-t border-slate-100 pt-5"><a href="/benchmark/explorer" className="flex items-center gap-2 text-sm font-semibold text-indigo-600 hover:text-indigo-800">Inspect the evidence <ArrowRight className="size-4" /></a></div>
  </div></aside>
}

export default function ResearchWriteup() {
  useEffect(() => {
    const oldTitle = document.title
    const description = document.querySelector<HTMLMetaElement>('meta[name="description"]')
    const oldDescription = description?.content
    const canonical = document.querySelector<HTMLLinkElement>('link[rel="canonical"]')
    const oldCanonical = canonical?.href
    document.title = "A better trick that makes a worse tracker — VisionTrack"
    if (description) description.content = "A controlled VisionTrack study of when appearance, learned motion, and calibrated uncertainty actually help multi-object tracking."
    if (canonical) canonical.href = "https://visiontrack.hulage.in/writeup"
    return () => { document.title = oldTitle; if (description && oldDescription) description.content = oldDescription; if (canonical && oldCanonical) canonical.href = oldCanonical }
  }, [])

  return <>
    <ReadingProgress />
    <header className="relative overflow-hidden border-b border-indigo-100 bg-gradient-to-br from-indigo-50 via-white to-cyan-50 px-5 pb-20 pt-32 lg:pb-24 lg:pt-40">
      <div className="soft-grid absolute inset-0 opacity-70" />
      <div className="orb -left-56 -top-56 bg-indigo-300/35" /><div className="orb -right-48 top-4 bg-cyan-200/45" />
      <div className="relative mx-auto max-w-5xl">
        <div className="flex flex-wrap items-center gap-3 font-mono text-[10px] font-semibold uppercase tracking-[.16em] text-indigo-600"><span className="rounded-full border border-indigo-100 bg-white/75 px-3 py-1.5">Research write-up</span><span>Controlled study</span><span>·</span><span>11 min read</span></div>
        <h1 className="mt-8 max-w-4xl text-balance text-5xl font-semibold leading-[1.02] tracking-[-.055em] text-slate-950 sm:text-7xl">A better trick that makes a <span className="gradient-text">worse tracker.</span></h1>
        <p className="mt-8 max-w-3xl text-pretty text-xl leading-9 text-slate-600">I built a multi-object tracker from first principles on NumPy—no ML framework in the core—and used it as a lab bench to ask: <strong className="font-semibold text-slate-900">when do the field’s standard tricks actually help?</strong></p>
        <div className="mt-9 flex flex-wrap items-center gap-x-6 gap-y-3 text-sm text-slate-500"><span className="flex items-center gap-2"><FlaskConical className="size-4 text-indigo-500" />Frozen baselines</span><span className="flex items-center gap-2"><CheckCircle2 className="size-4 text-emerald-500" />Paired significance</span><span className="flex items-center gap-2"><BookOpen className="size-4 text-sky-500" />Honest negatives</span></div>
      </div>
    </header>

    <div className="mx-auto grid max-w-7xl gap-12 px-5 py-16 lg:px-8 xl:grid-cols-[220px_minmax(0,760px)_1fr] xl:py-20">
      <Contents />
      <article id="research-article" className="research-article min-w-0 text-[1.05rem] leading-8 text-slate-700">
        <section aria-labelledby="setup">
          <SectionHeading id="setup">The setup, and why it’s built the hard way</SectionHeading>
          <p>Most tracking repositories are a thin wrapper: someone else’s detector, someone else’s vendored tracker, and a single reported number for a single configuration. You can’t ask a counterfactual of a black box. So I inverted the priority—the estimation and association math <em>is</em> the deliverable, and it exists to be ablated.</p>
          <p>The core is three pieces, each written from scratch and independently tested: an <strong>8-state constant-velocity Kalman filter</strong> (DeepSORT’s <code>xyah</code> parametrization, Joseph-form covariance update, Mahalanobis gating), a rectangular <strong>O(n³) Hungarian solver</strong> (validated against SciPy on 150 random matrices), and <strong>ByteTrack</strong> two-stage association over a <code>Tentative → Confirmed → Deleted</code> lifecycle. No <code>torch</code>, no <code>scipy</code> in the hot path—just NumPy.</p>
          <p>The trick that makes the whole study possible is one design choice in the association cost. It’s <em>factored</em>: a hard gate (IoU + class + Mahalanobis) decides which detection–track pairs are even <em>feasible</em>, and then each hypothesis is a single weighted term that only <em>ranks</em> the feasible pairs.</p>
          <blockquote className="my-9 overflow-x-auto rounded-2xl border-l-4 border-indigo-500 bg-slate-950 px-6 py-7 font-mono text-sm leading-7 text-white shadow-xl shadow-slate-950/10">cost = w_iou·motion ⊕ w_app·appearance ⊕ w_unc·uncertainty</blockquote>
          <p>At <code>w_app = w_unc = 0</code> this is <strong>bit-identical</strong> to the plain <code>1 − IoU</code> baseline. So every experiment toggles exactly one variable against a frozen reference, over multiple seeds, compared with a paired bootstrap and a Wilcoxon test. The from-scratch HOTA/IDF1 metrics are cross-checked against the standard <code>trackeval</code> to within <code>1.4e-3</code>. That’s the moat: not speed, but <em>honest measurement</em>.</p>
        </section>

        <div className="my-16 flex items-center gap-4 text-slate-300"><Minus className="size-5" /><span className="h-px flex-1 bg-slate-200" /></div>
        <section aria-labelledby="appearance">
          <SectionHeading id="appearance" label="RQ1 · Appearance">The result I spent the longest trying to disprove</SectionHeading>
          <p>Appearance re-ID is the crowd favourite: give each track a visual descriptor, add its cosine distance to the cost, and identities should survive crossings and occlusions. On MOT17 it does help—but modestly. A cheap from-scratch colour histogram barely moves the needle; a pretrained <strong>deep re-ID</strong> model (OSNet-x0.25, run through ONNX behind the same interface) roughly doubles the gain and cuts ID switches from 188 to <strong>163 (−13%)</strong>.</p>
          <ResearchTable label="MOT17 FRCNN appearance results"><thead><tr><Th>MOT17 FRCNN · Δ vs motion-only</Th><Th right>HOTA</Th><Th right>IDF1</Th><Th right>AssA</Th><Th right>IDSW</Th></tr></thead><tbody><tr><Td>from-scratch colour histogram</Td><Td right>+0.001</Td><Td right>+0.002</Td><Td right>+0.003</Td><Td right>170 (−18)</Td></tr><tr><Td><strong>deep re-ID (OSNet)</strong></Td><Td right good>+0.004</Td><Td right good>+0.004</Td><Td right good>+0.008</Td><Td right good>163 (−25)</Td></tr></tbody></ResearchTable>
          <p>Pooling all three public detectors for statistical power (21 sequence×detector units), the ID-switch and IDF1 reductions become <strong>significant</strong> (p&lt;0.05). But there’s a twist that runs opposite to intuition: appearance is <strong>completely inert on the weakest detector (DPM)</strong>. Its mislocalized boxes produce mis-framed crops, so the embeddings carry no identity signal. <em>Crop quality gates whether appearance helps at all</em>—not the amount of association ambiguity, which is the thing everyone assumes it fixes.</p>
          <Figure src="/assets/appearance_mot17_stratified.png" alt="Stratified analysis of where deep re-ID appearance helps on MOT17" caption="Where deep re-ID earns its weight—pooled across three detectors." width={1650} height={473} />
          <h3 id="trying-to-hurt" className="scroll-mt-28 text-2xl font-semibold tracking-tight text-slate-950">Trying to make it hurt</h3>
          <p>The textbook warning is that appearance <em>hurts</em> when objects look alike—the DanceTrack case, a stage full of near-identical dancers. I went looking for that failure on purpose, four ways:</p>
          <p><strong>1. A synthetic probe.</strong> I added a controlled appearance channel to the scene generator with one knob from “identical dancers” to “distinct pedestrians,” holding geometry and noise fixed. The benefit <em>grew</em> with distinctness and was significant at every level—but it never flipped to harmful. Even for identical objects, unbiased embedding noise averages to a near-uniform cost: appearance goes <em>inert</em>, not misleading.</p>
          <p><strong>2. Descriptor drift.</strong> Maybe non-stationary appearance—a stale gallery confidently matching the wrong object—is the real hazard. I made each object’s descriptor random-walk over time. It <em>still</em> didn’t hurt; it helped <em>more</em>. The geometric reason is quietly beautiful: independent random walks in high dimensions are near-orthogonal, so drifting objects <em>diverge</em> in appearance space and become <em>more</em> distinguishable, not less.</p>
          <p><strong>3. Real DanceTrack.</strong> The decisive test. On 12 real DanceTrack sequences—near-identical dancers, wildly non-linear motion, motion-only AssA of just 0.214 so there is <em>ample</em> room to hurt—deep re-ID still <strong>significantly cut ID switches (217 → 202, p&lt;0.05)</strong>. The marquee hypothesis, refuted on its home turf.</p>
          <Callout label="The unifying result"><p>“Appearance hurts on DanceTrack” is a property of trackers that let appearance <em>veto</em> a match—override the motion model and commit to a look-alike. This tracker’s cost only lets appearance <strong>rank within the motion gate, never veto a feasible pair</strong>. Under that one design rule, a gated appearance cost is <strong>robustly beneficial-or-neutral</strong> across every regime I could build or download. Making it harmful takes <em>confident misidentification</em>, which is an architecture choice, not a property of similar-looking objects.</p></Callout>
        </section>

        <div className="my-16 flex items-center gap-4 text-slate-300"><Minus className="size-5" /><span className="h-px flex-1 bg-slate-200" /></div>
        <section aria-labelledby="motion">
          <SectionHeading id="motion" label="RQ2 · Learned motion">A better predictor, a worse tracker</SectionHeading>
          <p>Constant velocity is a crude motion model. So I trained a small MLP—from scratch in NumPy, hand-written back-propagation and Adam, no framework—to predict a <em>correction</em> to the Kalman mean from recent velocities. Open-loop, evaluated on ground-truth trajectories, it does exactly what theory predicts:</p>
          <ResearchTable label="Next-centre prediction error"><thead><tr><Th>next-centre error</Th><Th right>constant velocity</Th><Th right>+ residual</Th></tr></thead><tbody><tr><Td>MOT17 (near-linear)</Td><Td right>1.05 px</Td><Td right warn>1.27 (−21% worse)</Td></tr><tr><Td>DanceTrack (non-linear)</Td><Td right>6.89 px</Td><Td right good>6.03 (+12% better)</Td></tr></tbody></ResearchTable>
          <p>It helps precisely where motion is non-linear and can’t help where CV is already accurate to a pixel. A clean, sensible result—until you wire it into the tracker. Closed-loop, it <strong>hurts identity on both datasets</strong> (DanceTrack HOTA −0.043, +29 ID switches; MOT17 HOTA −0.013, +12).</p>
          <Callout label="Honest negative" negative><p>The residual was trained on clean ground-truth trajectories but is fed the tracker’s own <em>noisy</em> estimates at inference—a train/serve distribution shift—and its correction nudges the association gate just enough to create switches. A more accurate one-step predictor produced a less accurate tracker. The gate cares more about not moving than about being right.</p></Callout>
        </section>

        <div className="my-16 flex items-center gap-4 text-slate-300"><Minus className="size-5" /><span className="h-px flex-1 bg-slate-200" /></div>
        <section aria-labelledby="uncertainty">
          <SectionHeading id="uncertainty" label="RQ3 · Calibrated uncertainty">The loose gate is a feature, not a bug</SectionHeading>
          <p>The Kalman filter carries a full covariance; the principled move is to fold that uncertainty into the association cost and, while you’re at it, calibrate the filter’s noise to real motion. I measured the calibration first. Stepping the filter along real MOT17 ground truth, the innovation χ² comes out at <strong>0.15</strong> where a well-calibrated filter would give <strong>4.0</strong>—it is ~25× <em>under-confident</em>, and its 95% gate captures 100% of innovations and never rejects anything.</p>
          <Figure src="/assets/kalman_calibration.png" alt="Kalman filter innovation chi-square reliability curve on MOT17" caption="The filter is drastically under-confident—the gate almost never rejects." width={605} height={605} />
          <p>So I fixed it. Tightening the filter to be properly calibrated (<code>kf_noise_scale = 0.19</code>) was <strong>catastrophic under detector noise</strong>: HOTA −0.205 and <strong>ID switches 40 → 400+</strong>. A gate tuned to clean motion rejects noisy-but-correct detections, and tracks fragment.</p>
          <Callout label="Honest negative" negative><p>The apparent under-confidence is doing real work. In tracking-by-detection the inputs are noisy in ways the motion model never sees, so a <em>loose</em> gate that forgives that noise is more robust than a “correct” tight one. Folding uncertainty in as a soft cost was null; <em>calibrating</em> was actively harmful. This unifies with an earlier ablation where disabling the gate entirely barely changed clean-data results—the gate was never the thing doing the work.</p></Callout>
        </section>

        <div className="my-16 flex items-center gap-4 text-slate-300"><Minus className="size-5" /><span className="h-px flex-1 bg-slate-200" /></div>
        <section aria-labelledby="takeaway">
          <SectionHeading id="takeaway">Why the negatives are the point</SectionHeading>
          <p>Three enhancements the literature treats as obvious upgrades: one helps less and more narrowly than folklore says (appearance—and refuses to hurt where folklore says it must), one helps prediction but <em>hurts</em> tracking (learned motion), and one is null-to-harmful (calibrated uncertainty). None of that is visible if you report a single number for a single configuration. It’s only visible with a frozen baseline, seed variance, paired significance, and the discipline to publish the result whichever way it falls.</p>
          <p>That harness—the from-scratch metrics, the config hashing, the paired tests—became a small product in its own right: a one-command <a href="/benchmark" className="font-semibold text-indigo-600 underline decoration-indigo-200 underline-offset-4 hover:text-indigo-800">honest MOT benchmark</a> that runs a family of trackers and emits a single reproducible report (a leaderboard with paired significance and an ID-switch error taxonomy), on synthetic data or on <a href="/benchmark/dancetrack" className="font-semibold text-indigo-600 underline decoration-indigo-200 underline-offset-4 hover:text-indigo-800">real DanceTrack</a>. The tracker also runs on your own video, installs from <code>pip</code>, and has a stable public API—but the identity of the project is the measurement, not the wrapper.</p>
          <Callout label="The one-line takeaway"><p>Whether a “standard trick” helps depends less on the trick than on how it’s wired into the decision. Let a signal <em>rank</em> feasible matches and it’s robust; let it <em>veto</em> them, or trust it beyond its training distribution, and your better component makes a worse system.</p></Callout>
          <div className="mt-12 flex flex-wrap gap-3"><Button asChild size="lg"><a href="/demo">Watch the RQ1 result live <ArrowRight className="size-4" /></a></Button><Button asChild size="lg" variant="outline"><a href="/benchmark/explorer">Explore structured results</a></Button></div>
        </section>
      </article>
      <aside className="hidden xl:block"><div className="sticky top-28 rounded-2xl border border-slate-200 bg-gradient-to-br from-slate-950 to-indigo-950 p-6 text-white shadow-xl"><p className="font-mono text-[10px] uppercase tracking-[.16em] text-cyan-300">Research principle</p><p className="mt-4 text-lg font-semibold leading-7">A negative result is useful when the experiment makes it reproducible.</p><a href="/lab" className="mt-6 flex items-center gap-2 text-sm font-semibold text-white/70 hover:text-white">Open Reliability Lab <ArrowRight className="size-4" /></a></div></aside>
    </div>
  </>
}
