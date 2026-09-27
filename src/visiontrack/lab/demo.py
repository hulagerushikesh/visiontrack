"""Preview-first deterministic synthetic onboarding for the Reliability Lab."""

from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .. import __version__
from ..detection.synthetic import SyntheticScene, SyntheticSceneConfig
from .comparison import create_comparison_summary
from .contracts import DetectionRecord, ExperimentManifest, GroundTruthRecord, SourceManifest
from .failures import calculate_failure_events
from .metrics import calculate_bundle_metrics
from .report import generate_local_report
from .runner import run_comparison
from .storage import (
    create_experiment_bundle,
    detection_payload_sha256,
    ground_truth_payload_sha256,
)

DEMO_CREATED_AT = "2026-01-01T00:00:00Z"
DEMO_SEED = 7
DEMO_FRAMES = 48
DEMO_OBJECTS = 4


@dataclass(frozen=True, slots=True)
class SyntheticLabPlan:
    """Resolved onboarding output and immutable experiment identity."""

    output_root: Path
    bundle_path: Path
    report_path: Path
    experiment_id: str
    source_id: str
    detection_count: int
    ground_truth_count: int
    frame_count: int
    object_count: int
    seed: int
    variants: tuple[str, ...]


def _records() -> tuple[
    SourceManifest,
    ExperimentManifest,
    tuple[DetectionRecord, ...],
    tuple[GroundTruthRecord, ...],
]:
    config = SyntheticSceneConfig(
        width=640,
        height=360,
        num_objects=DEMO_OBJECTS,
        num_frames=DEMO_FRAMES,
        miss_rate=0.12,
        occluded_miss_rate=0.3,
        false_positive_rate=0.2,
        seed=DEMO_SEED,
    )
    detections: list[DetectionRecord] = []
    ground_truth: list[GroundTruthRecord] = []
    for frame in SyntheticScene(config):
        detections.extend(
            DetectionRecord.from_detection(
                detection,
                frame_index=frame.index,
                source_frame=frame.index,
                detection_index=index,
            )
            for index, detection in enumerate(frame.detections)
        )
        ground_truth.extend(
            GroundTruthRecord(
                frame_index=frame.index,
                source_frame=frame.index,
                object_id=int(object_id) + 1,
                xyxy=tuple(float(value) for value in box),
                class_id=1,
                visibility=1.0,
                ignored=False,
            )
            for object_id, box in zip(frame.gt_ids, frame.gt_boxes, strict=True)
        )
    detection_records = tuple(detections)
    ground_truth_records = tuple(ground_truth)
    source = SourceManifest.create(
        kind="synthetic",
        name="VisionTrack deterministic onboarding scene",
        detection_sha256=detection_payload_sha256(
            detection_records, frame_count=config.num_frames
        ),
        ground_truth_sha256=ground_truth_payload_sha256(
            ground_truth_records, frame_count=config.num_frames
        ),
        video_sha256=None,
        detector={
            "name": "visiontrack.synthetic",
            "seed": config.seed,
            "miss_rate": config.miss_rate,
            "false_positive_rate": config.false_positive_rate,
        },
        frame_count=config.num_frames,
        width=config.width,
        height=config.height,
        fps=30.0,
        coordinate_space="pixel_xyxy",
        created_at=DEMO_CREATED_AT,
    )
    experiment = ExperimentManifest.create(
        source_id=source.source_id,
        baseline="bytetrack",
        variants=(
            {"name": "bytetrack", "preset": "bytetrack", "overrides": {}},
            {"name": "single-stage", "preset": "sort", "overrides": {}},
        ),
        metrics=("HOTA", "IDF1", "MOTA", "IDSW", "Frag"),
        frame_range={"start": 0, "end": config.num_frames},
        visiontrack_version=__version__,
        git_revision=None,
        environment={"generator": "visiontrack.synthetic", "seed": config.seed},
        created_at=DEMO_CREATED_AT,
    )
    return source, experiment, detection_records, ground_truth_records


def _validate_destination(output_root: Path) -> None:
    if output_root.exists() or output_root.is_symlink():
        raise FileExistsError(f"refusing to replace existing output path: {output_root}")
    parent = output_root.parent
    if not parent.is_dir():
        raise ValueError(f"output parent directory does not exist: {parent}")


def plan_synthetic_lab(output_root: str | Path) -> SyntheticLabPlan:
    """Resolve the deterministic onboarding operation without writing files."""
    output_path = Path(output_root)
    _validate_destination(output_path)
    source, experiment, detections, ground_truth = _records()
    bundle = output_path / experiment.experiment_id
    return SyntheticLabPlan(
        output_root=output_path,
        bundle_path=bundle,
        report_path=bundle / "report" / "report.json",
        experiment_id=experiment.experiment_id,
        source_id=source.source_id,
        detection_count=len(detections),
        ground_truth_count=len(ground_truth),
        frame_count=DEMO_FRAMES,
        object_count=DEMO_OBJECTS,
        seed=DEMO_SEED,
        variants=tuple(variant["name"] for variant in experiment.variants),
    )


def create_synthetic_lab(output_root: str | Path) -> Path:
    """Atomically create one complete deterministic onboarding bundle."""
    plan = plan_synthetic_lab(output_root)
    source, experiment, detections, ground_truth = _records()
    parent = plan.output_root.parent
    staging = Path(tempfile.mkdtemp(prefix=".visiontrack-lab-demo-", dir=parent))
    try:
        bundle = create_experiment_bundle(
            staging,
            experiment,
            source,
            detections,
            ground_truth,
        )
        run_comparison(bundle)
        calculate_bundle_metrics(bundle)
        calculate_failure_events(bundle)
        create_comparison_summary(bundle)
        generate_local_report(bundle)
        try:
            plan.output_root.mkdir()
        except FileExistsError:
            raise FileExistsError(
                f"refusing to replace existing output path: {plan.output_root}"
            ) from None
        try:
            bundle.rename(plan.bundle_path)
        except BaseException:
            try:
                plan.output_root.rmdir()
            except OSError:
                pass
            raise
        return plan.report_path
    finally:
        if staging.exists():
            shutil.rmtree(staging)
