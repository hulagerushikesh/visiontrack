type EvidenceProgressProps =
  | { status: "idle" | "verifying" | "error"; listedCount: number }
  | { status: "ready"; listedCount: number; verifiedCount: number; revealedCount: number }

export default function EvidenceProgress(props: EvidenceProgressProps) {
  const verified = props.status === "ready" ? props.verifiedCount : 0
  const revealed = props.status === "ready" ? props.revealedCount : 0
  const explanation = {
    idle: "No image files have been checked in this browser for this event. Importing report.json does not open its pictures.",
    verifying: "Checking the selected files against this report. Pictures remain hidden while the checks run.",
    error: "The selected files did not pass verification. No pictures from this selection are displayed. You can select the correct files and try again.",
    ready: "The selected files match this report's evidence records. Reveal an image below only when you want to see it. These checks do not prove tracking accuracy or explain the mistake's cause.",
  }[props.status]

  return (
    <div className="mt-4 rounded-xl border border-slate-200 bg-slate-50 p-4" role="status" aria-live="polite" aria-label="Image selection progress">
      <dl className="grid gap-3 text-sm sm:grid-cols-3">
        <div><dt className="text-xs text-muted-foreground">1. Listed in the report</dt><dd className="mt-1 font-semibold">{props.listedCount} images</dd></div>
        <div><dt className="text-xs text-muted-foreground">2. Checked in this browser</dt><dd className="mt-1 font-semibold">{verified} of {props.listedCount}</dd></div>
        <div><dt className="text-xs text-muted-foreground">3. Pictures revealed</dt><dd className="mt-1 font-semibold">{revealed} of {props.listedCount}</dd></div>
      </dl>
      <p className="mt-3 text-xs leading-5 text-slate-700">{explanation}</p>
    </div>
  )
}
