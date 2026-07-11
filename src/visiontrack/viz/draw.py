"""Visualization helpers built on matplotlib (an optional extra).

These are convenience renderers for demos and debugging — the tracker itself
never imports them. matplotlib is imported lazily so the core package has no
plotting dependency.

Two outputs are provided:

* :func:`save_trajectory_plot` — a single static figure of every track's path,
  handy for a README hero image and for eyeballing ID stability at a glance.
* :func:`animate_scene` — an animated GIF of boxes over time (needs Pillow).
"""
from __future__ import annotations

import colorsys
from collections.abc import Sequence

import numpy as np

__all__ = ["color_for_id", "save_trajectory_plot", "animate_scene", "FrameRender"]


def color_for_id(track_id: int) -> tuple[float, float, float]:
    """A stable, well-separated RGB colour for an integer id.

    Uses the golden-ratio hue rotation so consecutive ids are visually
    distinct and the palette never repeats for small id counts.
    """
    golden = 0.618033988749895
    hue = (track_id * golden) % 1.0
    return colorsys.hsv_to_rgb(hue, 0.65, 0.95)


class FrameRender:
    """A lightweight record of what to draw for a single frame."""

    __slots__ = ("index", "track_ids", "track_boxes", "gt_boxes")

    def __init__(
        self,
        index: int,
        track_ids: Sequence[int],
        track_boxes: np.ndarray,
        gt_boxes: np.ndarray | None = None,
    ) -> None:
        self.index = index
        self.track_ids = list(track_ids)
        self.track_boxes = np.asarray(track_boxes, dtype=np.float64).reshape(-1, 4)
        self.gt_boxes = None if gt_boxes is None else np.asarray(gt_boxes).reshape(-1, 4)


def save_trajectory_plot(
    path: str,
    trajectories: dict[int, list[np.ndarray]],
    width: int,
    height: int,
    title: str = "Tracked trajectories",
) -> str:
    """Render every track's centre path to an image file.

    ``trajectories`` maps ``track_id -> list of xyxy boxes`` (in time order).
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(width / 100, height / 100), dpi=100)
    ax.set_xlim(0, width)
    ax.set_ylim(height, 0)  # image coordinates: y grows downward
    ax.set_title(title)
    ax.set_facecolor("#111318")
    fig.patch.set_facecolor("#111318")
    ax.set_xlabel("x (px)", color="#cccccc")
    ax.set_ylabel("y (px)", color="#cccccc")
    ax.tick_params(colors="#888888")

    for tid, boxes in trajectories.items():
        if not boxes:
            continue
        arr = np.asarray(boxes).reshape(-1, 4)
        cx = (arr[:, 0] + arr[:, 2]) / 2
        cy = (arr[:, 1] + arr[:, 3]) / 2
        color = color_for_id(tid)
        ax.plot(cx, cy, "-", color=color, linewidth=1.8, alpha=0.9)
        ax.scatter(cx[-1], cy[-1], color=color, s=28, zorder=3)
        ax.text(cx[-1] + 5, cy[-1], str(tid), color=color, fontsize=8, weight="bold")

    fig.tight_layout()
    fig.savefig(path, facecolor=fig.get_facecolor())
    plt.close(fig)
    return path


def animate_scene(
    path: str,
    renders: list[FrameRender],
    width: int,
    height: int,
    fps: int = 15,
    show_gt: bool = True,
) -> str:
    """Write an animated GIF of the tracked boxes over time (needs Pillow)."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.animation import FuncAnimation, PillowWriter
    from matplotlib.patches import Rectangle

    fig, ax = plt.subplots(figsize=(width / 100, height / 100), dpi=100)
    fig.patch.set_facecolor("#111318")

    def draw(frame: FrameRender) -> None:
        ax.clear()
        ax.set_xlim(0, width)
        ax.set_ylim(height, 0)
        ax.set_facecolor("#111318")
        ax.set_title(f"frame {frame.index:03d}", color="#eeeeee")
        ax.tick_params(colors="#666666")

        if show_gt and frame.gt_boxes is not None:
            for box in frame.gt_boxes:
                ax.add_patch(
                    Rectangle(
                        (box[0], box[1]),
                        box[2] - box[0],
                        box[3] - box[1],
                        fill=False,
                        edgecolor="#555555",
                        linestyle="--",
                        linewidth=1.0,
                    )
                )
        for tid, box in zip(frame.track_ids, frame.track_boxes, strict=False):
            color = color_for_id(tid)
            ax.add_patch(
                Rectangle(
                    (box[0], box[1]),
                    box[2] - box[0],
                    box[3] - box[1],
                    fill=False,
                    edgecolor=color,
                    linewidth=2.0,
                )
            )
            ax.text(
                box[0], box[1] - 4, f"#{tid}", color=color, fontsize=9, weight="bold"
            )

    anim = FuncAnimation(fig, draw, frames=renders, interval=1000 / fps)
    anim.save(path, writer=PillowWriter(fps=fps))
    import matplotlib.pyplot as plt2

    plt2.close(fig)
    return path
