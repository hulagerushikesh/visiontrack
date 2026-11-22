# Traffic preset — opt-in, not a default change

**Added 2026-11-22, at the owner's request.** `preset("traffic")` is ByteTrack
with the Mahalanobis motion gate switched off (`use_mahalanobis_gating=False`).
Every other setting is the library default. The default itself does not change:
`TrackerConfig()` still has the gate on.

```python
from visiontrack import ByteTracker, preset

tracker = ByteTracker(preset("traffic"))
tracker = ByteTracker(preset("traffic", max_age=60))  # tweaks still compose
```

The C++ package needs no change: it already accepts the same switch, and the
preset only sets it.

## Why

The default gate is tuned for slow pedestrians. On fixed-camera vehicle video
it stopped tracks from confirming on fast vehicles near the camera, so they
were missed at the counting line. Two frozen tests on video that no earlier
comparison had touched both supported switching it off:

| Frozen test | Reference crossings | Missed: gate on → off | False: gate on → off | ID switches: on → off |
|---|---|---|---|---|
| [GRAM-RTM](GRAM_RTM_TEST_PROTOCOL.md), 2 sequences | 502 | 30 → 24 | 2 → 1 | not measured |
| [SVMOT](SVMOT_GATE_TEST_PROTOCOL.md), 9 sequences | 99 | 23 → 4 | 2 → 2 | 583 → 244 |
| **Together** | **601** | **53 → 28** | **4 → 3** | |

On pedestrians, MOT17 val-half moved from 47.78 to 47.97 HOTA with the gate
off, and ID switches from 190 to 185, so the preset is not known to hurt
people tracking either.

## What it does not show

- **Not a default change.** The [traffic gate test plan](TRAFFIC_GATE_TEST_PLAN.md)
  needs UA-DETRAC as the partner venue first. Its [protocol](UA_DETRAC_TEST_PROTOCOL.md)
  and runner are frozen, waiting on the authors' terms. A
  [draft proposal](DEFAULT_CHANGE_PROPOSAL.md) is ready for that point.
- **Straight roads only.** Both venues are elevated views of mostly straight
  roads. Turning traffic at busy junctions, which the gate was designed for, is
  untested.
- **One detector per venue.** GRAM-RTM and SVMOT used the pinned YOLOX-X.
  Other detectors were not tried.

## What stayed the same

The lineage presets (`PRESET_NAMES`), the tracker zoo and benchmark runs, all
frozen protocols and every published result are unchanged. The traffic preset
lives in a separate list, `USE_CASE_PRESET_NAMES`.
