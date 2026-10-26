# Daily checkpoints and the next weekly goal

Planning checkpoint: **2026-10-26**. Days below mean focused work sessions, not
automatic work while the chat is idle or promised calendar dates. No reminder,
scheduled job, email, publication or new tracking study is authorized by this plan.

**Review-route update:** no separate reviewer is available, and the owner has
delegated the technical review to the assistant. The [bounded AI-assisted case
note](MOT17_AI_REVIEW_DECISION.md) is complete with a no-change recommendation;
independent scene/reference validation remains deferred. The owner confirmed
page/image/frame controls, not a completed trajectory review. This supersedes
the waiting dependency below **for exploratory documentation only**, not for
independently validated labels, causality or acceptance of a future fix.

**Next technical checkpoint:** the [fixed detection/association inventory](MOT17_ASSOCIATION_INVENTORY.md)
is complete without new tracker execution. It distinguishes missing/separately
unavailable detections from an unoffered low-score recovery pair. The
[prospective observation-availability recipe](OBSERVATION_AVAILABILITY_PROTOCOL.md)
now fixes all 12 small development cells, unchanged controls and complete
startup/episode/recovery reporting. Commit the tested design before actual
execution, then audit all saved outcomes. No promised fix, new public
demonstration or C++ port.

## Big aim

**Give one tracking engineer a clear, reproducible explanation of a real tracking
failure and the trade-off behind a configuration choice.** A negative result is
valid; a prettier interface or one improved number is not the finish line.

The first audience hypothesis remains fixed-camera CV engineers and applied
researchers working on counts/trajectories. We must test usefulness with them;
we have not selected a validated commercial vertical or promised higher accuracy.

## Priority clarification: evidence before demonstration

The owner's clarification on 2026-10-23 supersedes a demo-first reading of this
plan. Do not wait for the owner walkthrough to advance technical research, or
create presentation work to fill time. The demo is an optional internal teaching
aid, not public readiness. Recommend a public demonstration only when the problem,
evidence and limitations are sufficiently clear and the owner agrees.

The [first real-data intake](REAL_DATA_CASE_INTAKE.md) has now verified the
existing MOT17-04-FRCNN cache against the pinned official annotations. This
admits **annotation-only diagnosis**, not a completed visual/checked-label
case study. The [unchanged baseline](REAL_DATA_BASELINE.md) now reproduces
byte for byte across two fresh full-sequence runs. The first chronological
switch (reference 85, 19 → 31 at source frame 54) has a bounded annotation
inspection; independent pixel review remains an explicit later gate.

## Weekly aim: establish the real-data baseline and its limits

Primary weekly target: a source-verified real-data input, a reproducible unchanged
baseline and one bounded, explainable diagnostic event (or an explicit absence).
Do not claim a causal visual explanation without pixels/review, or an improvement
without a prospectively fixed comparison. The owner walkthrough remains optional
teaching, not a prerequisite for this research work.

| Session | Our delivery | Owner help | Done means |
| --- | --- | --- | --- |
| Session 1 — intake | Verify the existing cache against official annotation members and define the limited admission | None for the annotation-only route | Done: exact source conversion, task/range and remaining visual/rights gates recorded |
| Session 2 — baseline | Run and reproduce an unchanged, full-sequence cold-start baseline with complete settings and outputs | None | Done: all four run files byte-identical; ignore handling, complete outputs and metrics retained |
| Session 3 — diagnose | Inspect the first chronological scored ID switch if present; document adjacent inputs/outputs without claiming a visual cause | Optional questions about the explanation | Done at annotation level: first switch at source frame 54, fixed 51–57 context plus same-event prior-match history; no visual cause claimed |
| Session 4 — review evidence | Fixed 22-image acquisition and preliminary AI-assisted triage done; private staged page ready. Independent human review remains | One separate reviewer can now use the ready local packet; no recording/setup needed | Record agreement/disagreement and ambiguity; preliminary AI inspection is not independent adjudication |
| Session 5 — decide scope | Summarize the baseline diagnosis; justify/freeze one comparison before outcomes, or stop if unsupported | Review the plain-language summary | A defensible next research decision, not a promised winner or demo deadline |

Sessions 1–3 are complete **at the annotation-only level**, as is the earlier
internal demo preparation. The [saved-box coverage diagnosis](REAL_DATA_COVERAGE.md)
now partitions all 21,825 misses: 19,387 without raw IoU ≥0.5 support, 149 with
only sub-threshold support, 270 losing eligible neighbours to ignore handling,
and 2,019 with eligible retained neighbours but no canonical match. These are
descriptive, not causal or recoverable-error counts. The
[unchanged association/lifecycle replay](REAL_DATA_TRACE.md) is now complete:
all 1,050 frames match, 19 remains updated, and 31 is created at 52 then confirmed
at 54. Nearby reference 89 overlaps 19 strongly; physical identity attribution
still needs independent pixels/label review. No intervention is justified yet.
The bounded review brief and reasons not to tune lifetime/gates/memory blindly
are recorded. A subsequent [independent metric check](REAL_DATA_METRIC_CHECK.md)
found IDSW 44 versus 43 and HOTA 0.52372649 versus 0.52554966. TP/FN/FP and IDF1
agree, but the equivalence check fails. **Evaluator alignment and a separately
versioned re-score of unchanged outputs now precede any new tracker comparison.**
Session 4's independent pixel/reference review remains a separate gate; do not
substitute a green test suite for metric agreement or visual evidence.

