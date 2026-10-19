import type { FailureType, ReportFailure } from "./types"

export const failureExplanations: Record<FailureType, { label: string; meaning: string }> = {
  id_switch: {
    label: "Tracking ID changed",
    meaning: "A reference object was matched to a different tracking ID than before.",
  },
  fragmentation: {
    label: "Tracking interrupted",
    meaning: "A previously matched reference object is now unmatched: its tracking was interrupted.",
  },
  miss: {
    label: "Expected object not matched",
    meaning: "An object in the reference labels had no matching tracker output under the evaluation rules.",
  },
  false_positive: {
    label: "Extra tracker output",
    meaning: "A tracker output had no matching object in the reference labels under the evaluation rules.",
  },
}

export function explainFailure(failure: ReportFailure) {
  return `${failure.variant}, frame ${failure.frame_index}: ${failureExplanations[failure.event_type].meaning}`
}
