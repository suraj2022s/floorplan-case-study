"""Join rooms that were measured separately into one property plan.

At the photo tier every room is reconstructed in its own frame, from its own folder of
photos. Nothing ties the frames together except the doors: a door seen from inside the
bedroom and a door seen from the corridor are the same door. So the rooms are joined at
their doors.

1. Every door (or open passage) of every room is a candidate connection.
2. Two doors can be the same door only if their widths and heights agree within their
   uncertainty.
3. Joining two rooms at a pair of doors fixes where the second room goes: its door faces
   the first room's door, the two wall faces a wall's thickness apart, door centres in line.
4. All ways of joining the rooms into one connected plan are searched. A placement in which
   two rooms overlap is thrown out: rooms cannot occupy the same floor. Among the rest, the
   one whose door pairs agree best is kept.

A room that cannot be joined (no door found, or no door that matches) is still drawn, set
beside the others and flagged, because a plan with a room missing is worse than a plan with
a room in an uncertain place. It is never silently forced into a wrong position without
that flag.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from shapely.geometry import LineString, Polygon

from floorplan.capture import Frame
from floorplan.pipeline import OpeningResult, Plan, RoomResult, WallResult
from floorplan.uncertainty.budget import Measurement, quadrature

DEFAULT_WALL_THICKNESS = 0.15  # metres, when the depth of the door frame was not measured
MAX_OVERLAP = 0.05  # m2 two rooms may overlap before a placement is rejected
MAX_MISMATCH = 3.0  # in sigmas of door width and height
UNJOINED_PENALTY = 25.0


@dataclass
class _Door:
    room: int
    opening: OpeningResult
    centre: np.ndarray
    outward: np.ndarray  # unit, pointing out of the room through the door


@dataclass
class Placement:
    """Where a room sits in the property frame: p_property = R(theta) p_room + shift."""

    theta: float
    shift: np.ndarray

    def apply(self, points: np.ndarray) -> np.ndarray:
        c, s = np.cos(self.theta), np.sin(self.theta)
        return np.atleast_2d(points) @ np.array([[c, -s], [s, c]]).T + self.shift

    def turn(self, vector: np.ndarray) -> np.ndarray:
        c, s = np.cos(self.theta), np.sin(self.theta)
        return np.array([[c, -s], [s, c]]) @ vector


def _doors(plans: list[Plan]) -> list[_Door]:
    doors = []
    for index, plan in enumerate(plans):
        room = plan.rooms[0]
        walls = {wall.id: wall for wall in room.walls}
        for opening in plan.openings:
            if opening.kind not in ("door", "passage") or opening.wall not in walls:
                continue
            wall = walls[opening.wall]
            direction = (wall.end - wall.start) / max(np.linalg.norm(wall.end - wall.start), 1e-9)
            inward = np.array([-direction[1], direction[0]])  # rooms are counter-clockwise
            doors.append(_Door(index, opening, np.asarray(opening.centre, float), -inward))
    return doors


def _mismatch(a: _Door, b: _Door) -> float:
    """How unlikely it is that two doors are the same door, in squared sigmas."""
    width = (a.opening.width.value - b.opening.width.value) / quadrature(
        a.opening.width.sigma, b.opening.width.sigma, 0.02
    )
    height = (a.opening.height.value - b.opening.height.value) / quadrature(
        a.opening.height.sigma, b.opening.height.sigma, 0.03
    )
    return float(width**2 + height**2)


def _reach(outline: np.ndarray, start: np.ndarray, direction: np.ndarray) -> float | None:
    """How far a room's outline extends from `start` along `direction` (first exit)."""
    ray = LineString([start, start + 30.0 * direction])
    inside = ray.intersection(Polygon(outline))
    if inside.is_empty:
        return None
    pieces = getattr(inside, "geoms", [inside])
    ends = [
        max(float(np.linalg.norm(np.asarray(c) - start)) for c in piece.coords)
        for piece in pieces
        if piece.length > 0
    ]
    return min(ends) if ends else None


