# VisionTrack 0.6.0 release

Scope status: **frozen on 2026-11-23**

Release status: **published on 2026-11-23**

This minor release packages the opt-in features added to the checkout since
public 0.5.1. Every one is off unless asked for. The tracker's default
behaviour, `TrackerConfig()`, the lineage presets, saved traces and the C++
parity contract are unchanged. With explicit owner approval, `v0.6.0` was
published from `2085dea8bff4f4614d60f0294ddfdf7826719ccf`. Public 0.5.1 files
and tags remain unchanged.

Install with `python -m pip install --upgrade "visiontrack-mot==0.6.0"`.

## What is new

| Surface | Change | Default |
| --- | --- | --- |
| `preset("traffic")` | A use-case preset that turns off the motion (Mahalanobis) gate for fixed-camera traffic counting. It lives in a separate `USE_CASE_PRESETS` registry, so the tracker zoo and benchmark lineage are unchanged. See [Traffic preset](TRAFFIC_PRESET.md). | Not used unless named |
| `ByteTracker(history_limit=...)` | Keep only the recent tail of each active track's `history` list. A limit below what the configured motion terms read is refused. See [API](API.md). | `None`: full history, as before |
| `YoloxDetector(preprocessing="upstream")` and `visiontrack track --yolox-preprocessing upstream` | Upstream-style BGR channel order and bilinear resize, through the new `yolox-upstream` extra (OpenCV). See [Video](VIDEO.md). | `legacy`: unchanged input handling |
| `YoloxDetector.detect_with_proposals()` and `ProposalCapture` | Bounded per-frame research diagnostics of the decoder's proposals, alongside the normal detections. See [proposal capture](YOLOX_PROPOSAL_CAPTURE.md). | `detect()` is unchanged and records nothing |
| `YoloxDetector` construction | A model whose fixed input size differs from `input_size` is refused when the detector is built, instead of failing later during inference. | Valid models are unaffected |

## Evidence behind the traffic preset

Three frozen tests on unused fixed-camera traffic video decided whether to
offer this preset:

- RoundaboutHD did **not** support turning the gate off: one camera got worse
  by one error.
- GRAM-RTM supported it: missed line crossings fell from 30 to 24 of 502, with
  false crossings 2 to 1.
- SVMOT supported it and preferred it to the aspect-free gate: missed
  crossings fell from 23 to 4 of 99, with no extra false crossings, and ID
  switches fell from 583 to 244.

On the MOT17 validation half, turning the gate off left HOTA at 47.97 against
47.78. That is why the preset is safe to offer. It is not evidence that the
default should change. That question waits for the
[UA-DETRAC test](UA_DETRAC_TEST_PROTOCOL.md) and the owner's decision on the
[draft proposal](DEFAULT_CHANGE_PROPOSAL.md).

## Compatibility and limits

- Code that does not name the new options behaves exactly as in 0.5.1.
- Turning traffic at busy junctions, other detectors and moving cameras are
  untested for the traffic preset.
- `history_limit` and the internal history bound in read-only Lab replay save
  memory. They are not speed or accuracy claims. Replay still checks the
  entire saved output exactly.
- Proposal capture records how greedy suppression grouped boxes. It is not a
  verified uncertainty estimate and does not feed the tracker.
- New producer versions change diagnostic content IDs. Older valid reports
  and fixed teaching assets remain supported and are not regenerated.
- C++ 0.1.1 and its accepted Python oracle are unchanged. C++ already exposes
  the same gate switch. A published 0.6.0 pairing is not established by this
  release.

## Candidate gates

- [x] Freeze the scope above: opt-in additions only, defaults unchanged.
- [x] Prepare matching project and import versions, and a current-producer
      benchmark fixture, keeping the 0.5.1 fixture as history.
- [x] Pass the full Python test suite (1,561 passed, 2 skipped), lint, all
      web contracts and workflows, types and app build, and the strict
      documentation build. Checked locally on 2026-11-23.
- [x] Build both distributions, pass the package metadata check, and install
      each into its own clean environment: version 0.6.0, the traffic preset,
      history limit, proposal capture and the command line all load from the
      installed copy. These local installs reused already-installed
      dependencies rather than downloading fresh ones; hosted CI runs the full
      fresh-install check.
- [x] Pass hosted CI at the exact candidate commit: all seven jobs passed on
      2026-11-23, including the isolated fresh wheel and source installs.
      A later commit that only edits this checklist must pass CI again before
      it is tagged.
- [x] Obtain owner approval for the verified commit, then publish the matching
      tag and verify the public files and a fresh public installation.
- [x] After publication, update the install instructions on the website and in
      the README to 0.6.0.
