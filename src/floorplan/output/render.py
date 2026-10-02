"""Draw the stitched floor plan as SVG and PNG.

The drawing is a plan a homeowner would recognise: rooms as outlined shapes, a dimension on
every wall, doors as a gap with a swing arc, windows as a gap with a double line, and a label
in each room with its area and ceiling height. A wall that was not actually seen is dashed,
so the drawing itself shows which parts are measured and which are inferred. Damage is
marked where it is, with its id; the colour only repeats what the legend and the id say.

The plan is turned so that its longest wall runs across the page. The pipeline's own frame
is wherever the capture started, which is rarely square to anything.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.patches import Arc, Polygon, Rectangle  # noqa: E402

from floorplan.pipeline import Plan  # noqa: E402

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_SECONDARY = "#52514e"
ROOM_FILL = "#f0efec"
WALL_WIDTH = 3.0
# one fixed colour per damage class, in the reference palette's order; never reassigned
DAMAGE_COLOURS = {
    "water_stain": "#2a78d6",
    "crack": "#eb6834",
    "mould": "#1baf7a",
    "peeling_paint": "#eda100",
    "hole": "#e87ba4",
}
DAMAGE_NAMES = {
    "water_stain": "water stain",
    "crack": "crack",
    "mould": "mould",
    "peeling_paint": "peeling paint",
    "hole": "hole",
}


def _half_width(measurement) -> float:
    return (measurement.hi - measurement.lo) / 2


def _reading_angle(direction: np.ndarray) -> float:
    angle = np.degrees(np.arctan2(direction[1], direction[0]))
    if angle > 90 or angle <= -90:
        angle += 180
    return angle


def draw_plan(plan: Plan, title: str, out_stem: Path) -> list[Path]:
    """Write `<out_stem>.svg` and `<out_stem>.png`; return the paths."""
    # turn the plan so its longest wall is horizontal
    walls = [wall for room in plan.rooms for wall in room.walls]
    longest = max(walls, key=lambda wall: wall.length.value)
    heading = np.arctan2(*(longest.end - longest.start)[::-1])
    c, s = np.cos(-heading), np.sin(-heading)
    turn = np.array([[c, -s], [s, c]])

    def view(points: np.ndarray) -> np.ndarray:
        return np.atleast_2d(points)[:, :2] @ turn.T

    corners = np.concatenate([view(room.polygon) for room in plan.rooms])
    span = corners.max(axis=0) - corners.min(axis=0)
    size = np.clip(span * 1.25 + 2.2, 6.0, 30.0)
    figure, axis = plt.subplots(figsize=tuple(size), facecolor=SURFACE)
    axis.set_facecolor(SURFACE)
    axis.set_aspect("equal")
    axis.axis("off")

    # 1. room fills and walls
    wall_of: dict[str, tuple] = {}
    for room in plan.rooms:
        axis.add_patch(
            Polygon(
                view(room.polygon), closed=True, facecolor=ROOM_FILL, edgecolor="none", zorder=1
            )
        )
        for wall in room.walls:
            start, end = view(wall.start)[0], view(wall.end)[0]
            length = np.linalg.norm(end - start)
            direction = (end - start) / max(length, 1e-9)
            wall_of[wall.id] = (start, direction, np.array([-direction[1], direction[0]]), length)
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

    # 2. openings: cut the wall on both sides of a door that joins two rooms
    for opening in plan.openings:
        if opening.wall not in wall_of:
            continue
        start, direction, inward, _ = wall_of[opening.wall]
        a = start + direction * opening.position_along_wall
        b = a + direction * opening.width.value
        cuts = [(a, b)]
        if opening.other_room is not None:
            thickness = opening.wall_thickness or 0.15
            middle = (a + b) / 2 - inward * thickness
            for wall_id, (w_start, w_direction, w_inward, w_length) in wall_of.items():
                if not wall_id.startswith(opening.other_room + "-"):
                    continue
                along = float((middle - w_start) @ w_direction)
                across = abs(float((middle - w_start) @ w_inward))
                if 0 <= along <= w_length and across < 0.15:
                    half = opening.width.value / 2
                    cuts.append(
                        (
                            w_start + w_direction * (along - half),
                            w_start + w_direction * (along + half),
                        )
                    )
        for p, q in cuts:
            axis.plot(
                [p[0], q[0]],
                [p[1], q[1]],
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
            axis.add_patch(
                Arc(
                    a,
                    2 * radius,
                    2 * radius,
                    angle=np.degrees(np.arctan2(direction[1], direction[0])),
                    theta1=0,
                    theta2=90,
                    color=INK_SECONDARY,
                    linewidth=0.8,
                    zorder=5,
                )
            )
            leaf = a + inward * radius
            axis.plot(
                [a[0], leaf[0]], [a[1], leaf[1]], color=INK_SECONDARY, linewidth=0.8, zorder=5
            )
        # along the wall like the wall's own dimension, one text line further into the room
        label_at = (a + b) / 2 + inward * 0.30
        axis.text(
            label_at[0],
            label_at[1],
            f"{opening.id.split('-')[-1]} {opening.width.value:.2f} "
            f"±{_half_width(opening.width):.2f}",
            fontsize=6.5,
            color=INK_SECONDARY,
            ha="center",
            va="center",
            rotation=_reading_angle(direction),
            rotation_mode="anchor",
            zorder=7,
        )

    # 3. damage, marked where it is
    classes_drawn = []
    for region in plan.damage:
        colour = DAMAGE_COLOURS.get(region.kind, INK_SECONDARY)
        if region.kind not in classes_drawn:
            classes_drawn.append(region.kind)
        centre = view(region.centre)[0]
        along = turn @ np.asarray(region.along)[:2]
        if region.surface in wall_of:
            _, _, inward, _ = wall_of[region.surface]
            half = along * region.width.value / 2
            p, q = centre - half + inward * 0.07, centre + half + inward * 0.07
            axis.plot(
                [p[0], q[0]],
                [p[1], q[1]],
                color=colour,
                linewidth=4.0,
                solid_capstyle="butt",
                zorder=6,
            )
            label_at = centre + inward * 0.42
        else:  # on a ceiling or floor: its footprint
            across = np.array([-along[1], along[0]])
            corner = centre - along * region.width.value / 2 - across * region.height.value / 2
            axis.add_patch(
                Rectangle(
                    corner,
                    region.width.value,
                    region.height.value,
                    angle=np.degrees(np.arctan2(along[1], along[0])),
                    facecolor="none",
                    edgecolor=colour,
                    linewidth=1.6,
                    hatch="////",
                    zorder=6,
                )
            )
            label_at = centre
        axis.text(
            label_at[0],
            label_at[1],
            region.id.split("-")[-1],
            fontsize=6.5,
            color=INK,
            ha="center",
            va="center",
            zorder=8,
            bbox={"facecolor": SURFACE, "edgecolor": "none", "pad": 0.6, "alpha": 0.85},
        )

    # 4. wall dimensions and room labels
    for room in plan.rooms:
        outline = view(room.polygon)
        extent = outline.max(axis=0) - outline.min(axis=0)
        narrow = extent.min() < 1.8
        for wall in room.walls:
            start, direction, inward, length = wall_of[wall.id]
            if length < 0.6:
                continue
            # in a narrow room the middle is taken by the room label: move long-wall
            # dimensions toward one end
            position = 0.22 if narrow and length > 2.5 else 0.5
            anchor = start + direction * length * position + inward * 0.14
            axis.text(
                anchor[0],
                anchor[1],
                f"{wall.length.value:.2f} ±{_half_width(wall.length):.2f}",
                fontsize=7.5,
                color=INK_SECONDARY,
                ha="center",
                va="center",
                rotation=_reading_angle(direction),
                rotation_mode="anchor",
                zorder=7,
            )
        height = room.ceiling_height
        height_text = (
            f"ceiling {height.value:.2f} ±{_half_width(height):.2f} m"
            if height.available
            else "ceiling not captured"
        )
        area_text = f"{room.floor_area.value:.1f} ±{_half_width(room.floor_area):.1f} m²"
        centroid = outline.mean(axis=0)
        if narrow:
            long_axis = np.array([1.0, 0.0]) if extent[0] >= extent[1] else np.array([0.0, 1.0])
            axis.text(
                centroid[0],
                centroid[1],
                f"{room.id} · {area_text} · {height_text}",
                fontsize=7.5,
                color=INK,
                ha="center",
                va="center",
                rotation=_reading_angle(long_axis),
                rotation_mode="anchor",
                zorder=7,
            )
        else:
            axis.text(
                centroid[0],
                centroid[1],
                f"{room.id}\n{area_text}\n{height_text}",
                fontsize=9,
                color=INK,
                ha="center",
                va="center",
                linespacing=1.4,
                zorder=7,
            )

    low, high = corners.min(axis=0) - 0.6, corners.max(axis=0) + 0.6
    axis.set_xlim(low[0], high[0])
    axis.set_ylim(low[1] - 0.6, high[1] + 0.5)

    # scale bar, caption and the damage legend
    bar = np.array([low[0] + 0.3, low[1] - 0.2])
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
    cursor = bar[0] + 1.6
    for kind in classes_drawn:
        axis.plot(
            [cursor, cursor + 0.3],
            [bar[1], bar[1]],
            color=DAMAGE_COLOURS.get(kind, INK),
            linewidth=4.0,
            solid_capstyle="butt",
        )
        label = axis.text(
            cursor + 0.4,
            bar[1],
            DAMAGE_NAMES.get(kind, kind),
            fontsize=7.5,
            color=INK_SECONDARY,
            ha="left",
            va="center",
        )
        figure.canvas.draw()
        box = label.get_window_extent().transformed(axis.transData.inverted())
        cursor = box.x1 + 0.4
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