def _sees_through(door: _Door, door_place: Placement, room_outline: np.ndarray) -> bool:
    """Whether what was seen through a door agrees with the room placed behind it.

    Through a bedroom door one sees the corridor's far wall about 1.3 m behind it. Joining the
    bedroom straight to the living room would put a wall 4.5 m behind that door instead. The
    distance seen through the door must match how far the joined room reaches behind it,
    within 0.6 m or 40% (depth from images is loose, and the wall seen through a door may be
    furniture standing in front of the far wall).
    """
    seen = door.opening.depth_beyond
    if seen is None:
        return True
    start = door_place.apply(door.centre)[0]
    outward = door_place.turn(door.outward)
    reach = _reach(room_outline, start + 0.02 * outward, outward)
    if reach is None:
        return False
    return abs(seen - reach) <= max(0.6, 0.4 * reach)


def _join(placed: Placement, a: _Door, b: _Door, thickness: float) -> Placement:
    """Placement of b's room so that door b meets door a (whose room is at `placed`)."""
    out_a = placed.turn(a.outward)
    centre_a = placed.apply(a.centre)[0]
    # b's outward direction must point back at a's
    theta = np.arctan2(-out_a[1], -out_a[0]) - np.arctan2(b.outward[1], b.outward[0])
    turned = Placement(theta, np.zeros(2))
    shift = centre_a + out_a * thickness - turned.apply(b.centre)[0]
    return Placement(float(theta), shift)


def place_rooms(
    plans: list[Plan],
) -> tuple[list[Placement | None], list[tuple[int, int]], list[str]]:
    """Placement of every room, the door pairs used (indices into the door list), notes."""
    doors = _doors(plans)
    polygons = [Polygon(plan.rooms[0].polygon) for plan in plans]
    count = len(plans)
    order = sorted(
        range(count), key=lambda i: (-sum(d.room == i for d in doors), -polygons[i].area, i)
    )
    best: dict = {"cost": np.inf, "placements": None, "pairs": []}

    def overlap(index: int, placement: Placement, placements: dict[int, Placement]) -> bool:
        candidate = Polygon(placement.apply(np.asarray(polygons[index].exterior.coords)))
        for other, other_placement in placements.items():
            placed = Polygon(other_placement.apply(np.asarray(polygons[other].exterior.coords)))
            if candidate.intersection(placed).area > MAX_OVERLAP:
                return True
        return False

    def search(placements: dict[int, Placement], used: set[int], pairs: list, cost: float) -> None:
        remaining = [i for i in order if i not in placements]
        bound = cost + 0.0
        if bound >= best["cost"]:
            return
        extended = False
        for index in remaining:
            for b_id, b in enumerate(doors):
                if b.room != index or b_id in used:
                    continue
                for a_id, a in enumerate(doors):
                    if a.room not in placements or a_id in used:
                        continue
                    mismatch = _mismatch(a, b)
                    if mismatch > MAX_MISMATCH**2:
                        continue
                    thickness = (
                        a.opening.wall_thickness
                        or b.opening.wall_thickness
                        or DEFAULT_WALL_THICKNESS
                    )
                    placement = _join(placements[a.room], a, b, thickness)
                    if overlap(index, placement, placements):
                        continue
                    # what each door shows of the space behind it must fit the other room
                    outline_b = placement.apply(np.asarray(polygons[index].exterior.coords))
                    outline_a = placements[a.room].apply(
                        np.asarray(polygons[a.room].exterior.coords)
                    )
                    if not _sees_through(a, placements[a.room], outline_b) or not _sees_through(
                        b, placement, outline_a
                    ):
                        continue
                    extended = True
                    search(
                        {**placements, index: placement},
                        used | {a_id, b_id},
                        pairs + [(a_id, b_id)],
                        cost + mismatch,
                    )
            if extended:
                break  # this room has been tried in every way; other rooms come deeper down
        total = cost + UNJOINED_PENALTY * len(remaining)
        if total < best["cost"]:
            best.update(cost=total, placements=dict(placements), pairs=list(pairs))

    search({order[0]: Placement(0.0, np.zeros(2))}, set(), [], 0.0)

    placements: list[Placement | None] = [best["placements"].get(i) for i in range(count)]
    notes = []
    # rooms that could not be joined are set out in a row beside the plan, and flagged
    corners = [
        placements[i].apply(np.asarray(polygons[i].exterior.coords))
        for i in range(count)
        if placements[i] is not None
    ]
    cursor = float(np.concatenate(corners)[:, 0].max()) + 1.0
    base = float(np.concatenate(corners)[:, 1].min())
    for i in range(count):
        if placements[i] is None:
            x0, y0, x1, _ = polygons[i].bounds
            placements[i] = Placement(0.0, np.array([cursor - x0, base - y0]))
            cursor += (x1 - x0) + 1.0
            notes.append(
                f"{plans[i].rooms[0].id} could not be joined to the plan through a door; it is "
                "drawn beside the plan and its position is not measured"
            )
    return placements, best["pairs"], notes


