# Proposal: switch the motion gate off by default

**Draft, 2026-11-22. Not approved, not in force.** This proposal is written
ahead of the UA-DETRAC result so that it only needs filling in once that
result exists. Nothing here changes a frozen rule, the library default or any
published number. It may go to the owner for a decision only after the
UA-DETRAC section below is complete.

## The change

Change one default: `TrackerConfig.use_mahalanobis_gating` from `True` to
`False`. Every other setting stays as it is.

The candidate is **gate off**, not the aspect-free gate. Gate off was the
preferred variant in both completed venues, and it is a switch that already
exists, while the aspect-free gate would add new code to the core. If
UA-DETRAC prefers the aspect-free gate instead, see the decision table below.

Without the Mahalanobis gate, association uses only the IoU test, as the
original ByteTrack does. The change therefore also brings the default closer
to the method the library is named after.

## Evidence so far

All on video that no earlier comparison had touched, under frozen protocols,
with each variant run twice and giving byte-identical output.

| Venue | Status | Missed: on → off | False: on → off | ID switches: on → off | Verdict for gate off |
|---|---|---|---|---|---|
| [GRAM-RTM](GRAM_RTM_TEST_PROTOCOL.md), 2 sequences, 502 crossings | Done 2026-11-21 | 30 → 24 | 2 → 1 | not measured | Supported, preferred |
| [SVMOT](SVMOT_GATE_TEST_PROTOCOL.md), 9 sequences, 99 crossings | Done 2026-11-22 | 23 → 4 | 2 → 2 | 583 → 244 | Supported, preferred |
| [UA-DETRAC](UA_DETRAC_TEST_PROTOCOL.md), 40 sequences | **Waiting on the authors' terms** | — | — | — | — |

**Pedestrians (guard).** MOT17 val-half, development run: HOTA 47.78 → 47.97,
ID switches 190 → 185 ([record](ASPECT_GATE_DEVELOPMENT.md)). The guard allows
a drop of at most 0.5 HOTA. It must be repeated on the release candidate.

## UA-DETRAC result — to be filled in

*Empty until the frozen run is complete. Copy the verdicts and pooled numbers
from the protocol's result section without rewording them.*

- Gate off versus gate on: ___ (missed ___ → ___, false ___ → ___, ID switches ___ → ___, sign test p = ___)
- Aspect-free gate versus gate on: ___
- Preferred by the protocol's rule: ___

## Decision table

Fixed now, before the UA-DETRAC result exists.

| UA-DETRAC outcome | What this proposal does |
|---|---|
| Gate off supported and preferred | **Go ahead** with gate off as the default, subject to the release checks below. |
| Gate off supported, aspect-free gate preferred | **Go ahead with gate off.** It is supported on all three venues, and the aspect-free gate was only "no harm" on GRAM-RTM. Record the preference in the release notes. |
| Only the aspect-free gate supported | **Stop.** The two venues agree on no candidate. The default stays; a new frozen test would be needed. |
| Neither supported | **Stop.** The default stays, and every number is published. |
| Test stopped (terms refused, format check fails) | **Stop.** The plan needs another partner venue before this proposal can go forward. |

## Release checks, if it goes ahead

1. **Pedestrian guard** on the release candidate: MOT17 val-half HOTA must not
   fall by more than 0.5 against the current default. DanceTrack is reported
   alongside it for information only and does not decide anything.
2. **Old behaviour stays one line away.** Add a named preset that restores the
   gate (for example `pedestrian_gate`), and keep `traffic` working as an
   alias of the new default so existing code does not break.
3. **Published numbers stay true.** Every earlier result names the
   configuration it ran with. Results computed with the gate on are labelled
   as such, not silently rerun or replaced.
4. **Pinned files.** The C++ parity fixture and the three web demo traces
   record the gate as on. Each is either pinned to the old setting explicitly
   or regenerated, and each choice is recorded. Earlier result files that
   record the gate as on are left as they are, since they describe what ran.
5. **Release notes** state the change in plain words at the top, with the
   one-line way to get the old behaviour back.
6. **Python release first** (a minor version, since the default output
   changes), then a separate C++ synchronisation milestone. The C++ default
   is also gate on today. Until that milestone, the two packages' defaults
   differ, and the release notes say so.

## What this proposal does not cover

- **Turning traffic at busy junctions.** All three venues are elevated views of
  mostly straight roads. The gate was designed for crossing paths, so this is
  the most likely place for the change to hurt, and it is untested.
- **Other detectors.** GRAM-RTM and SVMOT used the pinned YOLOX-X; UA-DETRAC
  uses its own supplied detections.
- **Moving cameras.** Not tested by any venue.

## Owner decisions needed when the time comes

- Approve or reject the change after the UA-DETRAC section is filled in.
- The version number for the Python release.
- The name of the preset that restores the gate.
