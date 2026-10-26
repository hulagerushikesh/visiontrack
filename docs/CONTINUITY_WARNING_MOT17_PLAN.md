# Continuity warning — fixed MOT17 exploratory triage check

Method checkpoint: **2026-10-26, before this replay**. This is a read-only,
post-development transfer check on the *already investigated* MOT17-04-FRCNN
sequence. It is not an untouched test set, independent physical-identity review,
flow-count evaluation, practitioner study or calibrated deployment claim. Preserve
the [v1 candidate and development outcome](CONTINUITY_WARNING_FINDINGS.md)
unchanged; there is no threshold search or new tracker behavior here.

## One engineer decision

Would a fixed-camera tracking engineer find it worthwhile to **queue a short
interval for manual continuity inspection** when the offline observer sees two
recent public tracks without two distinct detector boxes? This is a triage
choice, not an automatic identity correction or assertion that a person changed.
The engineer may inspect the source and decide that the warning is irrelevant.

For each warning at one-based source frame `w`, reserve the inclusive frame
window `[w, min(w+2, 1050)]`. Merge overlapping/adjacent windows to count
distinct review tasks. Count both raw warning frames/components and distinct
frames reserved for review; this is a proxy for workload, not measured human
review time. A corrected-v2 scored ID switch or fragmentation event at frame
`s` is *temporally covered* if any warning window includes `s`. Record covered
and missed event counts, unique event frames, and warning windows with/without
each event type. A warning window with no scored ID switch is **not** a proven
false alert: the observer detects box-support shortage and the scorer's labels
do not describe all legitimate review reasons. A covered switch is **not** a
causal explanation, physical-person match or useful practitioner decision.
Also retain every warning and no-warning frame with assessment-opportunity and
two-supported-track flags so empty/startup frames are not treated as safe.

## Fixed inputs and integrity gates

- Exactly source frames 1–1050 of the existing, locally verified
  `MOT17-04-FRCNN.npz`; cache and official annotation bytes must re-pass the
  existing intake, with no images/appearance inputs or downloads.
- Use `TrackerConfig()` defaults and the unchanged current NumPy package. Run
  the committed **v1 observer before each tracker update**. Compare *every*
  detection row/score and public track ID/box with the sealed historical raw
  baseline. Fail rather than reinterpret any mismatch. This replay is not a new
  tracker candidate. The observer's output-only memory is reset once at source
  frame 1; its frame number is zero-based (`source_frame-1`).
- Read the sealed historical baseline and the separately corrected v2 event
  packet by their pinned manifests. Require the v2 reference-metric receipt to
  pass. The v1 scores must not be used for event coverage.
- Save complete observer records, not only positive warnings, plus source,
  method, runtime and input fingerprints in a **new private directory outside
  both repositories**. Manifest only after the entire replay and all checks
  pass. Preserve partial records and an error receipt on failure, with no
  selective frame retry. No source images, private annotations, uploads,
  website changes or C++ port.

## Decision after observing results

Report the entire workload and temporal-event table, including a negative or
unhelpful result. This check has **no pass threshold for product acceptance**;
it cannot estimate real-world sensitivity or false-alarm rate from one known
sequence. Keep the observer offline even if some events align. Before a UI
feature or v2 rule, obtain permitted representative settings with independent
reference/scene review, a task-specific count/flow or trajectory decision, and
practitioner feedback on whether the queued intervals actually change a
decision. A data-collection choice remains with the owner.

This plan is committed with its replay/test implementation **before** the
exploratory run. The later findings must name that revision, full output
manifest and any integrity failures. No outcome-driven changes to this method.
