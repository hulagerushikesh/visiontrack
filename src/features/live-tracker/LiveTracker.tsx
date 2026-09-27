import { useEffect, useRef, useState } from "react"
import { Camera, CheckCircle2, Cpu, Eye, LockKeyhole, ScanSearch, TriangleAlert } from "lucide-react"

import { loadLiveRuntime, type LiveRuntimeCleanup } from "./runtime"

const stats=[["m-fps","—","fps · detect + track"],["m-tracks","0","active tracks"],["m-ids","0","session IDs created"],["m-dets","0","detections · frame"]]

export default function LiveTracker(){
  const root=useRef<HTMLDivElement>(null)
  const [runtimeError,setRuntimeError]=useState<string|null>(null)

  useEffect(()=>{
    const previousTitle=document.title
    document.title="VisionTrack — live on-device tracker"
    let cancelled=false
    let cleanup:LiveRuntimeCleanup|undefined
    loadLiveRuntime().then(runtime=>{
      if(cancelled||!root.current)return
      cleanup=runtime.mount(root.current)
    }).catch(error=>{
      if(!cancelled)setRuntimeError(error instanceof Error?error.message:"The live tracker could not start.")
    })
    return()=>{cancelled=true;cleanup?.();document.title=previousTitle}
  },[])

  return <div ref={root} className="mx-auto max-w-7xl px-5 pb-28 pt-32 lg:px-8 lg:pt-40">
    <section className="grid gap-10 lg:grid-cols-[.86fr_1.14fr] lg:items-end">
      <div><p className="mb-5 inline-flex items-center gap-2 rounded-full border border-emerald-100 bg-emerald-50 px-3 py-1.5 font-mono text-[10px] font-semibold uppercase tracking-[.16em] text-emerald-700"><Camera className="size-3"/>Live · on device</p><h1 className="text-balance text-5xl font-semibold tracking-[-.05em] sm:text-7xl">Point a camera.<br/><span className="text-muted-foreground">See identity persist.</span></h1><p className="mt-7 max-w-2xl text-lg leading-8 text-muted-foreground">A COCO detector proposes objects. VisionTrack’s own Kalman filter, Hungarian assignment, ByteTrack association, and lifecycle keep a stable track ID while the object remains in this session.</p></div>
      <div className="grid gap-3 sm:grid-cols-3"><div className="rounded-2xl border border-indigo-100 bg-indigo-50/60 p-5"><LockKeyhole className="size-5 text-primary"/><p className="mt-4 font-semibold">Private by default</p><p className="mt-2 text-sm leading-6 text-muted-foreground">Frames stay in this browser tab.</p></div><div className="rounded-2xl border border-cyan-100 bg-cyan-50/60 p-5"><Cpu className="size-5 text-cyan-700"/><p className="mt-4 font-semibold">Browser inference</p><p className="mt-2 text-sm leading-6 text-muted-foreground">Detection and tracking run on-device.</p></div><div className="rounded-2xl border border-emerald-100 bg-emerald-50/60 p-5"><ScanSearch className="size-5 text-emerald-700"/><p className="mt-4 font-semibold">Explainable core</p><p className="mt-2 text-sm leading-6 text-muted-foreground">No imported tracking library.</p></div></div>
    </section>

    <section className="mt-14 overflow-hidden rounded-[1.75rem] border border-slate-800 bg-[#050808] text-white shadow-2xl shadow-slate-950/25" aria-labelledby="tracker-stage-title">
      <div className="flex h-12 items-center border-b border-white/10 px-5"><div className="flex gap-1.5" aria-hidden="true"><i className="size-2 rounded-full bg-white/15"/><i className="size-2 rounded-full bg-white/15"/><i className="size-2 rounded-full bg-primary/70"/></div><h2 id="tracker-stage-title" className="ml-auto font-mono text-[10px] uppercase tracking-[.16em] text-emerald-300">Live · Kalman + Hungarian + ByteTrack</h2></div>
      <div className="relative aspect-video bg-black"><video id="src-video" className="absolute size-px opacity-0" playsInline muted/><canvas id="live-cv" width="960" height="540" role="img" aria-label="Live source with local detections and session-local numbered track IDs" className="absolute inset-0 size-full object-contain"/></div>
      <div className="border-t border-white/10 p-5 sm:p-6"><div className="flex flex-wrap items-center gap-3"><button id="start-btn" type="button" disabled className="inline-flex h-11 items-center justify-center rounded-xl bg-emerald-300 px-6 text-sm font-semibold text-slate-950 transition hover:bg-emerald-200 disabled:cursor-not-allowed disabled:opacity-45 data-[running=true]:bg-amber-300">Start tracking</button><div id="src-seg" role="group" aria-label="Video source" className="inline-flex rounded-xl border border-white/10 bg-white/5 p-1"><button type="button" data-src="webcam" aria-pressed="true" className="rounded-lg px-4 py-2 text-sm font-medium text-white/55 transition aria-pressed:bg-white aria-pressed:text-slate-950">Webcam</button><button type="button" data-src="sample" aria-pressed="false" className="rounded-lg px-4 py-2 text-sm font-medium text-white/55 transition aria-pressed:bg-white aria-pressed:text-slate-950">Sample clip</button></div><label className="ml-auto inline-flex cursor-pointer items-center gap-2 font-mono text-xs text-white/60"><input id="det-toggle" type="checkbox" defaultChecked className="accent-emerald-300"/>Show raw detections</label></div><p id="status" className="mt-4 min-h-5 font-mono text-xs text-white/55" role="status" aria-live="polite">Loading browser runtime…</p>{runtimeError&&<div className="mt-4 flex gap-3 rounded-xl border border-amber-400/30 bg-amber-300/10 p-4 text-sm text-amber-100" role="alert"><TriangleAlert className="mt-0.5 size-5 shrink-0"/><span>{runtimeError} Check your connection and reload this page.</span></div>}</div>
    </section>

    <section className="mt-4 grid grid-cols-2 gap-3 lg:grid-cols-4" aria-label="Live tracker metrics">{stats.map(([id,value,label])=><div key={id} className="rounded-2xl border border-border bg-white p-5"><p id={id} className="font-mono text-2xl font-bold tabular-nums">{value}</p><p className="mt-2 text-xs font-medium text-muted-foreground">{label}</p></div>)}</section>

    <section className="mt-8 rounded-3xl border border-emerald-200 bg-emerald-50/70 p-6 sm:p-8"><div className="flex items-start gap-4"><LockKeyhole className="mt-0.5 size-6 shrink-0 text-emerald-700"/><div><h2 className="text-lg font-semibold text-emerald-950">Nothing leaves your device.</h2><p className="mt-2 max-w-4xl leading-7 text-emerald-950/70">Camera frames are decoded, detected, and tracked in this browser tab. VisionTrack has no video server or upload step. Camera permission is requested only after you press Start with Webcam selected; choose Sample clip to try the identical pipeline without granting camera access.</p><p className="mt-3 text-sm font-medium text-emerald-900">Track IDs are temporary session labels—not persistent person identities, recognition, or identification.</p></div></div></section>

    <section className="mt-20"><div className="max-w-3xl"><p className="font-mono text-xs font-semibold uppercase tracking-[.16em] text-primary">What happens per frame</p><h2 className="mt-3 text-4xl font-semibold tracking-[-.04em]">One detector. Four inspectable steps.</h2></div><div className="mt-10 grid gap-4 md:grid-cols-2 lg:grid-cols-4">{[[Eye,"Detect","COCO-SSD proposes person and vehicle boxes. This is the only learned imported component."],[Cpu,"Predict","Each active track advances through an 8-state constant-velocity Kalman filter."],[ScanSearch,"Associate","Hungarian matching and ByteTrack’s two score bands reconnect detections to tracks."],[CheckCircle2,"Manage","Tentative, confirmed, and deleted states control when session-local IDs appear and retire."]].map(([Icon,title,text])=><article key={String(title)} className="rounded-2xl border border-border bg-white p-6"><Icon className="size-5 text-primary"/><h3 className="mt-7 text-lg font-semibold">{String(title)}</h3><p className="mt-3 text-sm leading-6 text-muted-foreground">{String(text)}</p></article>)}</div></section>
  </div>
}
