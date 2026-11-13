"""Render the counting paper figure from the frozen initiation-threshold replay."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib
from matplotlib import pyplot as plt
from matplotlib.lines import Line2D

from experiments.hvsd_rain_review import LINE, line_crossings
from experiments.initiation_threshold import ROOT, centers, digest, score_run

SCORE = 0.57
SPEED = 6
CASES = {
    "steady_true": "Object crosses with continuous detections",
    "persistent_false": "Clutter produces the same detections",
    "confirmed_gap": "Object crosses during a detection gap",
}
BLUE = "#155692"
GRAY = "#4b5563"
INK = "#172033"


def read_case(replay: Path, cell: dict) -> tuple[list, list]:
    directory = replay / f"{cell['case']}-{SCORE:.2f}-{SPEED}"
    inputs = json.loads((directory / "inputs.json").read_bytes())
    if digest(inputs) != cell["input_sha256"]:
        raise ValueError(f"Input differs from the frozen result in {directory.name}")
    outputs = {variant: json.loads((directory / f"{variant}.json").read_bytes())
               for variant in ("baseline", "candidate")}
    for variant, rows in outputs.items():
        if (digest(rows) != cell["output_sha256"][variant]
                or score_run(inputs, rows) != cell[variant]):
            raise ValueError(f"{variant} differs from the frozen result in {directory.name}")
    # The published figure shows the candidate trace. The baseline never emits a box here.
    if cell["baseline"]["public_boxes"] != 0:
        raise ValueError(f"Unexpected baseline observations in {directory.name}")
    return inputs, outputs["candidate"]


def plot_case(ax, inputs: list, outputs: list, title: str) -> None:
    reference = centers(inputs, "truth")
    ax.plot([row[0] for row in reference], [row[2] for row in reference],
            "--", color=GRAY, lw=1.5, label="Reference object")

    detections = [(row["frame"], (box["xyxy"][0] + box["xyxy"][2]) / 2)
                  for row in inputs for box in row["detections"]]
    frames, positions = zip(*detections, strict=True)
    ax.plot(frames, positions, "o", ms=6.5, mfc="none", mec=GRAY, mew=1, label="Detection")

    # Missing frames break the plotted line just as they break the counting rule.
    public = centers(outputs, "observations")
    by_frame = {row[0]: row[2] for row in public}
    ax.plot([row["frame"] for row in outputs],
            [by_frame.get(row["frame"], float("nan")) for row in outputs],
            "s-", ms=3.3, color=BLUE, lw=1.5, label="Public track at 0.55")

    ax.axhline(LINE["x"], color=GRAY, linestyle=":", lw=1.2, label="Counting line")
    for event in line_crossings(public):
        ax.plot(event["estimated_frame"], LINE["x"], marker="D", ms=6,
                color=BLUE, mec="white", mew=0.8, zorder=4)
    for row in inputs:
        if not row["detections"]:
            frame = row["frame"]
            ax.axvspan(frame - 0.5, frame + 0.5, color="#e6ebf1", lw=0, zorder=0)
    ax.set_title(title, loc="left", fontweight="bold", pad=9)
    ax.set_xlabel("Frame")
    ax.set_xticks(range(len(inputs)))
    ax.set_ylim(468, 545)
    ax.set_yticks([480, LINE["x"], 520, 540])
    ax.spines[["top", "right"]].set_visible(False)


def outcome(crossings: dict) -> str:
    labels = [f"{crossings[key]} {label}" for key, label in
              (("tp", "correct"), ("fp", "false"), ("fn", "missed")) if crossings[key]]
    return ", ".join(labels) or "0 events"


def render(replay: Path, output: Path) -> None:
    summary = json.loads((ROOT / "experiments/initiation_threshold_v1_results.json").read_bytes())
    cells = {cell["case"]: cell for cell in summary["cells"]
             if cell["score"] == SCORE and cell["speed"] == SPEED and cell["case"] in CASES}
    traces = {case: read_case(replay, cells[case]) for case in CASES}
    if (cells["steady_true"]["detector_sha256"] != cells["persistent_false"]["detector_sha256"]
            or traces["steady_true"][1] != traces["persistent_false"][1]):
        raise ValueError("The continuous object and clutter cases must have identical tracker I/O")

    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9.5,
                         "text.color": INK, "axes.labelcolor": INK, "axes.titlecolor": INK,
                         "xtick.color": GRAY, "ytick.color": GRAY, "axes.edgecolor": GRAY,
                         "svg.hashsalt": "visiontrack-initiation-threshold-v1"})
    fig, (continuous, gap) = plt.subplots(1, 2, figsize=(9, 5), sharey=True)
    fig.subplots_adjust(left=0.085, right=0.965, top=0.735, bottom=0.36, wspace=0.16)
    fig.text(0.085, 0.94, "Lowering the threshold recovers a crossing and adds a false count",
             fontsize=14, fontweight="bold")
    fig.text(0.085, 0.891, "Scripted cases with detection score 0.57 and speed 6 px/frame",
             color=GRAY)
    plot_case(continuous, *traces["steady_true"], "A   Continuous detections")
    plot_case(gap, *traces["confirmed_gap"], "B   Detections absent at frames 5–6")
    continuous.set_ylabel("Box center x (pixels)")
    handles, labels = continuous.get_legend_handles_labels()
    handles.append(Line2D([], [], marker="D", linestyle="none", ms=5, color=BLUE))
    labels.append("Emitted crossing")
    fig.legend(handles, labels, loc="upper left", bbox_to_anchor=(0.075, 0.867),
               frameon=False, ncol=5, columnspacing=1.15)

    table_ax = fig.add_axes([0.085, 0.042, 0.88, 0.193])
    table_ax.axis("off")
    table = table_ax.table(
        colLabels=["C   Crossing outcome by reference case", "0.60 baseline", "0.55 candidate"],
        cellText=[[title, outcome(cells[case]["baseline"]["crossings"]),
                   outcome(cells[case]["candidate"]["crossings"])]
                  for case, title in CASES.items()],
        colWidths=[0.60, 0.20, 0.20], cellLoc="left", colLoc="left", bbox=[0, 0, 1, 1],
    )
    table.auto_set_font_size(False)
    table.set_fontsize(9.2)
    for (row, _), cell in table.get_celld().items():
        cell.PAD = 0.025
        cell.set_edgecolor("white")
        cell.set_facecolor("#e6ebf1" if row == 0 else "#f4f6f9")
        cell.get_text().set_weight("bold" if row == 0 else "normal")
    is_svg = output.suffix.lower() == ".svg"
    metadata = {"Date": None} if is_svg else None
    fig.savefig(output, dpi=200, metadata=metadata)
    plt.close(fig)
    if is_svg:
        # Matplotlib adds spaces before line breaks inside path attributes.
        lines = output.read_bytes().splitlines()
        output.write_bytes(b"\n".join(line.rstrip(b" \t") for line in lines) + b"\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("replay", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    matplotlib.use("Agg")
    render(args.replay, args.output)


if __name__ == "__main__":
    main()
