"""Experiment configuration — typed, YAML-backed, content-hashed.

The plan calls for "a run fully specified by its config hash". We get exactly
that with plain dataclasses + PyYAML + a canonical SHA-256, and deliberately
**avoid** Hydra/OmegaConf: those add a heavy, opinionated application framework
that fights a library, and buy us nothing here beyond what a dozen lines of
hashing already provide. The whole experiment (dataset, sequences, seeds,
tracker variants) is captured in one YAML file; its hash names the run.

Heavy deps stay out of ``core`` — this module lives under ``experiments/`` and
is never imported by the package.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field


@dataclass(slots=True)
class VariantSpec:
    """A named tracker configuration: overrides applied to ``TrackerConfig``."""

    name: str
    overrides: dict = field(default_factory=dict)


@dataclass(slots=True)
class ExperimentConfig:
    """Full specification of an experiment sweep.

    ``dataset`` is ``"synthetic"`` or ``"mot17"``. For synthetic, ``sequences``
    is a list of integer scene ids (each defines a distinct reproducible scene);
    for MOT17 it is a list of video ids (e.g. ``"MOT17-02"``). Every
    (variant × sequence × seed) cell is one run.
    """

    name: str = "experiment"
    dataset: str = "synthetic"
    sequences: list = field(default_factory=lambda: [1, 2, 3])
    seeds: list = field(default_factory=lambda: [0, 1, 2, 3, 4])
    variants: list = field(default_factory=list)
    baseline: str = "baseline"
    metrics: list = field(default_factory=lambda: ["MOTA", "IDF1", "HOTA", "IDSW"])

    # synthetic-only knobs
    scene: dict = field(default_factory=dict)
    # mot17-only knobs
    detector: str = "FRCNN"
    split: str = "val"
    split_file: str = "mot17_val_half"
    cache_dir: str = "data/cache/mot17"

    def __post_init__(self) -> None:
        # Allow variants given as plain dicts (from YAML) or VariantSpec.
        norm = []
        for v in self.variants:
            norm.append(v if isinstance(v, VariantSpec) else VariantSpec(**v))
        self.variants = norm
        if not self.variants:
            self.variants = [VariantSpec("baseline", {})]

    def to_dict(self) -> dict:
        d = asdict(self)
        return d

    def config_hash(self) -> str:
        """Stable 12-char hash of the full config (order-independent)."""
        canonical = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()[:12]

    # -- YAML round-trip --------------------------------------------------
    @classmethod
    def from_yaml(cls, path: str) -> ExperimentConfig:
        import yaml

        with open(path) as f:
            data = yaml.safe_load(f) or {}
        return cls(**data)

    def to_yaml(self, path: str) -> None:
        import yaml

        with open(path, "w") as f:
            yaml.safe_dump(self.to_dict(), f, sort_keys=False)

    def variant_names(self) -> list[str]:
        return [v.name for v in self.variants]
