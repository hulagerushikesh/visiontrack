# Next goal: one understandable tracking-reliability case study

Planning checkpoint: **2026-10-23**. This is a bounded delivery plan, not a
new accuracy claim, validated customer segment, or promised completion date.

## What we can show now

VisionTrack is a research alpha: a tracker, a local-first Reliability Lab and
learning material. C++ is its released, parity-checked execution engine. The
current public site can be demonstrated now with its synthetic/illustrative
evidence labelled honestly. We do not need to invent a better tracker before
showing a useful diagnostic workflow.

One completed experiment already provides a concrete lesson: turning off a
rejection gate removed ID switches in the tested synthetic scenes but worsened
other tracking/counting measures. We rejected that change rather than presenting
one improved metric as an overall improvement. This is evidence of the Lab's
diagnostic purpose, not proof of customer value or real-world accuracy.

## Who the first demonstration is for

**Primary audience hypothesis:** computer-vision engineers and applied tracking
researchers evaluating detector/tracker combinations for fixed-camera counting
or trajectories. Their proposed task is: “Help me understand a failure and avoid
shipping a misleading improvement.” Traffic analytics is a useful first context,
not a selected commercial vertical. Jan's written feedback is one domain input,
not a partnership, buying commitment or market validation.

**Secondary audience:** students and researchers learning tracking and controlled
evaluation. Learning material is useful today, but learner interest alone would
not validate an engineering product. General consumers, worldwide person search,
face recognition and a large surveillance platform are outside this milestone.

## Finish line

One permitted real clip, one narrowly defined tracking task, and one readable
case study showing:

- The input, camera/detector context, evaluated range and known limitations.
- Independently checked reference labels for that task; missing labels are not
  treated as evidence that nothing happened.
- The unchanged baseline and one justified, prospectively fixed comparison on
  identical detections, with relevant trade-offs and no cherry-picked winner.
- At least one visually understandable failure, with any pictures shared only
  under explicit permission. A private clip can remain private.
- A reproducible local report and a short explanation of what decision the
  evidence supports, including “reject” or “insufficient evidence.”
- One outside practitioner's usability feedback, if a willing reviewer is
  available. Absence of feedback leaves that checkbox open, not product-validated.

This is a **single-clip diagnostic case study**, not a general accuracy benchmark,
independent validation of a tuned fix, re-entry risk certification or research
novelty claim. Any later acceptance claim needs separate representative evidence
and a frozen evaluation. A two-person rehearsal cannot establish low error risk.

## Checklist and planning estimates

Estimates assume focused working days, usable inputs and timely human review.
They are effort estimates, not background work or calendar guarantees.

| Order | Deliverable | State | Estimated effort / dependency |
| --- | --- | --- | --- |
| 1 | Stop the fixed counting-band candidate at its structural feasibility gate | Done; see [counter decision](CROSSING_BAND_COUNTER.md#feasibility-decision-2026-10-23) | Reviewed authored counterexamples; no grid run |
| 2 | Prepare a 3–5 minute existing-report demonstration: problem, failure, trade-off, decision | Ready locally; owner/external walkthrough pending | [Generated/verified report and run sheet](SHOWCASE_DEMO.md); onboarding is a tie, trade-off comes from a separate completed synthetic study |
| 3 | Admit one real clip with permission, task definition, detector and checked labels | Open | About 1 day of technical intake **after** rights/data are ready; acquisition/review time is separate |
| 4 | Produce the fixed comparison, visual explanation and reproducible report | Open | About 2–3 focused days after step 3; stop on invalid evidence |
| 5 | Review the case study and obtain one practitioner workflow response | Open | About 1 day of preparation/review, plus their availability |

The real-clip technical case study is approximately **4–5 focused working days
after admissible data and labels are ready** (steps 3–5). Allow roughly **1–2
calendar weeks only if** permission, labelling and reviewer availability line up.
If they do not, finish the synthetic workflow demonstration and report the
specific missing dependency; do not wait idly or substitute synthetic scores.

Use the [daily checkpoints and weekly delivery goal](WEEKLY_DELIVERY_PLAN.md) to
track this work. Demo preparation is complete; comprehension, clip admission and
real-data evidence are not. No reminders or background runs are scheduled.

A first external pilot is a later checkpoint, not a promised product launch.
Reserve a separate **4–6 week planning window after an engaged practitioner and
representative permitted data exist** to test repeated usefulness and scope the
smallest application. The window can end with rejection or a narrower problem.
There is no honest date yet for a superior tracker, a paper or product-market fit.

## How to reach people without waiting on one contact

Prepare a short public demo and ask a few relevant engineers/researchers whether
it helps them explain a real failure or choose between configurations. Existing
open-source tracking communities and the existing OpenTrafficCam conversation
are possible routes, subject to community rules and explicit outreach approval.
Lead with a concrete example and a small feedback request, not a mass mailing or
an unsupported accuracy claim. Do not publish private footage, contact details,
unreleased repository content or a new external post without approval.

Continue the broader discovery goal of 5–10 conversations and three prospective
design partners separately. It is not necessary to wait for all of them before
showing the research alpha; one response does not establish demand either.

## Owner help and boundaries

The owner need not learn every metric or run terminal commands to help. First
complete the short [Lab walkthrough](LAB_WALKTHROUGH.md) and say which explanation
is unclear. For a private recording route, start with the empty-room setup check;
agree permission, adult consent, storage and retention **before** filming people.
We can guide recording one step at a time. Existing-dataset use is an alternative
only after rights and task-label suitability are checked.

No new UI redesign, cloud platform, identity database or C++ port is on this
critical path. C++ remains maintained at the accepted Python contract. Re-entry
research stays separate and gated on admissible labels and explicit error risk.
This plan does not authorize sending messages, publishing assets or uploading data.
