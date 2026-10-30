"""Preview-first deterministic synthetic onboarding for the Reliability Lab."""

from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .. import __version__
from ..detection.synthetic import SyntheticScene, SyntheticSceneConfig
from .comparison import create_comparison_summary
from .contracts import (
    DetectionRecord,
    ExperimentManifest,
    GroundTruthRecord,
    SourceManifest,
    canonical_json,
)
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
DEMO_BROWSER_DIRECTORY = "try-in-browser"


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


def _prepare_browser_demo(bundle: Path, destination: Path) -> None:
    """Stage optional import files beside, never inside, the sealed bundle."""
    from .initiation import build_initiation_trace

    trace = build_initiation_trace(bundle, variant="bytetrack", start=0, end=10)
    destination.mkdir()
    shutil.copyfile(bundle / "report/report.json", destination / "report.json")
    (destination / "initiation-trace.json").write_text(
        canonical_json(trace) + "\n", encoding="utf-8"
    )
    observations = []
    for frame in trace["frames"][:3]:
        states = ", ".join(
            f"ID {row['track_id']}: {row['state']}, "
            f"{row['hits']} {'hit' if row['hits'] == 1 else 'hits'}"
            for row in frame["tracks"]
        ) or "no internal tracks"
        public = ", ".join(str(value) for value in frame["public_track_ids"]) or "none"
        observations.append(f"  Frame {frame['frame_index']}: {states}. Public IDs: {public}.")
    guide = (
        "VisionTrack: a five-minute synthetic initiation demonstration\n\n"
        "These are generated objects, not footage or recorded people. No camera is needed.\n"
        "1. Open https://visiontrack.hulage.in/lab (or your local /lab development page).\n"
        "2. Click Import report.json and select report.json from this folder.\n"
        "3. Follow Inspect track initiation near the report heading.\n"
        "4. Click Import initiation trace and select initiation-trace.json from this folder.\n"
        "5. Use Next to compare frames 0, 1 and 2 in the three columns.\n\n"
        "Expected observations from this generated trace:\n"
        + "\n".join(observations)
        + "\n\nA tentative track is internal: it does not yet emit a public box.\n"
        "Confirmation does not add boxes retrospectively to the earlier frames.\n"
        "A confident proposal or confirmed ID does not prove a real object or correct identity.\n"
        "This demonstrates saved-run diagnosis, not improved accuracy or a better tracker.\n\n"
        "Optional: explore the comparison and failure list. This onboarding comparison is a tie.\n"
        "Skip Human review: no acceptance decision is needed for this walkthrough.\n"
        "The browser reads your selected files into tab memory; it does not upload them.\n"
        "Reloading clears the imports. Import both files again to repeat the demonstration.\n"
        "If the trace controls are missing, use the current local app or wait for deployment.\n\n"
        "For feedback: explain why an internal track might have no public box, and name\n"
        "one thing this example cannot prove. Note any confusing step; do not mark it passed\n"
        "on someone else's behalf. Preparation alone is not a usability study.\n\n"
        "The adjacent fingerprint-named directory contains the original complete Lab bundle.\n"
        "This folder holds only a byte-identical report copy, a separate trace and this guide.\n"
    )
    (destination / "START_HERE.txt").write_text(guide, encoding="utf-8")


def create_synthetic_lab(output_root: str | Path, *, with_initiation: bool = False) -> Path:
    """Stage then publish a new bundle, optionally with separate browser-demo files."""
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
        staged_paths = [bundle]
        if with_initiation:
            browser_demo = staging / DEMO_BROWSER_DIRECTORY
            _prepare_browser_demo(bundle, browser_demo)
            staged_paths.append(browser_demo)
        try:
            plan.output_root.mkdir()
        except FileExistsError:
            raise FileExistsError(
                f"refusing to replace existing output path: {plan.output_root}"
            ) from None
        published: list[Path] = []
        try:
            for staged in staged_paths:
                destination = plan.output_root / staged.name
                staged.rename(destination)
                published.append(destination)
        except BaseException:
            for destination in reversed(published):
                shutil.rmtree(destination)
            try:
                plan.output_root.rmdir()
            except OSError:
                pass
            raise
        return plan.report_path
    finally:
        if staging.exists():
            shutil.rmtree(staging)
