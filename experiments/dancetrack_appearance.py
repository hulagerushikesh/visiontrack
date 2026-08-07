"""RQ1 cross-dataset contrast: does deep re-ID appearance help — or HURT — on
DanceTrack, where MOT17 said it helps?

DanceTrack is the predicted *appearance-hurts* case: dancers wear near-identical
outfits (appearance is uninformative) and move non-linearly (the CV motion prior
struggles), so a re-ID cost can pull assignments toward the wrong, look-alike
dancer. Detections are oracle-perturbed GT (DanceTrack ships none), holding
detection quality fixed — the same protocol as the synthetic probe — so this
isolates appearance's effect on association and is directly comparable to the
MOT17 result.

    python -m experiments.dancetrack_appearance --embedder onnx \
        --weights 0.0,0.15,0.3,0.6 --out-fig assets/appearance_dancetrack.png

Reads the DanceTrack detection + embedding caches (data/cache/precompute_dancetrack.py
and precompute_embeddings.py --glob 'dancetrack*.npz').
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(_ROOT), str(_ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from visiontrack.datasets.cache import CachedSequence  # noqa: E402
from visiontrack.eval.mot17 import evaluate_frames, run_sequence  # noqa: E402
from visiontrack.eval.stats import compare  # noqa: E402
from visiontrack.tracking.config import TrackerConfig  # noqa: E402


def _readers(cache_dir: Path, embedder: str):
    readers = []
    for det in sorted(cache_dir.glob("dancetrack*.npz")):
        if det.name.endswith(".emb.npz"):
            continue
        emb = det.with_name(det.stem + f".{embedder}.emb.npz")
        if emb.exists():
            readers.append(CachedSequence(det, emb_path=emb))
    return readers


def _per_seq(readers, w_app: float) -> dict[str, dict]:
    cfg = TrackerConfig(w_app=w_app)
    out = {}
    for r in readers:
        frames = run_sequence(r, cfg, 1, len(r))
        out[r.name] = evaluate_frames(frames)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="RQ1 appearance on DanceTrack")
    parser.add_argument("--embedder", default="onnx")
    parser.add_argument("--cache-dir", default="data/cache/dancetrack")
    parser.add_argument("--weights", default="0.0,0.15,0.3,0.6")
    parser.add_argument("--metrics", default="HOTA,IDF1,AssA,MOTA,IDSW")
    parser.add_argument("--out-fig", default=None)
    parser.add_argument("--detections-label", default="oracle-perturbed",
                        help="how detections are labelled in output (e.g. 'real YOLOX')")
    args = parser.parse_args(argv)

    readers = _readers(Path(args.cache_dir), args.embedder)
    if not readers:
        print(f"No DanceTrack caches (+{args.embedder} embeddings) in {args.cache_dir}. "
              "Run precompute_dancetrack.py then precompute_embeddings.py "
              "--glob 'dancetrack*.npz'.")
        return 1

    weights = [float(w) for w in args.weights.split(",")]
    metrics = args.metrics.split(",")
    seqs = [r.name for r in readers]
    print(f"RQ1 DanceTrack | embedder={args.embedder} | {len(readers)} sequences "
          f"({args.detections_label} detections)\n")

    base = _per_seq(readers, 0.0)
    header = f"{'w_app':>6} | " + " | ".join(f"{m:>16}" for m in metrics)
    print(header)
    print("-" * len(header))

    overalls = {}
    for w in weights:
        per = base if w == 0.0 else _per_seq(readers, w)
        overalls[w] = {m: float(sum(per[s][m] for s in seqs) / len(seqs)) for m in metrics}
        cells = []
        for m in metrics:
            mean = overalls[w][m]
            if w == 0.0:
                cells.append(f"{mean:>16.3f}")
            else:
                c = compare([per[s][m] for s in seqs], [base[s][m] for s in seqs], seed=0)
                star = "*" if c.p_wilcoxon < 0.05 else ""
                cells.append(f"{mean:>7.3f} {c.delta:+.3f}{star:>1}")
        print(f"{w:>6} | " + " | ".join(cells))

    print("\nΔ vs w_app=0; * = p<0.05 (Wilcoxon over sequences).")
    print("On DanceTrack the RQ1 prediction is that appearance helps LESS than on "
          "MOT17 — Δ HOTA/IDF1 near zero or negative, ΔIDSW up (hurts).")

    if args.out_fig:
        _save_figure(overalls, weights, args.out_fig, args.embedder,
                     args.detections_label)
        print(f"wrote figure -> {args.out_fig}")
    return 0


def _save_figure(overalls, weights, path, embedder, detections_label="oracle-perturbed"):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    base = overalls[0.0]
    d_assa = [overalls[w]["AssA"] - base["AssA"] for w in weights]
    d_idf1 = [overalls[w]["IDF1"] - base["IDF1"] for w in weights]
    idsw = [overalls[w]["IDSW"] for w in weights]

    fig, ax1 = plt.subplots(figsize=(6.8, 4.2), dpi=110)
    ax1.plot(weights, d_assa, "o-", color="#4c9aff", label="Δ AssA")
    ax1.plot(weights, d_idf1, "s-", color="#37b679", label="Δ IDF1")
    ax1.axhline(0, color="#888", lw=0.8)
    ax1.set_xlabel("appearance weight  w_app")
    ax1.set_ylabel("Δ vs motion-only")
    ax1.legend(loc="upper left")
    ax1.grid(alpha=0.3)

    ax2 = ax1.twinx()
    ax2.plot(weights, idsw, "^--", color="#e8833a", label="IDSW")
    ax2.set_ylabel("ID switches", color="#e8833a")
    ax2.tick_params(axis="y", colors="#e8833a")
    ax1.set_title(f"RQ1 on DanceTrack ({embedder}, {detections_label} dets)")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path


if __name__ == "__main__":
    raise SystemExit(main())
