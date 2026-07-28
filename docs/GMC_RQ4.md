# H1.3b — RQ4: global motion compensation (GMC)

On a moving camera the whole image translates between frames, so a track's
constant-velocity Kalman prediction (which assumes a *static* camera) lands in
the wrong place and association fails. BoT-SORT's fix is **global motion
compensation**: estimate the camera's frame-to-frame motion and shift the
predictions to match. RQ4 asks the study's usual question — *when does it help?*

**From-scratch, NumPy-only.** Rather than OpenCV's ORB+RANSAC affine estimator,
GMC here uses **phase correlation** ([`tracking/motion/gmc.py`](../src/visiontrack/tracking/motion/gmc.py)):
the normalized cross-power spectrum of two frames has an inverse-FFT that peaks
at their relative shift — a few `np.fft` calls. Scope, stated honestly:
**translation only** (the dominant term for pans/handheld jitter), not the full
affine (zoom/rotation) BoT-SORT models. Per-frame shifts are precomputed once
from the image frames and cached (`<seq>.gmc.npz`), so tracking stays cache-only.

## The method validates itself

Run on MOT17 with **no prior knowledge** of which sequences move, the estimator
recovers the known ground truth exactly:

| sequence | mean \|shift\| | camera |
|---|---|---|
| MOT17-02 | 0.00 px | static |
| MOT17-04 | 0.00 px | static |
| MOT17-09 | 0.35 px | static |
| MOT17-10 | 3.29 px | moving |
| MOT17-11 | 3.53 px | moving |
| MOT17-05 | 4.38 px | moving |
| MOT17-13 | 8.53 px | moving |

## Finding — GMC helps iff the camera moves

MOT17 val-half, FRCNN detections, GMC on vs off, paired over sequences:

| group | MOTA Δ | IDF1 Δ | HOTA Δ | IDSW Δ |
|---|---|---|---|---|
| **Moving** (05/10/11/13) | +0.012 | +0.021 | +0.013 | **−6.25** |
| **Static** (02/04/09) | +0.000 | +0.000 | +0.000 | +0.000 |

- **Static cameras: a strict no-op** (Δ = 0.000, p=1.00 everywhere). Phase
  correlation detects ~zero motion, so GMC shifts nothing — the method is
  provably inert exactly where it should be. A clean control.
- **Moving cameras: consistent improvement** (fewer ID switches, higher IDF1/
  HOTA) — but **not** significant (n=4 moving sequences, p≈0.12). An honest
  positive *trend*, underpowered by how few moving-camera sequences MOT17 has.

**Answer to RQ4:** GMC helps *when and only when* the camera moves — the exact
predicted contrast. The effect is directionally clear and the no-op on static
cameras is strong validation; significance would need more moving-camera data
than MOT17 val provides (n=4).

## Status
Done: from-scratch phase-correlation GMC, gated `use_gmc` wiring (default off →
bit-identical), precompute cache, RQ4 study, 6 tests. This completes **Horizon 1**.
Reproduce: `python data/cache/precompute_gmc.py …` then `make gmc`.
