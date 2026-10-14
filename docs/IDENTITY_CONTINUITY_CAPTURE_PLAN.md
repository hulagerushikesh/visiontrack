# RQ5 consented capture and adjudication plan

Status: **plan only, 2026-10-14**. No participant recruitment, recording, or
real-data result is authorized or reported here. This plan addresses the
[DanceTrack feasibility audit](IDENTITY_CONTINUITY_DATA_AUDIT.md): a GT box gap
does not by itself show that a person left and returned.

## Purpose and boundary

Build a small, owner-controlled **same-camera, same-session** research set with
observable exits, returns, and genuinely new arrivals. The decision remains
the registered [restore-or-abstain question](IDENTITY_CONTINUITY_PROTOCOL.md).
It does not recognize names, search unrelated cameras, or create a permanent
person database. The pilot tests the capture and labeling pipeline; it cannot
certify the protocol's 1% false-restoration operating point on its own.

Do not collect anything until the project owner has chosen a lawful venue,
obtained appropriate informed consent and recording permissions, reviewed
applicable privacy requirements, and documented a withdrawal path. Exclude
minors and incidental bystanders; if one enters, pause or discard that take.
Keep raw video and derived appearance vectors out of Git, public demos, and
third-party services unless a separate explicit permission and data review
covers that use. Store locally with restricted access and encryption, define
retention and deletion dates before recording, and honor withdrawals.

## Capture matrix for the feasibility pilot

Use a fixed camera, resolution, frame rate, and marked scene boundary. Record
camera and lighting settings, not names, in the experiment manifest. Aim for
several consenting adult volunteers across **separate development and test
recording sessions**; final counts depend on recruitment and should be
reported, never silently padded with repeated correlated attempts.

| Scenario | Ground-truth action | Required negative control |
|---|---|---|
| Novel arrival | A volunteer enters for the first time in that session | Gallery does not contain that volunteer |
| Short return | Volunteer fully crosses the visible boundary, stays out for a scripted short interval, then re-enters | Another volunteer may remain on scene |
| Long return | Same action after a longer scripted interval, including a predeclared memory-expiry condition | A return after expiry is unavailable, not an eligible success |
| Lookalike distractor | Two volunteers with similar clothing/appearance enter at distinct times | A novel lookalike must not inherit the earlier ID |
| Crowded/occluded control | Volunteer stays within scene but is temporarily hidden | Never label this as an exit-and-return event |
| Session reset | End one authorized session and start another | No identity carryover across sessions |

Before recording, specify actual short/long intervals, gallery capacity, TTL,
number of takes, and permissible scene changes in a dated manifest. Avoid
choosing these after seeing tracker errors. Mix scenario order where practical
and include ordinary footage between scripted events so the stream is not
solely idealized entrances.

## Truth and split contract

1. Assign random **session-local participant codes** in a private key held by
   the owner; do not put names or the key in the research repository. Record
   event IDs, recording IDs, frame numbers, and whether the person fully left
   the observable scene. An occlusion or missed detection is a different event.
2. Mark the last fully visible frame before exit, first fully out-of-scene
   frame, first visible frame on return, and any ambiguity interval. Mark novel
   arrivals independently of tracker output. Retired candidate availability
   is computed from the predeclared TTL/eviction policy, not inferred from a
   successful match.
3. Have two reviewers independently label events using the same rubric before
   looking at model decisions. Resolve disagreements with a recorded reason;
   exclude unresolved cases without silently replacing them. Keep the private
   event ledger and video local. A shareable aggregate may contain counts and
   timings only after privacy review.
4. Partition by **recording session and participant** before any threshold or
   crop tuning. No person or recording appears in both development and test.
   If this is impossible with the available volunteers, report a pipeline
   pilot only—no held-out-person claim. Keep the test sessions unopened during
   feature and threshold selection.
5. Freeze detector version, crop selection, embedding adapter, tracklet
   boundaries, gallery policy, exclusions, and threshold grid on development
   data. Score abstain-all, forced-nearest, threshold-only, and threshold-plus-
   margin on the identical test opportunity list.

## Pilot acceptance and scale-up gate

First verify that every scripted event has a reviewable video boundary and a
consistent ledger, that novel and expired-return controls are present, and
that independent reviewers agree or document disagreement. Report counts by
event type and recording, exclusions, restore attempts, false restorations,
eligible-return recall, and memory availability exactly as in the registered
protocol. A small pilot's zero observed errors is **not** a low-risk bound;
nearby events from one participant or take are correlated. Use grouped
uncertainty in a larger follow-up, and report insufficient evidence when the
sample cannot support the risk budget.

If consent, rights, truthful labels, or a leakage-free split cannot be
established, stop the real-data RQ5 claim. Continue only with synthetic
engineering tests and the existing ordinary tracker. Do not port identity
memory to VisionTrack C++ until a Python decision contract and parity fixture
are frozen after this gate.