That [v2 evaluator correction](EVALUATOR_V2.md) is now complete: all 45 same-input
reference checks pass, legacy reports remain unchanged and frozen studies stay
at their original revision. Independent
[preprocessing verification](MOT17_PREPROCESSING.md), the general versioned
MOT17-policy correction, [v2 coverage and the extended same-event actual trace](MOT17_COVERAGE_V2.md)
are now complete as well. The corrected prior match at 37 changes the fixed
review window to **36–57**, not the old 45–57. Every raw/scored frame and v2
failure is reproduced exactly; track 19 stays updated/public throughout.
Visual/reference review is still separate and open.
This is measurement correctness, not improved tracking or public accuracy readiness.
The [Lab policy migration](LAB_EVALUATION_POLICY.md) is also complete: new schema-3
metrics explicitly carry preprocessing v2 through failures and reports, while
historical artifacts remain unchanged and mixed policies are rejected. This
does not replace Session 4's independent visual/reference review.
The [fixed source images and preliminary visual triage](MOT17_VISUAL_REVIEW.md)
are now ready: 22 images, exact annotation correspondence, private staged review
and no public pixels. The late boxes align with two separating figures; earlier
physical correspondence remains uncertain. No lifetime/memory/gate change is
justified. Independent human review, full case admission and the optional owner
walkthrough remain pending. These sessions need not consume five full
engineering days; permission/label availability may dominate calendar time.

The [read-only prior-prefix audit](MOT17_PRIOR_CONTEXT.md) now adds earlier saved
geometry: 19 is public from 3 and supports reference 85 alone through 35. No
additional pixels or tracker runs were needed. This makes the review question
more precise but does not complete Session 4 or justify an intervention.

The separate [file-to-score verification](MOT17_TEXT_ROUNDTRIP.md) is now complete:
actual reference text-file loading, preprocessing and all 45 corrected metrics
agree on the unchanged full baseline. This closes the adapter-only boundary of
the earlier checks. Independent scene/reference review is the next external
dependency; do not create another harness solely to occupy the waiting time.

Independent maintenance during that wait found and closed real gaps in the
existing C++ parity tools (omitted classes, signed-zero equality and ignored
unit-test failure). [The maintenance record](https://github.com/hulagerushikesh/visiontrack-cpp/blob/main/PARITY_GUARDS.md)
checks the published wheel against released and current NumPy separately.
Runtime behavior is unchanged. The earlier plan for owner review tomorrow is
superseded by the delegated-review update above; do not turn unused session
allowance into a speculative fix or additional data acquisition.

## Next big deliverable: one real-clip diagnostic case study

After a clip, permitted use and independently checked task labels are ready:

- [ ] Technical intake, task boundaries and label verification: about 1 focused day.
- [ ] Unchanged baseline plus one prospectively fixed comparison on identical
      detections; visual failure explanation and reproducible report: about 2–3 days.
- [ ] Review trade-offs/limitations, prepare the case study and seek one willing
      practitioner's workflow response: about 1 day, plus their availability.

This preserves the [milestone estimate](SHOWCASE_MILESTONE.md): **4–5 focused
working days after usable data/labels are ready**. Some intake work may already
be done in Week 1; do not count it twice. A real-clip draft is a stretch weekly
outcome only if dependencies are ready early. If they are not, the real-data goal
is **not achieved** by substituting the synthetic demo.

One clip can demonstrate diagnosis, not general accuracy, novelty, a tuned fix's
independent validation or product-market fit. Private footage can stay private;
sharing any pixels needs explicit permission. A consented two-person indoor
rehearsal is not automatically representative of traffic or a re-entry risk test.

## If data is unavailable

Spend at most one focused session assessing one suitable existing-dataset route.
If rights, task fit or labels fail, record the reason and stop that route. Do not
download restricted imagery or quietly reinterpret labels. A narrower annotation
diagnostic can proceed only if explicitly suitable; do not silently call it the
complete real-data goal or create another framework just to fill time.
Acquiring data, annotating it and independent review are real work, not included
in the post-readiness technical estimate. Escalate the specific missing choice.

## After the case study

With explicit approval, show the small example to a few relevant engineers or
researchers and ask whether it would help with a failure they actually face.
No automatic mailing, repeated follow-up or dependence on one contact. Record
whether they can use it, what input they have, and what decision it changes.
Continue broader discovery separately; interest is not a design partnership.

C++ stays in maintenance at its accepted Python contract. Do not port the rejected
gate-off or stopped counting-band candidate. A new C++ milestone starts only when
useful Python behavior, frozen fixtures/API and explicit adoption justify it.

## End-of-session update template

```text
Aim:
Finished artifact and verification:
What the evidence permits us to say:
Still open / blocked, and why:
Owner action (none unless needed):
Next bounded task and conditional effort:
Local / committed / pushed / deployed status:
```

Choose one main outcome per session. Judge weekly progress by understandable
evidence and user feedback, not commit count or an invented project percentage.
