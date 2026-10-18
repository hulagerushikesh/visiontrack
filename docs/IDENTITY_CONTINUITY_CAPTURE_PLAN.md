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
number of takes, and permissible scene changes in a dated manifest. The
metadata-only [`CaptureManifest`](https://github.com/hulagerushikesh/visiontrack/blob/main/experiments/reentry_capture_manifest.py)
validates these choices and yields a stable fingerprint. Keep the populated
manifest and fingerprint in the owner's private study record, not Git; record
the fingerprint before the first take to make later changes detectable. The
hash alone does not prove *when* the plan was frozen. The validator checks
structure, **not** whether permissions or consent actually exist. Mix scenario
order where practical and include ordinary footage between scripted events so
the stream is not solely idealized entrances.

## Truth and split contract

1. Assign random **session-local participant codes** and a separate, stable
   random **participant-group key** in a private mapping held by the owner.
   The group key is needed to catch the same volunteer appearing in both
   development and test under different session-local codes. Do not put names,
   the mapping, or actual event records in the research repository. Record
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

The metadata-only [`experiments/reentry_capture_ledger.py`](https://github.com/hulagerushikesh/visiontrack/blob/main/experiments/reentry_capture_ledger.py)
contract checks that two distinct reviewer codes labeled each event, disagreements
are not silently promoted, returns have an ordered observable exit boundary,
and recording/session/participant groups do not cross splits. It returns only
counts by event category. It cannot establish consent, correct visual truth,
or that a private group key actually represents the same person, or that the
reviewers worked independently; those remain owner and reviewer
responsibilities. No real ledger has been created.

### Owner-local preflight command

The [preflight CLI](https://github.com/hulagerushikesh/visiontrack/blob/main/experiments/reentry_pilot_preflight.py) connects the
frozen manifest and two-reviewer ledger without opening footage. Start with
the checked-in [example plan](https://github.com/hulagerushikesh/visiontrack/blob/main/experiments/examples/reentry_pilot_manifest.example.json)
and [example ledger](https://github.com/hulagerushikesh/visiontrack/blob/main/experiments/examples/reentry_pilot_ledger.example.jsonl)
to learn the format; every `EXAMPLE` value is fake, and the example is **not**
rights, consent, or a research result. For a real pilot, create populated files
**outside both repositories** in the owner's restricted local study workspace.
Do not substitute a public URL or upload these records.

Before any recording, run the manifest-only check and write down its printed
SHA-256 in the private dated freeze log:

```bash
python -m experiments.reentry_pilot_preflight --manifest /private/path/pilot-plan.json
```

After the independent reviews and any reasoned adjudication, run the ledger
check against that **previously recorded** fingerprint:

```bash
python -m experiments.reentry_pilot_preflight \
  --manifest /private/path/pilot-plan.json \
  --ledger /private/path/pilot-events.jsonl \
  --expected-fingerprint PRE_RECORDING_SHA256
```

For planned-versus-recorded accounting, create a private take inventory with
**one row per frozen `(split, scenario, slot)`**. A row is `recorded`, `missing`,
or `excluded`; an excluded row uses only a controlled code (`withdrawn`,
`bystander`, `technical`, or `other`), not a name or free-text explanation.
Every recorded scored take links to exactly one reviewed ledger event with the
same split, recording, session, and scenario label. A recorded `session_reset`
control has no scored event and still needs human review of the reset boundary.
The [synthetic inventory example](https://github.com/hulagerushikesh/visiontrack/blob/main/experiments/examples/reentry_pilot_inventory.example.json)
shows the format and intentionally has five missing takes. Run:

```bash
python -m experiments.reentry_pilot_preflight \
  --manifest /private/path/pilot-plan.json \
  --ledger /private/path/pilot-events.jsonl \
  --inventory /private/path/pilot-takes.json \
  --expected-fingerprint PRE_RECORDING_SHA256
```

The command rejects unknown or duplicate JSON fields, changed plans, malformed
reviews, impossible exit boundaries, and split leakage. It emits only the plan
fingerprint and aggregate event counts, never participant keys or event IDs.
Without an inventory, the output explicitly marks take coverage `not_checked`
and keeps the research gate incomplete. The optional inventory rejects omitted/duplicate planned slots, extra ledger
events, mismatched event links, and recording/session split conflicts. Its
output is aggregate counts only. `metadata_incomplete` means the ledger still
lacks unambiguous novel/return events in both splits, has unresolved reviews,
or the inventory declares missing/excluded takes. Even
`metadata_only_review_required` is **not** clearance to score or publish: a
human must still establish actual consent/rights, independent visual truth,
whether each declared recording actually exists and covers the scripted take,
the reason for any exclusion, reset behavior, and the frozen
detector/crop/gallery protocol. The CLI deliberately does not mark those
conditions as passed. Do not silently replace missing or excluded slots after
seeing outcomes; document protocol deviations in the private study record.

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
