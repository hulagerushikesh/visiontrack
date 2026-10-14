import { ArrowRight, BookOpen, FlaskConical, GraduationCap, ShieldCheck } from "lucide-react"
import type { ReactNode } from "react"
import { Button } from "@/components/ui/button"

const source = "https://github.com/hulagerushikesh/visiontrack/blob/main/learning/"

const audiences = [
  { title: "Curious reader", time: "6–8 hours", outcome: "Explain why an ID can change, what the tracker knows, and when a human should question it." },
  { title: "Computer vision student", time: "8–12 weeks", outcome: "Build a small tracker, reproduce an experiment, and report its limitations." },
  { title: "Developer or ML engineer", time: "4–6 weeks", outcome: "Trace the real code, produce a Reliability Lab bundle, and protect its contracts." },
  { title: "Research or product lead", time: "6 weeks", outcome: "Frame falsifiable questions and decide which evidence earns a product or runtime change." },
]

const research = [
  { title: "Tracking reliability", status: "Built; validating the user need", text: "Compare fixed evidence, inspect failures, and preserve the reason for a human decision." },
  { title: "Bounded identity continuity", status: "Next scientific study", text: "Study when to restore a recent anonymous identity and when to abstain under explicit error, time, and memory budgets." },
  { title: "Verified acceleration", status: "C++ parity gate active", text: "Move accepted behavior into the fast runtime only after exact outputs and the performance benefit are measured." },
]

function GuideShell({children}:{children:ReactNode}) {
  return <div className="mx-auto max-w-7xl px-5 pb-28 pt-32 lg:px-8 lg:pt-40">{children}</div>
}

export function ZeroToHero() {
  return <GuideShell>
    <a href="/teaching" className="text-sm font-medium text-primary hover:underline">← Learning lab</a>
    <div className="mt-8 max-w-4xl"><p className="font-mono text-xs font-semibold uppercase tracking-[.16em] text-primary">Choose your starting point</p><h1 className="mt-4 text-balance text-5xl font-semibold tracking-[-.05em] sm:text-7xl">From zero to research.</h1><p className="mt-6 max-w-2xl text-lg leading-8 text-muted-foreground">One real tracker, four ways in. Each route ends with something you can explain, build, or test.</p></div>
    <div className="mt-12 grid gap-4 md:grid-cols-2">{audiences.map((route, index) => <a key={route.title} href={`${source}ZERO_TO_HERO.md#choose-your-route`} className="group rounded-[1.5rem] border border-border bg-card p-7 transition hover:-translate-y-1 hover:border-primary/40"><div className="flex items-start justify-between"><span className="font-mono text-xs font-semibold text-primary">0{index + 1} · {route.time}</span><GraduationCap className="size-5 text-primary"/></div><h2 className="mt-8 text-2xl font-semibold">{route.title}</h2><p className="mt-3 leading-7 text-muted-foreground">{route.outcome}</p><span className="mt-8 inline-flex items-center gap-2 text-sm font-semibold text-primary">Read the complete path <ArrowRight className="size-4 transition group-hover:translate-x-1"/></span></a>)}</div>
    <div className="mt-12 rounded-[1.5rem] border border-indigo-100 bg-gradient-to-br from-indigo-50 via-white to-cyan-50 p-8"><BookOpen className="size-6 text-primary"/><h2 className="mt-4 text-2xl font-semibold">Practice with the actual system</h2><p className="mt-3 max-w-2xl leading-7 text-muted-foreground">The full curriculum connects geometry, motion, assignment, evaluation, research design, and the Python/C++ parity capstone. The source document is the single maintained version.</p><div className="mt-6 flex flex-wrap gap-3"><Button asChild><a href={`${source}ZERO_TO_HERO.md`}>Open full curriculum <ArrowRight className="size-4"/></a></Button><Button asChild variant="outline"><a href="/study">Interactive study guide</a></Button></div></div>
  </GuideShell>
}

export function ResearchLead() {
  return <GuideShell>
    <a href="/teaching" className="text-sm font-medium text-primary hover:underline">← Learning lab</a>
    <div className="mt-8 max-w-4xl"><p className="font-mono text-xs font-semibold uppercase tracking-[.16em] text-primary">Research lead path</p><h1 className="mt-4 text-balance text-5xl font-semibold tracking-[-.05em] sm:text-7xl">Know what we built.<br/><span className="text-muted-foreground">Know what remains unknown.</span></h1><p className="mt-6 max-w-2xl text-lg leading-8 text-muted-foreground">A six-week route for understanding VisionTrack’s product question, scientific thesis, and Python-to-C++ decision boundary.</p></div>
    <div className="mt-12 grid gap-4 lg:grid-cols-3">{research.map((area, index) => <div key={area.title} className="rounded-[1.5rem] border border-border bg-card p-7"><div className="flex items-center justify-between"><span className="font-mono text-xs font-semibold text-primary">0{index + 1}</span>{index === 1 ? <FlaskConical className="size-5 text-primary"/> : <ShieldCheck className="size-5 text-primary"/>}</div><h2 className="mt-8 text-2xl font-semibold">{area.title}</h2><p className="mt-2 text-xs font-semibold uppercase tracking-wider text-primary">{area.status}</p><p className="mt-4 leading-7 text-muted-foreground">{area.text}</p></div>)}</div>
    <div className="mt-12 rounded-[1.5rem] border border-indigo-100 bg-gradient-to-br from-indigo-50 via-white to-cyan-50 p-8"><h2 className="text-2xl font-semibold">The research question</h2><p className="mt-3 max-w-3xl text-lg leading-8 text-muted-foreground">When a recently disappeared anonymous object returns, can we restore continuity within a fixed false-restoration and memory budget—and refuse when the evidence is weak?</p><div className="mt-6 flex flex-wrap gap-3"><Button asChild><a href={`${source}RESEARCH_LEAD_PATH.md`}>Read the full six-week path <ArrowRight className="size-4"/></a></Button><Button asChild variant="outline"><a href="/writeup">See existing research</a></Button></div></div>
  </GuideShell>
}
