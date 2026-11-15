import data from "./preprocessing-hanoi.json"

export default function PreprocessingCaseStudy() {
  const total = data.crossings.length
  const legacyMatches = data.crossings.filter((row) => row.legacy !== null).length
  const upstreamMatches = data.crossings.filter((row) => row.upstream !== null).length
  const metrics = [
    { label: "Matched crossings", legacy: legacyMatches, upstream: upstreamMatches },
    { label: "Missed crossings", legacy: total - legacyMatches, upstream: total - upstreamMatches },
    { label: "Unmatched predictions", legacy: data.legacy.unmatched.length, upstream: data.upstream.unmatched.length },
    { label: "Detector boxes", legacy: data.legacy.detectionBoxes, upstream: data.upstream.detectionBoxes },
  ]

  return (
    <details id="preprocessing-study" className="scroll-mt-28 rounded-3xl border border-indigo-100 bg-white p-5 shadow-sm sm:p-7">
      <summary className="cursor-pointer text-xl font-semibold tracking-tight">
        Traffic case study · YOLOX preprocessing
      </summary>
      <div className="mt-4 space-y-4 text-sm leading-6 text-slate-700">
        <p>On one held-out Hanoi clip, changing how YOLOX received each frame increased matches
          from <strong>{legacyMatches} to {upstreamMatches} of {total}</strong> labeled crossings.
          Both runs used the same 501 frames, YOLOX Nano weights and 0.60 track-initiation threshold.</p>
        <div className="overflow-x-auto">
          <table className="w-full min-w-96 text-left">
            <caption className="sr-only">Crossing outcomes and detection volume by preprocessing mode</caption>
            <thead className="border-b border-slate-200 text-slate-950">
              <tr>
                <th scope="col" className="p-2">Measure</th>
                <th scope="col" className="p-2">RGB + nearest-sample</th>
                <th scope="col" className="p-2">BGR + bilinear</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {metrics.map((row) => (
                <tr key={row.label}>
                  <th scope="row" className="p-2 font-medium">{row.label}</th>
                  <td className="p-2 tabular-nums">{row.legacy.toLocaleString()}</td>
                  <td className="p-2 tabular-nums">{row.upstream.toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p>A match required the same direction and a prediction within four frames of a labeled crossing.
          Unmatched predictions occurred at different frames in the two runs.</p>
        <details className="rounded-xl border border-slate-200 p-4">
          <summary className="cursor-pointer font-semibold text-slate-950">Inspect individual crossings</summary>
          <div className="mt-3 overflow-x-auto">
            <table className="w-full min-w-96 text-left">
              <caption className="sr-only">Predicted frame for every labeled crossing</caption>
              <thead className="border-b border-slate-200 text-slate-950">
                <tr>
                  <th scope="col" className="p-2">Label frame</th>
                  <th scope="col" className="p-2">Direction</th>
                  <th scope="col" className="p-2">RGB prediction</th>
                  <th scope="col" className="p-2">BGR prediction</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data.crossings.map((row) => (
                  <tr key={row.frame} className={row.legacy === null && row.upstream !== null ? "bg-emerald-50" : undefined}>
                    <th scope="row" className="p-2 font-medium tabular-nums">{row.frame}</th>
                    <td className="p-2">{row.direction}</td>
                    <td className="p-2 tabular-nums">{row.legacy ?? "Missed"}</td>
                    <td className="p-2 tabular-nums">{row.upstream ?? "Missed"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <ul className="mt-3 list-disc space-y-1 pl-5">
            {data.legacy.unmatched.map((row) => <li key={row.frame}>RGB unmatched prediction at frame {row.frame} ({row.direction})</li>)}
            {data.upstream.unmatched.map((row) => <li key={row.frame}>BGR unmatched prediction at frame {row.frame} ({row.direction})</li>)}
          </ul>
        </details>
        <p>The alternate input still missed {total - upstreamMatches} crossings at this gate.
          The table contains numeric results from the VnTraffic subset of the{" "}
          <a className="font-semibold text-primary underline underline-offset-4" href="https://zenodo.org/records/18195750">Vehicle Tracking Dataset</a>.</p>
        <details className="rounded-xl border border-slate-200 p-4">
          <summary className="cursor-pointer font-semibold text-slate-950">Evaluation settings</summary>
          <p className="mt-3">Frames 0–500 at 30 fps, 1920 × 1080. A crossing occurs when the bottom center
            of a box passes the vertical segment at x = 950 and y = 670–1070 between consecutive frames.
            The scorer matches events one to one in either direction.</p>
          <p className="mt-2">Both runs use a 416-pixel model input, detection confidence 0.25 and
            suppression IoU 0.45. Predictions include cars, motorcycles, buses and trucks.
            Reference boxes label vehicles without distinguishing their types.</p>
        </details>
      </div>
    </details>
  )
}
