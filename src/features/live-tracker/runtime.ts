export type LiveRuntimeCleanup = () => void

declare global {
  interface Window {
    tf?: unknown
    cocoSsd?: {load:(options:{base:string})=>Promise<unknown>}
    VT?: {ByteTracker:new(options:Record<string,number>)=>unknown}
    VTLive?: {mount:(root:Document|HTMLElement)=>LiveRuntimeCleanup}
  }
}

const pending = new Map<string,Promise<void>>()

function loadScript(src:string,ready:()=>boolean):Promise<void>{
  if(ready())return Promise.resolve()
  const existing=pending.get(src)
  if(existing)return existing
  const promise=new Promise<void>((resolve,reject)=>{
    const script=document.createElement("script")
    script.src=src
    script.async=true
    script.onload=()=>ready()?resolve():reject(new Error(`Runtime loaded without its expected API: ${src}`))
    script.onerror=()=>reject(new Error(`Unable to load the live-tracker runtime: ${src}`))
    document.head.appendChild(script)
  }).catch(error=>{pending.delete(src);throw error})
  pending.set(src,promise)
  return promise
}

export async function loadLiveRuntime():Promise<NonNullable<Window["VTLive"]>>{
  await loadScript("https://cdn.jsdelivr.net/npm/@tensorflow/tfjs@4.22.0/dist/tf.min.js",()=>Boolean(window.tf))
  await loadScript("https://cdn.jsdelivr.net/npm/@tensorflow-models/coco-ssd@2.2.3/dist/coco-ssd.min.js",()=>Boolean(window.cocoSsd))
  await loadScript("/assets/tracker.js",()=>Boolean(window.VT?.ByteTracker))
  await loadScript("/assets/live.js",()=>Boolean(window.VTLive?.mount))
  if(!window.VTLive)throw new Error("The live-tracker adapter is unavailable.")
  return window.VTLive
}
