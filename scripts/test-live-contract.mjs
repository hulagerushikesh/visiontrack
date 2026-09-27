import assert from "node:assert/strict"

globalThis.window=globalThis
await import("../assets/tracker.js")

assert.equal(window.VT.iou([0,0,10,10],[5,0,15,10]),1/3)
assert.deepEqual(window.VT.hungarian([[4,1,3],[2,0,5],[3,2,2]]),[[1,0],[0,1],[2,2]])

const detection=(x=10)=>({box:[x,10,x+20,50],score:.9,cls:"person"})
const tracker=new window.VT.ByteTracker({nInit:2,maxAge:2,trackThresh:.5,detThresh:.2})
assert.deepEqual(tracker.update([detection()]),[])
let visible=tracker.update([detection(1)])
assert.equal(visible.length,1)
assert.equal(visible[0].id,1)
assert.equal(tracker.totalIds,1)

tracker.reset()
assert.equal(tracker.totalIds,0)
tracker.update([detection()])
visible=tracker.update([detection(1)])
assert.equal(visible[0].id,1,"a new browser session must restart temporary labels")

console.log("live tracker contract: ok")
