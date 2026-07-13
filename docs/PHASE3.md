# Phase 3 — RQ1: appearance association (the centerpiece)

Question (RQ1): *does an appearance (re-ID) association cost improve tracking,
and where does it start to hurt?* This phase builds the appearance branch and
answers the **MOT17 half** of RQ1. The cross-dataset crossover (DanceTrack,
where appearance is expected to *hurt*) is deferred — the 256 GB / MOT17-only
storage constraint means DanceTrack/SportsMOT don't fit yet.

## What shipped

| Piece | Where | Role |
|-------|-------|------|
| Embedders | [`appearance/embedder.py`](../src/visiontrack/appearance/embedder.py) | `ColorHistogramEmbedder` (from-scratch HSV histogram, **no download**), `IdentityEmbedder` (tests) |
| Optional deep re-ID | [`appearance/reid_onnx.py`](../src/visiontrack/appearance/reid_onnx.py) | `OnnxReID` — pretrained OSNet/FastReID ONNX behind the same interface (lazy) |
| EMA gallery | [`appearance/gallery.py`](../src/visiontrack/appearance/gallery.py) | per-track appearance memory (`update_gallery`) |
| Track wiring | [`tracking/track.py`](../src/visiontrack/tracking/track.py) | tracks carry an EMA `feature`, updated from matched detections |
| Cost hook | already in place (Phase 2) | `w_app` term in `build_association_cost` |
| Embedding cache | [`data/cache/precompute_embeddings.py`](../data/cache/precompute_embeddings.py) + `datasets/cache.py` | embed each detection once → `.emb.npz` aligned to the detection cache |
| Study | [`experiments/appearance_study.py`](../experiments/appearance_study.py) | appearance-on/off sweep with paired significance + figure |

Design: the embedder is **pluggable** (color histogram now, deep re-ID later),
appearance is a **weighted cost term** (`w_app`), and embeddings are **cached
once** so the sweep is CPU-only and fast. Core is untouched.

## Run it

```bash
pip install -e ".[experiments,appearance]"
# 1. detections (Phase 0) then embeddings (once, reads img1 crops):
python data/cache/precompute.py            --data-root ~/Downloads/MOT17 --detector FRCNN --out data/cache/mot17
python data/cache/precompute_embeddings.py --data-root ~/Downloads/MOT17 --detector FRCNN --cache-dir data/cache/mot17
# 2. the study:
python -m experiments.appearance_study --detector FRCNN --out-fig assets/appearance_mot17_frcnn.png
```

Detection cache: 5.2 MB. Embedding cache (32-dim color histogram, 7 seqs):
6.3 MB. Both tiny; raw frames stay deletable.

## Result (MOT17 val-half, FRCNN public detections, color-histogram embedder)

Δ vs the `w_app=0` motion-only baseline; `*` = p<0.05 (Wilcoxon over 7 sequences).

| w_app | HOTA | IDF1 | AssA | MOTA | IDSW |
|------:|------|------|------|------|-----:|
| 0.00  | 0.497 | 0.570 | 0.587 | 0.469 | 188 |
| 0.15  | +0.002 | +0.004 | +0.005 | −0.001 | 190 |
| 0.30  | +0.004 | +0.005 | +0.009 | −0.001 | 183 |
| 0.60  | **+0.005** | **+0.007** | **+0.011** | −0.000 | **178 (−10)** |

![appearance on MOT17](../assets/appearance_mot17_frcnn.png)

### Reading it honestly

- **Appearance helps association on MOT17, modestly.** The gains land in
  **AssA** (+0.011) and **IDF1** (+0.007) — the *association* metrics — while
  DetA is unchanged (appearance can't add detections). HOTA rises through AssA.
- **ID switches fall 188 → 178 (−5%)** as `w_app` increases — the cleanest
  signal, and exactly what appearance is for.
- **MOTA is flat** — expected: MOTA is detection-dominated and appearance only
  touches association.
- **Not statistically significant** at p<0.05 over 7 sequences. The effect is
  directionally consistent but small, because an HSV colour histogram is a
  *weak* descriptor. This is the honest result, not a cherry-pick — and it sets
  up the obvious next lever: a deep re-ID embedder (`OnnxReID`) drops in behind
  the same interface and should widen the gap.

This supports the RQ1 hypothesis on MOT17 (diverse pedestrian appearance ⇒
appearance helps). The predicted **sign flip on DanceTrack** (near-identical
dancers ⇒ appearance hurts) is the deferred cross-dataset half.

## Tests

`tests/test_appearance.py` (9) covers the EMA gallery, both embedders, and the
key proof that the appearance term **breaks an otherwise-symmetric motion tie**
toward the appearance-consistent assignment. `tests/test_mot_loader.py` adds
embedding-cache alignment (and misalignment → error). Behavior is unchanged
when `w_app=0`: all prior tracker/eval tests pass untouched. **244 tests pass.**

## Notes / limitations

- Colour histogram is deliberately weak; `OnnxReID` is the drop-in upgrade.
- Cross-dataset crossover (DanceTrack/SportsMOT) deferred for storage.
- Appearance deps (`matplotlib`, `pillow`) are in the `[appearance]` extra,
  lazily imported; core still needs only NumPy.
