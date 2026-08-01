# VisionTrack — reproducibility & dev targets.
# Override the interpreter if needed:  make test PY=python3.11
PY ?= python3

.PHONY: help install test lint reproduce reproduce-synth demo og-image zoo taxonomy gmc profile benchmark benchmark-dancetrack residual figures clean

help:
	@echo "targets:"
	@echo "  install          editable install with all extras"
	@echo "  test             run the test suite"
	@echo "  lint             ruff check"
	@echo "  demo             build the self-contained interactive demo (viz/webdemo/index.html)"
	@echo "  og-image         regenerate the social preview card (assets/og-image.png)"
	@echo "  reproduce-synth  regenerate synthetic results (NO dataset needed; CI smoke)"
	@echo "  reproduce        full reproduction (needs the MOT17 cache; see docs/PHASE0.md)"

install:
	$(PY) -m pip install -e ".[dev,experiments,appearance]"

test:
	$(PY) -m pytest -q

lint:
	$(PY) -m ruff check src tests experiments data viz

# Synthetic-only: reproduces the harness + RQ3 synthetic probe with no data.
reproduce-synth:
	$(PY) -m experiments.run_matrix --config experiments/configs/synth_baseline.yaml --out results_synth.parquet
	$(PY) -m experiments.analyze --results results_synth.parquet --out-md docs/results_synth.md
	$(PY) -m experiments.run_matrix --config experiments/configs/rq3_uncertainty_synth.yaml --out results_rq3_synth.parquet
	$(PY) -m experiments.analyze --results results_rq3_synth.parquet --baseline motion_gate

# Full reproduction of every real-data table and figure in the README.
# Prerequisite (one-time): build the caches, see docs/PHASE0.md and docs/PHASE3.md:
#   $(PY) data/cache/precompute.py            --data-root <MOT17> --detector FRCNN --out data/cache/mot17
#   $(PY) data/cache/precompute_embeddings.py --data-root <MOT17> --detector FRCNN --cache-dir data/cache/mot17
reproduce: reproduce-synth
	@echo "== baseline (all detectors) =="
	$(PY) -m visiontrack.cli eval --dataset mot17 --split val --detector FRCNN
	@echo "== RQ1 appearance =="
	$(PY) -m experiments.appearance_study --detector FRCNN --out-fig assets/appearance_mot17_frcnn.png
	@echo "== RQ3 calibration + noise =="
	$(PY) -m experiments.uncertainty_study --detector FRCNN --out-fig assets/kalman_calibration.png

# Build the pre-baked interactive demo (synthetic scene; no dataset needed).
demo:
	$(PY) viz/webdemo/build_demo_data.py

# Regenerate the Open-Graph / social preview card (assets/og-image.png) that
# renders when visiontrack.hulage.in is shared. License-clean, deterministic.
og-image:
	$(PY) scripts/make_og_image.py

# Tracker zoo: significance-tested comparison of the lineage presets
# (single-stage SORT, DeepSORT, ByteTrack, ByteTrack+ReID, GIoU) on a hard
# synthetic scene. No dataset needed; writes docs/results_tracker_zoo.md.
zoo:
	$(PY) -m experiments.tracker_zoo --out-md docs/results_tracker_zoo.md

# ID-switch error taxonomy: classify why the tracker swaps identities
# (occlusion / crowding / fast motion). Needs the DanceTrack caches.
taxonomy:
	$(PY) -m experiments.error_taxonomy --dataset dancetrack --preset bytetrack \
		--out-md docs/results_error_taxonomy_dancetrack.md

# RQ4 global motion compensation study (needs MOT17 det + <seq>.gmc.npz caches;
# build the latter with data/cache/precompute_gmc.py over the img1 frames).
gmc:
	$(PY) -m experiments.gmc_study --detector FRCNN --out-md docs/results_gmc_rq4.md

# Profile tracker throughput (FPS vs scene load) on this CPU. No dataset needed.
profile:
	$(PY) -m experiments.profile_fps --out-md docs/results_profile_fps.md

# The benchmarking tool (H3): leaderboard + significance + error taxonomy in one
# self-contained report. No dataset needed; writes the HTML served at /benchmark.
benchmark:
	$(PY) -m experiments.benchmark --out-html web/benchmark.html \
		--out-md docs/results_benchmark_synth.md

# Same tool on real DanceTrack data (needs the DanceTrack det + Re-ID caches).
benchmark-dancetrack:
	$(PY) -m experiments.benchmark --dataset dancetrack \
		--out-html web/benchmark-dancetrack.html \
		--out-md docs/results_benchmark_dancetrack.md

# RQ2: train the from-scratch motion residual and run the tracking ablation
# (needs the MOT17 + DanceTrack GT caches).
residual:
	$(PY) -m experiments.train_residual --out models/motion_residual.npz
	$(PY) -m experiments.residual_ablation --model models/motion_residual.npz

clean:
	rm -f results*.parquet
