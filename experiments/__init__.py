"""Experiment harness: config, cell runner, sweep matrix and analysis.

Not part of the installable ``visiontrack`` package — this is the research
driver that sits on top of it. Run as modules from the repo root, e.g.::

    python -m experiments.run_matrix --config experiments/configs/synth_baseline.yaml
    python -m experiments.analyze --results results.parquet
"""