def _move_room(room: RoomResult, placement: Placement) -> RoomResult:
    walls = [
        WallResult(
            wall.id,
            placement.apply(wall.start)[0],
            placement.apply(wall.end)[0],
            wall.length,
            wall.observed_share,
        )
        for wall in room.walls
    ]
    return RoomResult(
        room.id,
        placement.apply(room.polygon),
        walls,
        room.floor_area,
        room.ceiling_height,
        room.ceiling_height_range,
        room.entered,
        list(room.notes),
        room.floor_z,
    )


def stitch(plans: list[Plan]) -> Plan:
    """One property plan from single-room plans."""
    if len(plans) == 1:
        return plans[0]
    placements, pairs, notes = place_rooms(plans)
    doors = _doors(plans)
    rooms = [
        _move_room(plan.rooms[0], placement)
        for plan, placement in zip(plans, placements, strict=True)
    ]

    # the frames each room was built from, moved into the property frame with their room
    frames = []
    for plan, placement in zip(plans, placements, strict=True):
        move = np.eye(4)
        c, s = np.cos(placement.theta), np.sin(placement.theta)
        move[:2, :2] = [[c, -s], [s, c]]
        move[:2, 3] = placement.shift
        frames.extend(
            Frame(
                index=f.index,
                timestamp=f.timestamp,
                K=f.K,
                T_world_cam=move @ f.T_world_cam,
                name=f.name,
            )
            for f in plan.frames
        )

    twin_of = {b: a for a, b in pairs}
    openings: list[OpeningResult] = []
    door_ids = {id(door.opening): k for k, door in enumerate(doors)}
    for index, plan in enumerate(plans):
        for opening in plan.openings:
            door_index = door_ids.get(id(opening))
            if door_index in twin_of:
                continue  # the same door, already listed from the other room
            other, thickness, width = None, opening.wall_thickness, opening.width
            for a, b in pairs:
                if a == door_index:
                    twin = doors[b].opening
                    other = plans[doors[b].room].rooms[0].id
                    wa, wb = 1 / width.sigma**2, 1 / twin.width.sigma**2
                    width = Measurement(
                        (width.value * wa + twin.width.value * wb) / (wa + wb),
                        float(np.sqrt(1 / (wa + wb))),
                        width.basis,
                    )
                    thickness = thickness or DEFAULT_WALL_THICKNESS
            openings.append(
                OpeningResult(
                    id=opening.id,
                    kind=opening.kind,
                    room=opening.room,
                    wall=opening.wall,
                    other_room=other,
                    width=width,
                    height=opening.height,
                    sill=opening.sill,
                    position_along_wall=opening.position_along_wall,
                    wall_thickness=thickness,
                    centre=placements[index].apply(opening.centre)[0],
                    method=opening.method,
                    evidence=opening.evidence,
                )
            )

    footprint = sum(room.floor_area.value for room in rooms)
    scale = max(plan.footprint_area.sigma / max(plan.footprint_area.value, 1e-9) for plan in plans)
    warnings = sorted({w for plan in plans for w in plan.warnings}) + notes
    timings: dict[str, float] = {}
    for plan in plans:
        for stage, seconds in plan.timings.items():
            timings[stage] = round(timings.get(stage, 0.0) + seconds, 3)
    adjacency = sorted(
        (min(o.room, o.other_room), max(o.room, o.other_room), o.id)
        for o in openings
        if o.other_room is not None
    )
    return Plan(
        tier=plans[0].tier,
        rooms=rooms,
        openings=openings,
        # the rooms share one depth model and so one scale error: it does not average out
        footprint_area=Measurement(footprint, scale * footprint, unit="m2"),
        adjacency=adjacency,
        warnings=warnings,
        timings=timings,
        stats={
            "rooms": [plan.stats for plan in plans],
            "door_pairs": len(pairs),
            "scale_sigma": max(plan.stats.get("scale_sigma", 0.05) for plan in plans),
            "joined_by": "doors matched by width and height, overlaps rejected",
        },
        calibration=plans[0].calibration,
        frames=frames,
        images={name: loader for plan in plans for name, loader in plan.images.items()},
    )
