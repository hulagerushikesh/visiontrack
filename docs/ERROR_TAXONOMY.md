# H1.3a — ID-switch error taxonomy

An IDSW count says *how often* the tracker swaps identities; it doesn't say
*when*. This tool ([`experiments/error_taxonomy.py`](../experiments/error_taxonomy.py))
classifies every identity switch by the local scene condition at the frame it
happens, and compares each condition's rate **among switches** to its **base
rate** across all ground-truth observations. The ratio is a *lift*: how
over-represented switches are in that condition. Lift ≫ 1 is the failure mode
worth attacking.

It reuses the **exact** CLEAR-MOT switch detection via a new opt-in `on_switch`
hook on `MotAccumulator` (default off → metrics unchanged), so the classified
switches are precisely those counted in IDSW.

**Conditions** (per GT box at a frame):
- **occlusion** — max IoU with any other GT box (overlap ⇒ occluder present).
- **crowding** — number of other GT boxes overlapping it (IoU > 0.05).
- **fast motion** — centre displacement from the previous frame, in box-heights.

## Finding — DanceTrack (bytetrack, 12 val seqs, 2 685 switches)

| condition | % of switches | base rate | lift |
|---|---|---|---|
| occlusion | 74.7% | 68.7% | 1.09× |
| crowding | 43.3% | 37.6% | 1.15× |
| **fast motion** | 3.4% | 0.9% | **3.86×** |

**Occlusion and crowding barely discriminate** — DanceTrack is so densely
occluded (69% of *all* GT observations are occluded) that "the switch happened
under occlusion" is almost vacuous. The signal is **fast motion**: switches are
**~4× over-represented** when an object is moving fast, even though fast frames
are rare (0.9% of observations). So the *discriminating* driver of ID switches on
DanceTrack is **motion**, not occlusion per se.

This is exactly the diagnostic the study needed: it explains *why* DanceTrack is
hard for a constant-velocity tracker (fast, non-linear motion breaks the motion
prior at the moments that matter), why appearance re-ID helps there (it's
motion-independent identity signal), and why the real lever is better motion
handling — while also showing, consistently with H1.2, that a naive linear motion
"fix" (OC-SORT's straight-line ORU) is the wrong kind of better-motion.

Run it: `make taxonomy` (DanceTrack) or
`python -m experiments.error_taxonomy --dataset synthetic --preset bytetrack`.

## Status
Done: taxonomy tool + `on_switch` hook + 6 tests, DanceTrack finding above.
Remaining half of H1.3: **CMC / GMC as RQ4** (camera-motion compensation — needs
image frames for global motion estimation), still queued.
