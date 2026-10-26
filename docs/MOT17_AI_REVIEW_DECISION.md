# MOT17 case note: an ID switch is not necessarily a forgotten person

Checkpoint: **2026-10-26**. **AI-assisted exploratory review; retain the unchanged
tracker.** This is a documented non-intervention recommendation, not a successful
fix, a measured intervention result or an independently validated visual case.

The owner confirmed that the private page opens, displays the street image and
changes frames. They then delegated the technical review to the assistant because
no second reviewer is available. Those observations are useful interaction
feedback, **not a completed human interpretation of the trajectories**. No human
review notes, agreement, approval or independent-review status were manufactured.

## What question are we answering?

The corrected scorer reports that reference trajectory **85**, previously matched
to public track **19**, is matched to **31** at source frame **54**. Does that
mean the tracker forgot a person who disappeared and returned?

**Not in the recorded 36–57 window:** public 19 is present throughout, and the
actual-call trace records an update in every frame. The evidence does not support
treating this event as deletion followed by re-entry. That conclusion is narrower
than proving the physical identity of either pedestrian or the cause of a switch.

## Evidence, kept separate from interpretation

| Evidence | Observation | What it does not establish |
| --- | --- | --- |
| Earlier saved boxes, 3–35 | 19 overlaps reference 85 at IoU >=0.5, and not 89, in all 33 public frames | Earlier pixels were not inspected; overlap is not physical-person truth |
| All 22 existing source frames, 36–57 | Two nearby light-topped figures overlap and then become more separated; their movement is consistent with opposing directions | The early overlap is ambiguous; the assistant already knew the diagnosis |
| References and saved public boxes | In later separated frames, 19 aligns with the approaching figure/reference 89; 31 appears at 54 over the away-moving figure/reference 85 | Published labels are not independently verified by this review |
| Unchanged actual-call trace | 19 stays updated/public; 31 is spawned at 52 and becomes public at 54 | No counterfactual tracker was run; a trace alone does not identify the best remedy |
| Corrected measurement chain | Original GT and saved predictions pass the real reference text loader, preprocessing and all 45 metric checks on 1,050 frames | Numerical agreement does not verify imagery, physical correspondence or usefulness to practitioners |

Plainly: a tracking box can keep its number while its correspondence to a
reference trajectory changes. Another box can subsequently become public over
the other trajectory. That is a different diagnostic situation from a lost track
being recreated after absence. This case supports investigating association
ambiguity, **not claiming its complete causal explanation**.

## What was checked in this delegated review?

Only the already admitted **36–57** images and existing saved records were used.
No earlier pixels, new scene, detector, tracker variant or validation set was
opened. This revisits known exploratory evidence; it is not a new discovery or
an independent replication of the earlier assistant inspection.

- Rechecked the pinned image manifest and every one of its 24 members: the 22
  JPEGs, acquisition receipt and method.
- Rechecked both members of the final private page manifest and confirmed the
  final page's 22-frame data agrees with the earlier contact-sheet source data.
- Checked all 22 scene contact-sheet crops pixel for pixel against the verified
  JPEG crops. Inspected those six scene sheets and six reference/output sheets,
  plus the original full frames 36 and 57 for scene context.
- Confirmed from the saved page data that 19 is public in all 22 frames and 31
  is public at 54–57. The actual internal spawn/update history comes from the
  previously recorded trace, not from guessing at the images.

All of this is **anchored AI-assisted inspection**, not blind annotation,
independent label adjudication or a measured estimate of reviewer reliability.
The private page was not controlled through an automated browser: direct local
image/file checks and the owner's interaction feedback are different evidence.

Existing image manifest:
`02bd442793b58b6090a661da66f0e779b5f571aadf431f4783e15c18ff924a89`.
Existing final page manifest:
`b3d59eac3678087d9196ae40e5ebcd2fbd9c3e4457aabd797e8f03fb5c496404`.
Neither packet, source label nor its independent-review flag was changed.
Dataset images and private notes remain outside Git; this note contains no pixels.

Verification for this documentation checkpoint: **41 focused Python tests pass**
(image intake, staged review, earlier saved context and v2 trace), the offline
staged-page control check passes, and the strict documentation build passes.
These are integrity/tooling checks, not independent visual validation. No full
repository test run or live-site deployment is claimed for this checkpoint.

## Decision: no speculative tracker fix

| Proposed action | Decision for this episode |
| --- | --- |
| Increase track lifetime or add persistent identity memory | Not justified: 19 is continuously updated/public in the observed window |
| Disable the motion gate | Not justified: the recorded later rejected pair also fails the overlap requirement; no gate-only causal attribution or counterfactual is established |
| Reduce confirmation below three hits | Would affect when the new track becomes public, but does not establish correct earlier correspondence or a safe improvement |
| Change reference labels | No: this review does not independently adjudicate them |
| Port a change to C++ | No accepted behavior change exists to port |

Keep the released/default tracker behavior and all historical results unchanged.
**“Not justified by this evidence” does not mean these ideas can never help.**
There was no intervention experiment here, so do not describe this as a measured
zero effect, an accuracy improvement or a comparison win.

## Proceed without pretending the missing review is complete

- [x] Assistant-led technical review of the existing bounded packet, with limits.
- [x] Plain-language exploratory case note and reasoned no-change recommendation.
- [ ] Independent scene/reference validation: **deferred; no reviewer available**.
- [ ] Any future intervention: justify it, prospectively fix the comparison and
      safety outcomes, and use fresh validation before accepting an improvement.
- [ ] Practitioner usefulness: remains untested; no outreach is sent by this review.

The owner does **not** need to finish the manual walkthrough for technical
documentation and exploratory analysis to continue. This explicitly changes
the earlier plan to wait for a second person before writing a case note; it does
not silently tick that review gate or relax evidence needed for validated claims.
If later physical correspondence needs more context, first record the exact
question and a fixed additional range; this review performs no new acquisition.

The current deliverable is the limited case explanation above. A subsequent
[fixed-window association inventory](MOT17_ASSOCIATION_INVENTORY.md) now separates
raw detection support from predicted association and filtered public geometry:
36–50 lack two distinct eligible neighbours for references 85/89; the separate
low-score row at 51 is not offered to already-matched 19. This is descriptive
evidence, not a tested fix. The next research decision must be based on a specific
unresolved, testable question—not a retry of a rejected candidate or a public
demonstration deadline.
Independent reference checking is still required before presenting this as a
validated physical-identity explanation or using disputed labels to accept a fix.

Supporting records: [visual intake and handoff](MOT17_VISUAL_REVIEW.md),
[saved earlier geometry](MOT17_PRIOR_CONTEXT.md),
[corrected coverage and actual trace](MOT17_COVERAGE_V2.md), and
[actual file-to-score verification](MOT17_TEXT_ROUNDTRIP.md).
