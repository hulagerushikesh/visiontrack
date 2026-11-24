# Two-week plan while the UA-DETRAC terms are pending

Written 2026-11-23. Window: **2026-11-23 to 2026-12-06.** The terms email went
to the UA-DETRAC authors on 2026-11-20. This plan assumes their reply takes
about two weeks.

## Where things stand

- The traffic motion-gate question has three frozen tests behind it.
  RoundaboutHD did not support turning the gate off. GRAM-RTM supported it.
  SVMOT supported it and preferred it to the aspect-free gate.
- The opt-in `preset("traffic")` is published in 0.6.0 (2026-11-23). The
  library default is unchanged.
- The [default-change proposal](DEFAULT_CHANGE_PROPOSAL.md) is a draft. Its
  UA-DETRAC section is empty.
- The [UA-DETRAC protocol](UA_DETRAC_TEST_PROTOCOL.md) is frozen and its
  runner is written and tested on made-up files. The test uses the dataset's
  own detections, so it needs **no detector run**. Once data arrives, the
  compute is light.

## Rules for this window

- Nothing from UA-DETRAC is downloaded until the authors confirm the terms in
  writing and the owner approves the download.
- No other download without owner approval (file, source and size stated).
- Nothing here changes the library default, saved traces or the C++ parity
  contract, except where an item says it adds a test.
- Laptop limits apply: one heavy job at a time, ask before more than 30
  minutes of load. Every item below is light.

## Week 1 (2026-11-23 to 2026-11-29): build — ship what is already proven

**B1. Release candidate 0.6.0 with the traffic preset.** Bump the version,
write release notes that say plainly the default is unchanged, and run the
release-readiness checks: the full test suite, the package build and a fresh
install from the built files. A minor version, because it adds public names.
*Done when:* the candidate is ready on main and the owner can publish it.
Publishing stays the owner's step.

*B1 done 2026-11-23: 0.6.0 published. B2 done 2026-11-23: a gate-off parity
fixture is checked by both runtimes, and C++ CI passes it. B3 done 2026-11-23:
the measured list is in the
[proposal](DEFAULT_CHANGE_PROPOSAL.md#dry-run-what-moves-if-the-default-flips-measured-2026-11-23).
B4 done 2026-11-23: the [run sheet](UA_DETRAC_RUN_SHEET.md) needs two files
(test annotations and detections, no images); a full-size made-up run took
10 minutes. R1 done 2026-11-23: [why the gate misses](GATE_MISS_EXPLANATION.md);
on SVMOT every recovered crossing was refused on width-to-height ratio, not
speed. R2 done 2026-11-23: [turning-traffic screen](TURNING_TRAFFIC_SCREEN.md);
no new source meets every need, and GRAM-RTM Urban1 stays first choice. R3 done
2026-11-24: the write-up's closing section now names the traffic follow-up and
its limits.*

**B2. C++ agreement with the gate off.** C++ 0.1.1 already has the gate
switch. Add one gate-off case to the cross-runtime fixtures, so both runtimes
are checked with the gate off as well as on. This is a test, not a C++
behaviour change, so it fits maintenance mode. *Done when:* C++ CI passes
the gate-off case. If the runtimes disagree, that is worth knowing before any
default change.

**B3. Default-change dry run.** On a throwaway branch that is never merged,
flip the default and record everything that moves: tests, saved traces, the
three web demo traces, the parity fixture and the docs that quote the default.
*Done when:* the proposal's release checks have a measured list, so a "go"
decision takes about a day of work instead of an unknown amount.

**B4. UA-DETRAC run sheet.** Time the existing runner on made-up files at the
full test-split size (40 sequences) and write a one-page sheet: which files
are needed (the test may need only the annotations and detections, not the
images, to be confirmed on the dataset page), the format check, the run and
how the result is recorded. *Done when:* the owner can approve the download
with a size and a time estimate in hand.

## Week 2 (2026-11-30 to 2026-12-06): research — explain, don't re-test

**R1. Why the gate misses fast vehicles.** Replay the saved GRAM-RTM and
SVMOT detections and, for every crossing the gate-on tracker missed, record
what blocked the match: the gate distance, which part of the box drove it
(position, width-to-height ratio or height), the vehicle's speed in pixels
per frame and its box size as a stand-in for distance from the camera.
*Output:* one figure and a short record. This uses data the project has
already used, so it explains the earlier results. It does not test anything
and cannot change a verdict.

**R2. The turning-traffic gap.** Every test so far is fixed cameras on mostly
straight traffic. Do a desk screen, with no downloads, for unused junction
video with per-vehicle identities and clear reuse terms. *Output:* a short
list with the terms status of each, for the owner to choose from.

**R3. Refresh the write-up's closing section.** It still speaks only of the
three original enhancements. Add a sentence on the traffic follow-up and its
limits.

## Decision point: 2026-12-04, two weeks after the email

| What happened | What follows |
|---|---|
| Terms allow the use | Owner approves the download. Then the format check, the run (expected well under an hour) and the filled-in proposal for the owner's decision on the default. |
| Terms forbid the use | The protocol stays as a record. Recommendation: keep the preset opt-in and do not change the default on two supporting venues alone. Pick a replacement unused source, starting from the R2 list or the earlier backup screen. |
| No reply yet | Owner sends one short reminder on 2026-12-01. On 2026-12-04, plan as if the answer is no, while leaving the door open if a reply arrives later. |

## Not in this window

- Changing the library default (it waits for UA-DETRAC and the owner).
- The preprint (deferred by the owner).
- New C++ features (maintenance only).
- Any data download without approval.

## Owner steps in this window

- Publish 0.6.0 once the candidate is ready, if you want the preset on PyPI
  before the UA-DETRAC answer. This is optional.
- Send the reminder email on 2026-12-01 if there is no reply by then.
