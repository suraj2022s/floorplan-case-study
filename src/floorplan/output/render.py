"""Draw the stitched floor plan as SVG and PNG.

The drawing is a plan a homeowner would recognise: rooms as outlined shapes, a dimension on
every wall, doors as a gap with a swing arc, windows as a gap with a double line, and a label
in each room with its area and ceiling height. A wall that was not actually seen is dashed,
so the drawing itself shows which parts are measured and which are inferred.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.patches import Arc, Polygon  # noqa: E402

from floorplan.pipeline import Plan  # noqa: E402

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
ROOM_FILL = "#f0efec"
WALL_WIDTH = 3.0


def _half_width(measurement) -> float:
    return (measurement.hi - measurement.lo) / 2


def _wall_label(wall) -> str:
    return f"{wall.length.value:.2f} ±{_half_width(wall.length):.2f}"


def draw_plan(plan: Plan, title: str, out_stem: Path) -> list[Path]:
    """Write `<out_stem>.svg` and `<out_stem>.png`; return the paths."""
    corners = np.concatenate([room.polygon for room in plan.rooms])
    span = corners.max(axis=0) - corners.min(axis=0)
    scale = 1.25  # inches of drawing per metre
    size = np.clip(span * scale + 2.0, 6.0, 30.0)
    figure, axis = plt.subplots(figsize=tuple(size), facecolor=SURFACE)
    axis.set_facecolor(SURFACE)
    axis.set_aspect("equal")
    axis.axis("off")

    openings_by_wall: dict[str, list] = {}
    for opening in plan.openings:
        openings_by_wall.setdefault(opening.wall, []).append(opening)

    for room in plan.rooms:
        axis.add_patch(
            Polygon(room.polygon, closed=True, facecolor=ROOM_FILL, edgecolor="none", zorder=1)
        )
        centroid = room.polygon.mean(axis=0)
        for wall in room.walls:
            start, end = wall.start, wall.end
            length = np.linalg.norm(end - start)
            direction = (end - start) / max(length, 1e-9)
            inward = np.array([-direction[1], direction[0]])
            observed = wall.length.basis == "observed" and wall.observed_share >= 0.3
            axis.plot(
                [start[0], end[0]],
                [start[1], end[1]],
                color=INK,
                linewidth=WALL_WIDTH,
                linestyle="-" if observed else (0, (2, 2)),
                solid_capstyle="round",
                zorder=3,
            )
            for opening in openings_by_wall.get(wall.id, []):
                a = start + direction * opening.position_along_wall
                b = a + direction * opening.width.value
                # erase the wall across the opening, then draw the opening's own symbol
                axis.plot(
                    [a[0], b[0]],
                    [a[1], b[1]],
                    color=ROOM_FILL,
                    linewidth=WALL_WIDTH + 2.5,
                    solid_capstyle="butt",
                    zorder=4,
                )
                if opening.kind == "window":
                    for offset in (-0.035, 0.035):
                        p, q = a + inward * offset, b + inward * offset
                        axis.plot([p[0], q[0]], [p[1], q[1]], color=INK, linewidth=0.9, zorder=5)
                elif opening.kind == "door":
                    radius = opening.width.value
                    wall_angle = np.degrees(np.arctan2(direction[1], direction[0]))
                    axis.add_patch(
                        Arc(
                            a,
                            2 * radius,
                            2 * radius,
                            angle=wall_angle,
                            theta1=0,
                            theta2=90,
                            color=INK_SECONDARY,
                            linewidth=0.8,
                            zorder=5,
                        )
                    )
                    leaf = a + inward * radius
                    axis.plot(
                        [a[0], leaf[0]],
                        [a[1], leaf[1]],
                        color=INK_SECONDARY,
                        linewidth=0.8,
                        zorder=5,
                    )
                middle = (a + b) / 2 + inward * 0.30
                axis.text(
                    middle[0],
                    middle[1],
                    f"{opening.id.split('-')[-1]} {opening.width.value:.2f} "
                    f"±{_half_width(opening.width):.2f}",
                    fontsize=6.5,
                    color=INK_SECONDARY,
                    ha="center",
                    va="center",
                    zorder=6,
                )

            # dimension text sits just inside the wall, reading along it
            anchor = (start + end) / 2 + inward * 0.14
            angle = np.degrees(np.arctan2(direction[1], direction[0]))
            if angle > 90 or angle <= -90:
                angle += 180
            if length >= 0.6:
                axis.text(
                    anchor[0],
                    anchor[1],
                    _wall_label(wall),
                    fontsize=7.5,
                    color=INK_SECONDARY,
                    ha="center",
                    va="center",
                    rotation=angle,
                    rotation_mode="anchor",
                    zorder=6,
                )

        height = room.ceiling_height
        height_text = (
            "ceiling not captured"
            if np.isnan(height.value)
            else f"ceiling {height.value:.2f} ±{_half_width(height):.2f} m"
        )
        axis.text(
            centroid[0],
            centroid[1],
            f"{room.id}\n{room.floor_area.value:.1f} ±{_half_width(room.floor_area):.1f} m²\n"
            f"{height_text}",
            fontsize=9,
            color=INK,
            ha="center",
            va="center",
            linespacing=1.4,
            zorder=6,
        )

    low = corners.min(axis=0) - 0.6
    high = corners.max(axis=0) + 0.6
    axis.set_xlim(low[0], high[0])
    axis.set_ylim(low[1] - 0.5, high[1] + 0.5)

    # one-metre scale bar and the caption
    bar = np.array([low[0] + 0.3, low[1] - 0.15])
    axis.plot([bar[0], bar[0] + 1.0], [bar[1], bar[1]], color=INK, linewidth=1.5)
    axis.text(
        bar[0] + 0.5,
        bar[1] - 0.16,
        "1 m",
        fontsize=7.5,
        color=INK_SECONDARY,
        ha="center",
        va="center",
    )
    footprint = plan.footprint_area
    axis.text(
        low[0] + 0.3,
        high[1] + 0.25,
        f"{title}   ·   {plan.tier} tier   ·   {len(plan.rooms)} room(s)   ·   footprint "
        f"{footprint.value:.1f} ±{_half_width(footprint):.1f} m²   ·   lengths in metres, "
        f"± is the 90% interval   ·   dashed = not seen, inferred",
        fontsize=8,
        color=INK_SECONDARY,
        ha="left",
        va="center",
    )

    out_stem.parent.mkdir(parents=True, exist_ok=True)
    paths = []
    plt.rcParams["svg.hashsalt"] = "floorplan"  # stable ids, so the SVG is reproducible
    for suffix in (".svg", ".png"):
        path = out_stem.with_suffix(suffix)
        figure.savefig(
            path,
            dpi=160,
            facecolor=SURFACE,
            bbox_inches="tight",
            metadata={"Date": None} if suffix == ".svg" else None,
        )
        paths.append(path)
    plt.close(figure)
    return paths
