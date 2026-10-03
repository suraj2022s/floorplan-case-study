"""Photo tier: per-room folders of still images to one stitched property plan.

    capture/
        kitchen/   IMG_0101.HEIC  IMG_0102.HEIC ...
        bedroom/   ...

Each room is rebuilt on its own from its 2 to 8 photos (`views.py`, `room.py`), run through
the same back-end as every other tier, and the rooms are then joined at their doors
(`stitch.py`). A folder of images with no sub-folders is treated as a single room.

The depth of each photo comes from a learned model, so the metric scale of a whole room can
be off by a few percent and no amount of geometry inside the room can detect that. This is
the dominant uncertainty at this tier and it is carried into every interval.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

import numpy as np

from floorplan.frontend.room import RoomFit, _turn, fit_room, room_capture
from floorplan.frontend.views import LevelView, View, level_view
from floorplan.io.intake import IMAGE_SUFFIXES, room_folders
from floorplan.pipeline import (
    OpeningResult,
    PipelineConfig,
    Plan,
    RoomResult,
    WallResult,
    config_for,
    run,
)
from floorplan.stitch import stitch
from floorplan.uncertainty.budget import BUDGETS, Measurement, load_calibration, quadrature

PHOTO_SCALE_SIGMA = 0.06  # relative 1-sigma of the depth model's metric scale indoors (measured)
# Floor seen in the photos must land inside the room fitted to them. When more than this
# share lands more than FLOOR_MARGIN outside it, the photos do not fit the protocol and the
# room's size is not measured.
FLOOR_OUTSIDE_LIMIT = 0.15
FLOOR_MARGIN = 0.30  # metres


def _rename(plan: Plan, old: str, new: str) -> None:
    for room in plan.rooms:
        room.id = room.id.replace(old, new, 1)
        for wall in room.walls:
            wall.id = wall.id.replace(old, new, 1)
    for opening in plan.openings:
        opening.id = opening.id.replace(old, new, 1)
        opening.room = opening.room.replace(old, new, 1)
        opening.wall = opening.wall.replace(old, new, 1)


def floor_outside(fit: RoomFit, views: list[LevelView]) -> float:
    """Share of the floor the photos show that the fitted room cannot contain.

    The rectangle fit places each photo where the protocol says it was taken (back to the
    middle of a wall). If the photos were taken some other way, the fit still returns a
    rectangle, but the floor each photo shows, placed by that fit, spills outside it. That is
    the check: it needs no ground truth, and it catches photos taken from the middle of the
    room, close-ups, and a wrong walking order.
    """
    total = outside = 0
    used = getattr(fit, "used", list(range(len(fit.quarters))))
    for k, index in enumerate(used):
        if views[index].floor is None:
            continue  # no floor in this photo: its height is assumed, not seen
        points = views[index].points
        floor = points[np.abs(points[:, 2]) < 0.06] if len(points) else points
        # floor beyond a wall this photo sees was seen through a door or window: not this room
        for wall in views[index].walls:
            floor = floor[wall.distance(floor[:, :2]) > -0.10] if len(floor) else floor
        if not len(floor):
            continue
        xy = fit.positions[k] + fit.scales[k] * (floor[:, :2] @ _turn(fit.quarters[k]).T)
        beyond = (
            (xy[:, 0] < -FLOOR_MARGIN)
            | (xy[:, 0] > fit.width + FLOOR_MARGIN)
            | (xy[:, 1] < -FLOOR_MARGIN)
            | (xy[:, 1] > fit.depth + FLOOR_MARGIN)
        )
        total += len(floor)
        outside += int(beyond.sum())
    return outside / total if total else 0.0


def sides_seen(fit: RoomFit, views: list[LevelView]) -> set[int]:
    """Which sides of the fitted rectangle (0 S, 1 N, 2 W, 3 E) some photo saw directly.

    A side no photo saw is placed by the protocol's assumption alone (the photographer's
    back against it), so the room's size along that direction was not measured.
    """
    seen: set[int] = set()
    used = getattr(fit, "used", list(range(len(fit.quarters))))
    directions = [
        np.array([0.0, 1.0]),
        np.array([0.0, -1.0]),
        np.array([1.0, 0.0]),
        np.array([-1.0, 0.0]),
    ]
    for k, index in enumerate(used):
        turn = _turn(fit.quarters[k])
        for wall in views[index].walls:
            normal = turn @ wall.normal
            side = max(range(4), key=lambda i: float(directions[i] @ normal))
            if directions[side] @ normal >= np.cos(np.radians(25.0)):
                seen.add(side)
    return seen


def _rectangle_plan(
    name: str,
    fit: RoomFit,
    views: list[LevelView],
    notes: list[str],
    capture=None,
    measured: bool = True,
) -> Plan:
    """The fallback when the back-end cannot close a room from the photos: the rectangle the
    views were fitted to, with every wall marked as inferred and wide intervals.

    With `measured=False` the photos did not fit the protocol (see `floor_outside`): the room
    is drawn so the plan still shows it, but its walls and area are reported as not measured.
    """
    budget = BUDGETS["photo"]
    calibration = load_calibration("photo")
    corners = np.array([[0, 0], [fit.width, 0], [fit.width, fit.depth], [0, fit.depth]], float)
    lengths = [fit.width, fit.depth, fit.width, fit.depth]
    walls = []
    for k in range(4):
        sigma = quadrature(budget.inferred_sigma / 2, PHOTO_SCALE_SIGMA * lengths[k], fit.rms)
        walls.append(
            WallResult(
                f"{name}-W{k + 1}",
                corners[k],
                corners[(k + 1) % 4],
                Measurement(lengths[k], sigma * calibration.factor("wall_length"), "inferred"),
                0.0,
            )
        )
    heights = [v.ceiling_height for v in views if v.ceiling_height is not None]
    height = float(np.median(heights)) if heights else float("nan")
    area = fit.width * fit.depth
    if not measured:
        for wall in walls:
            wall.length = Measurement(float("nan"), float("nan"), "inferred")
        area = float("nan")
    room = RoomResult(
        id=name,
        polygon=corners,
        walls=walls,
        floor_area=Measurement(
            area,
            quadrature(2 * PHOTO_SCALE_SIGMA * area, fit.depth * walls[0].length.sigma),
            "inferred",
            unit="m2",
        ),
        ceiling_height=Measurement(height, quadrature(0.05, PHOTO_SCALE_SIGMA * 2.6), "inferred"),
        ceiling_height_range=(height, height),
        entered=True,
        notes=notes
        + [
            "walls could not be traced from the photos; the room is drawn as the "
            "rectangle that best fits the walls that were seen"
            if measured
            else "the photos do not fit one room taken by the protocol, so its size was not "
            "measured; the outline is only a sketch"
        ],
    )
    return Plan(
        tier="photo",
        rooms=[room],
        openings=[],
        footprint_area=Measurement(area, room.floor_area.sigma, "inferred", unit="m2"),
        adjacency=[],
        warnings=[
            f"{name}: rectangle fallback used"
            if measured
            else f"{name}: the photos do not show the room the way the capture protocol "
            "asks (" + "; ".join(notes[-2:]) + "), so its walls and area were not measured. "
            "Retake them: back against the middle of each wall, photographing the opposite wall."
        ],
        timings={},
        stats={"fallback": "rectangle", "scale_sigma": PHOTO_SCALE_SIGMA},
        calibration=calibration,
        frames=[] if capture is None else list(capture.frames),
        images={} if capture is None else dict(capture.images),
    )


def room_plan(name: str, views: list[View], config: PipelineConfig | None = None) -> Plan:
    """A single-room plan from the views of one room."""
    config = config or config_for("photo")
    levelled = []
    notes: list[str] = []
    for view in views:
        try:
            levelled.append(level_view(view))
        except ValueError as problem:
            notes.append(str(problem))
    if not levelled:
        raise ValueError(f"{name}: none of the photos gave usable depth")
    fit = fit_room(levelled)
    notes += fit.notes + [note for view in levelled for note in view.notes]
    capture = room_capture(levelled, fit, name, scale_sigma=PHOTO_SCALE_SIGMA)
    spill = floor_outside(fit, levelled)
    seen = sides_seen(fit, levelled)
    if spill > FLOOR_OUTSIDE_LIMIT or len(seen) < 4:
        if spill > FLOOR_OUTSIDE_LIMIT:
            notes.append(f"{spill:.0%} of the floor the photos show lies outside the fitted room")
        if len(seen) < 4:
            notes.append(f"only {len(seen)} of the room's 4 walls appear in the photos")
        plan = _rectangle_plan(name, fit, levelled, notes, capture, measured=False)
        plan.stats["floor_outside"] = round(spill, 3)
        plan.stats["walls_seen"] = len(seen)
        return plan

    try:
        plan = run(capture, config)
    except RuntimeError as problem:
        return _rectangle_plan(name, fit, levelled, notes + [str(problem)], capture)
    if plan.stats.get("closure") == "fallback":
        # The walls seen do not close a room. The rectangle the views were fitted to is a
        # better stand-in than the box around what was observed, because it also accounts
        # for the wall behind the photographer, which no photo shows.
        return _rectangle_plan(name, fit, levelled, notes, capture)

    # keep the room the photos were taken in; anything else was seen through a doorway
    cameras = np.array([frame.position[:2] for frame in capture.frames])
    from shapely.geometry import Point, Polygon

    def cameras_inside(room: RoomResult) -> int:
        polygon = Polygon(room.polygon)
        return sum(polygon.contains(Point(c)) for c in cameras)

    main = max(plan.rooms, key=lambda room: (cameras_inside(room), room.floor_area.value))
    kept_openings = [o for o in plan.openings if o.room == main.id]
    for opening in kept_openings:
        opening.other_room = None  # neighbours are assigned when the rooms are joined
    plan = replace(
        plan, rooms=[main], openings=kept_openings, adjacency=[], footprint_area=main.floor_area
    )
    main.notes = list(main.notes) + notes
    plan.stats["floor_outside"] = round(spill, 3)
    plan.stats["room_fit"] = {
        "width_m": round(fit.width, 3),
        "depth_m": round(fit.depth, 3),
        "rms_m": round(fit.rms, 4),
        "views_used": len(fit.quarters),
        "views_given": len(views),
        "scales": [round(float(s), 4) for s in fit.scales],
    }
    _rename(plan, main.id, name)
    return plan


def photo_plan(
    capture: Path,
    depth_provider: Callable[[Path], View],
    config: PipelineConfig | None = None,
) -> Plan:
    """The stitched property plan for a photo capture."""
    plans = []
    failed = []
    for name, files in room_folders(capture).items():
        views = [depth_provider(path) for path in files]
        try:
            plans.append(room_plan(name, views, config))
        except ValueError as problem:
            failed.append(f"{name}: {problem}")
    if not plans:
        raise RuntimeError("no room could be rebuilt from the photos: " + "; ".join(failed))
    plan = stitch(plans)
    plan.warnings.extend(failed)
    return plan


__all__ = ["IMAGE_SUFFIXES", "OpeningResult", "photo_plan", "room_folders", "room_plan"]
