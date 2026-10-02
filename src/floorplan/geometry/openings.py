"""Find doors, windows and passages in each wall, and measure them.

For every wall of every room, each depth pixel of each frame taken inside that room is
asked one question: where does this pixel's line of sight meet the wall plane, and what did
the sensor report along it? The answer falls into one of four bins for that spot on the
wall:

* hit      the measured point lies on the wall (within 3 cm): the wall is solid there;
* open     the measured point lies well behind the wall: the ray went through a hole;
* blocked  the measured point lies in front of the wall: furniture hides that spot;
* void     the sensor returned nothing trustworthy: typical of glass and of open space
           beyond the sensor's range.

An opening is a compact region of the wall where see-through rays dominate (or, for glass,
where nothing came back and nothing was in the way). Keeping "blocked" separate is what stops
a wardrobe in front of a wall from looking like a doorway: nothing was seen on the wall
there, but nothing was seen *through* it either.

The width is the distance between the two jamb faces, the narrow surfaces lining the sides
of the opening. They are planes like any wall, so their position comes from a fit over many
points instead of from the ragged edge of a depth image. When a jamb face was not seen well
enough the edge of the open region is used instead and a wider uncertainty is reported.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np
import shapely

from floorplan.capture import Capture
from floorplan.geometry.cloud import Cloud, CloudConfig, trusted_pixels
from floorplan.geometry.layout import Room
from floorplan.geometry.planes import Level


@dataclass(frozen=True)
class OpeningConfig:
    cell: float = 0.02  # metres, resolution of the wall maps
    wall_band: float = 0.03  # a point this close to the wall plane is on the wall
    beyond: float = 0.08  # a point this far behind the wall plane was seen through a hole
    max_range: float = 4.5  # ignore wall spots farther than this from the camera
    level_clearance: float = 0.05  # points this close to the floor or ceiling are not wall
    pixel_stride: int = 2
    min_open_rays: int = 2
    min_void_rays: int = 3
    min_width: float = 0.40
    min_height: float = 0.40
    min_fill: float = 0.55  # share of the bounding rectangle the region must fill
    min_open_share: float = 0.10  # share of the region that must have see-through rays
    void_door_min_fill: float = 0.80  # how clean a rectangle a no-return doorway must be
    door_max_sill: float = 0.15
    door_min_height: float = 1.60
    jamb_search: float = 0.08  # metres either side of the region edge to look for a jamb face
    jamb_min_points: int = 12
    max_thickness: float = 0.45  # deepest wall a jamb face is searched in
    face_sigma: float = 0.004  # systematic floor on a jamb-face position, metres
    grid_sigma: float = 0.010  # systematic floor on a region-edge position, metres


@dataclass
class Opening:
    kind: str  # "door" | "window" | "passage"
    room: str
    edge: int  # index of the wall in the room's edge list
    u0: float  # metres along the wall from its first corner to the near jamb
    u1: float
    sill: float  # metres above the floor
    height: float
    width: float
    width_sigma: float
    method: str  # "jamb_faces" | "mixed" | "region_edge"
    centre: np.ndarray  # (2,) world position of the opening's middle on the wall face
    open_share: float
    evidence: str = "seen_through"  # "seen_through" | "no_return" (weaker: nothing came back)
    other_room: str | None = None
    wall_thickness: float | None = None
    id: str = ""


@dataclass
class _WallMap:
    room: Room
    edge: int
    p0: np.ndarray
    direction: np.ndarray
    inward: np.ndarray
    length: float
    height: float
    floor: Level
    hit: np.ndarray
    open: np.ndarray
    blocked: np.ndarray
    void: np.ndarray


def _wall_maps(
    rooms: list[Room], floors: dict[str, Level], heights: dict[str, float], config: OpeningConfig
) -> list[_WallMap]:
    maps = []
    for room in rooms:
        for index, edge in enumerate(room.edges):
            if edge.line is None or edge.length < config.min_width:
                continue
            nu = max(1, int(np.ceil(edge.length / config.cell)))
            nv = max(1, int(np.ceil(heights[room.name] / config.cell)))
            shape = (nv, nu)
            maps.append(
                _WallMap(
                    room=room,
                    edge=index,
                    p0=edge.p0,
                    direction=edge.direction,
                    inward=edge.inward,
                    length=edge.length,
                    height=heights[room.name],
                    floor=floors[room.name],
                    hit=np.zeros(shape, np.int32),
                    open=np.zeros(shape, np.int32),
                    blocked=np.zeros(shape, np.int32),
                    void=np.zeros(shape, np.int32),
                )
            )
    return maps


def _cast_frame(
    capture: Capture,
    i: int,
    walls: list[_WallMap],
    config: OpeningConfig,
    cloud_config: CloudConfig,
) -> None:
    """Sort every pixel of frame `i` into hit / open / blocked / void for each wall."""
    frame = capture.frames[i]
    depth = capture.depth(i)
    trusted = trusted_pixels(depth, capture.confidence(i), cloud_config)
    s = config.pixel_stride
    depth, trusted = depth[::s, ::s].astype(np.float64), trusted[::s, ::s]
    height, width = depth.shape
    K = frame.K
    u = (np.arange(width) * s - K[0, 2]) / K[0, 0]
    v = (np.arange(height) * s - K[1, 2]) / K[1, 1]
    rays_cam = np.stack(np.broadcast_arrays(u[None, :], v[:, None], 1.0), axis=-1).reshape(-1, 3)
    rays = rays_cam @ frame.T_world_cam[:3, :3].T  # world direction per unit of z-depth
    camera = frame.position
    depth, trusted = depth.reshape(-1), trusted.reshape(-1)

    for wall in walls:
        camera_distance = float((camera[:2] - wall.p0) @ wall.inward)
        if camera_distance < 0.05:
            continue
        approach = -(rays[:, :2] @ wall.inward)  # metres closer to the wall per unit depth
        reaches = approach > 1e-6
        depth_at_wall = np.zeros(len(rays))
        depth_at_wall[reaches] = camera_distance / approach[reaches]
        crossing = camera + depth_at_wall[:, None] * rays
        along = (crossing[:, :2] - wall.p0) @ wall.direction
        above = crossing[:, 2] - wall.floor.z_at(crossing[:, :2])
        on_wall = (
            reaches
            & (depth_at_wall < config.max_range)
            & (along >= 0)
            & (along < wall.length)
            & (above >= 0)
            & (above < wall.height)
        )
        if not on_wall.any():
            continue
        column = np.minimum((along / config.cell).astype(np.int64), wall.hit.shape[1] - 1)
        row = np.minimum((above / config.cell).astype(np.int64), wall.hit.shape[0] - 1)
        flat = row * wall.hit.shape[1] + column
        point_distance = camera_distance - depth * approach  # of the measured point; + is in front

        def vote(counter: np.ndarray, cells: np.ndarray) -> None:
            counter += np.bincount(cells, minlength=counter.size).reshape(counter.shape)

        # Open, blocked and void describe the line of sight, so they are recorded where the
        # ray crosses the wall plane.
        vote(wall.open, flat[on_wall & trusted & (point_distance < -config.beyond)])
        vote(wall.blocked, flat[on_wall & trusted & (point_distance > config.wall_band)])
        vote(wall.void, flat[on_wall & ~trusted])

        # A hit describes the surface itself, so it is recorded where the measured point is.
        # (A ray that skims along the wall crosses the plane far from the point it ends on;
        # recording hits at the crossing painted wall into doorways.) Points on the floor or
        # the ceiling are not wall, even where they touch the wall plane in a doorway.
        point = camera + depth[:, None] * rays
        own_along = (point[:, :2] - wall.p0) @ wall.direction
        own_above = point[:, 2] - wall.floor.z_at(point[:, :2])
        is_hit = (
            trusted
            & (np.abs(point_distance) <= config.wall_band)
            & (own_along >= 0)
            & (own_along < wall.length)
            & (own_above > config.level_clearance)
            & (own_above < wall.height - config.level_clearance)
        )
        own_column = np.minimum(
            (own_along[is_hit] / config.cell).astype(np.int64), wall.hit.shape[1] - 1
        )
        own_row = np.minimum(
            (own_above[is_hit] / config.cell).astype(np.int64), wall.hit.shape[0] - 1
        )
        vote(wall.hit, own_row * wall.hit.shape[1] + own_column)


def _weighted_median(values: np.ndarray, weights: np.ndarray) -> float:
    order = np.argsort(values)
    cumulative = np.cumsum(weights[order])
    return float(values[order][np.searchsorted(cumulative, cumulative[-1] / 2)])


def _jamb_face(
    wall: _WallMap,
    side_points: Cloud,
    u_edge: float,
    faces: float,
    v0: float,
    v1: float,
    config: OpeningConfig,
) -> tuple[float, float] | None:
    """Position along the wall of a jamb face near `u_edge`, and its 1-sigma.

    `faces` is +1 for the jamb whose surface looks toward increasing u, -1 for the other.
    """
    relative = side_points.xyz[:, :2] - wall.p0
    along = relative @ wall.direction
    across = relative @ wall.inward
    above = side_points.xyz[:, 2] - wall.floor.z_at(side_points.xyz[:, :2])
    facing = side_points.normal[:, :2] @ wall.direction
    margin = 0.15 * (v1 - v0)
    chosen = (
        (facing * faces > 0.8)
        & (np.abs(along - u_edge) < config.jamb_search)
        & (across > -config.max_thickness)
        & (across < 0.02)
        & (above > v0 + margin)
        & (above < v1 - margin)
    )
    if chosen.sum() < config.jamb_min_points:
        return None
    position = _weighted_median(along[chosen], side_points.weight[chosen])
    spread = 1.4826 * np.median(np.abs(along[chosen] - position))
    sigma = float(np.hypot(spread / np.sqrt(chosen.sum()), config.face_sigma))
    return position, sigma


def _region_edge(
    wall: _WallMap,
    is_open: np.ndarray,
    is_wall: np.ndarray,
    column: int,
    rows: range,
    leftward: bool,
    config: OpeningConfig,
) -> tuple[float, float]:
    """Jamb position from the wall maps: midway between the last wall cell and the first
    open cell, per row, then the median over rows."""
    reach = int(np.ceil(0.15 / config.cell))
    positions, gaps = [], []
    for r in rows:
        if leftward:
            inside = np.flatnonzero(is_open[r, max(0, column - 2) : column + reach])
            outside = np.flatnonzero(is_wall[r, max(0, column - reach) : column + 2])
            if len(inside) == 0 or len(outside) == 0:
                continue
            first_open = max(0, column - 2) + inside[0]
            last_wall = max(0, column - reach) + outside[-1] + 1
            positions.append((first_open + last_wall) / 2)
            gaps.append(first_open - last_wall)
        else:
            inside = np.flatnonzero(is_open[r, max(0, column - reach) : column + 3])
            outside = np.flatnonzero(is_wall[r, max(0, column - 1) : column + reach + 1])
            if len(inside) == 0 or len(outside) == 0:
                continue
            last_open = max(0, column - reach) + inside[-1] + 1
            first_wall = max(0, column - 1) + outside[0]
            positions.append((last_open + first_wall) / 2)
            gaps.append(first_wall - last_open)
    if not positions:
        # no wall cell next to the region on this side: fall back to the region border
        return (column if leftward else column + 1) * config.cell, 3 * config.grid_sigma
    position = float(np.median(positions)) * config.cell
    gap = max(0.0, float(np.median(gaps))) * config.cell
    spread = 1.4826 * np.median(np.abs(np.array(positions) * config.cell - position))
    sigma = np.sqrt((spread**2) / len(positions) + gap**2 / 12 + config.grid_sigma**2)
    return position, float(sigma)


def _measure(
    wall: _WallMap, side_points: Cloud, flat_points: Cloud, config: OpeningConfig
) -> list[Opening]:
    # A spot can collect different votes from different viewpoints (a doorway is hidden by a
    # chair from one place and seen clean through from another), so each state is decided
    # by which vote dominates, never by the mere presence of one vote.
    is_wall = (wall.hit >= 2) & (wall.hit >= wall.open)
    is_open = (wall.open >= config.min_open_rays) & ~is_wall
    is_void = (
        (wall.void >= config.min_void_rays) & ~is_wall & ~is_open & (wall.void > 2 * wall.blocked)
    )
    candidate = (is_open | is_void).astype(np.uint8)
    kernel = np.ones((3, 3), np.uint8)
    candidate = cv2.morphologyEx(candidate, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    candidate = cv2.morphologyEx(candidate, cv2.MORPH_OPEN, kernel)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(candidate, connectivity=4)

    openings = []
    for label in range(1, count):
        left, top, box_width, box_height, area = stats[label]
        if (
            box_width * config.cell < config.min_width
            or box_height * config.cell < config.min_height
        ):
            continue
        region = labels[top : top + box_height, left : left + box_width] == label
        # trim ragged borders: keep rows and columns that are at least half inside the region
        columns = np.flatnonzero(region.mean(axis=0) >= 0.5)
        rows = np.flatnonzero(region.mean(axis=1) >= 0.5)
        if len(columns) == 0 or len(rows) == 0:
            continue
        c0, c1 = left + columns[0], left + columns[-1]
        r0, r1 = top + rows[0], top + rows[-1]
        core = labels[r0 : r1 + 1, c0 : c1 + 1] == label
        width_cells, height_cells = c1 - c0 + 1, r1 - r0 + 1
        if (
            width_cells * config.cell < config.min_width
            or height_cells * config.cell < config.min_height
            or core.mean() < config.min_fill
        ):
            continue
        open_share = float(is_open[r0 : r1 + 1, c0 : c1 + 1][core].mean())
        v0, v1 = r0 * config.cell, (r1 + 1) * config.cell
        # A region nothing came back from is accepted only when it is a clean door-shaped
        # rectangle standing on the floor (a glass door, or a doorway onto a space beyond
        # the sensor's range). Elsewhere "nothing came back" is too easily a television or
        # a dark patch, so a window must show see-through rays around its reveal.
        door_shaped_void = (
            v0 <= config.door_max_sill
            and v1 - v0 >= config.door_min_height
            and core.mean() >= config.void_door_min_fill
        )
        if open_share < config.min_open_share and not door_shaped_void:
            continue
        evidence = "seen_through" if open_share >= config.min_open_share else "no_return"
        middle = range(r0 + int(0.2 * height_cells), r1 + 1 - int(0.2 * height_cells))
        left_edge = _region_edge(wall, candidate > 0, is_wall, c0, middle, True, config)
        right_edge = _region_edge(wall, candidate > 0, is_wall, c1, middle, False, config)
        left_face = _jamb_face(wall, side_points, left_edge[0], +1.0, v0, v1, config)
        right_face = _jamb_face(wall, side_points, right_edge[0], -1.0, v0, v1, config)
        u0, sigma0 = left_face or left_edge
        u1, sigma1 = right_face or right_edge
        faces_used = (left_face is not None) + (right_face is not None)
        method = {2: "jamb_faces", 1: "mixed", 0: "region_edge"}[faces_used]

        # head and sill from the horizontal faces lining the opening, when they were seen
        v1 = _level_face(wall, flat_points, u0, u1, v1, -1.0, config) or v1
        sill = 0.0
        if v0 > config.door_max_sill:
            # Rays through the bottom of a doorway end on the floor just behind the wall
            # plane, too close to count as seen-through, so a door's open region starts a
            # little above the floor. A window has solid wall right under it; a door has not.
            under = is_wall[max(0, r0 - 4) : r0, c0 : c1 + 1]
            if under.size and under.mean() < 0.5:
                v0 = 0.0
            else:
                sill = _level_face(wall, flat_points, u0, u1, v0, +1.0, config) or v0
        kind = _kind(sill, v1 - sill, v1, wall.height, config)

        middle_u = (u0 + u1) / 2
        openings.append(
            Opening(
                kind=kind,
                room=wall.room.name,
                edge=wall.edge,
                u0=float(u0),
                u1=float(u1),
                sill=float(sill),
                height=float(v1 - sill),
                width=float(u1 - u0),
                width_sigma=float(np.hypot(sigma0, sigma1)),
                method=method,
                centre=wall.p0 + middle_u * wall.direction,
                open_share=open_share,
                evidence=evidence,
            )
        )
    return openings


def _kind(
    sill: float, height: float, top: float, wall_height: float | None, config: OpeningConfig
) -> str:
    """Door, window or passage, from where the opening sits in the wall."""
    if sill > config.door_max_sill or height < config.door_min_height:
        return "window"  # includes a low hole that reaches the floor: reported, not as a door
    if wall_height is not None and top >= wall_height - 0.10:
        return "passage"  # open from floor to ceiling
    return "door"


def _level_face(
    wall: _WallMap,
    flat_points: Cloud,
    u0: float,
    u1: float,
    v_guess: float,
    facing_up: float,
    config: OpeningConfig,
) -> float | None:
    """Height of the head (facing down) or sill (facing up) face lining an opening."""
    relative = flat_points.xyz[:, :2] - wall.p0
    along = relative @ wall.direction
    across = relative @ wall.inward
    above = flat_points.xyz[:, 2] - wall.floor.z_at(flat_points.xyz[:, :2])
    chosen = (
        (flat_points.normal[:, 2] * facing_up > 0.8)
        & (along > u0 + 0.05)
        & (along < u1 - 0.05)
        & (across > -config.max_thickness)
        & (across < 0.02)
        & (np.abs(above - v_guess) < 0.10)
    )
    if chosen.sum() < config.jamb_min_points:
        return None
    return _weighted_median(above[chosen], flat_points.weight[chosen])


def find_openings(
    rooms: list[Room],
    floors: dict[str, Level],
    heights: dict[str, float],
    cloud: Cloud,
    capture: Capture,
    config: OpeningConfig | None = None,
    cloud_config: CloudConfig | None = None,
) -> list[Opening]:
    """Openings in every wall of every room, each measured and linked to the room behind."""
    config = config or OpeningConfig()
    cloud_config = cloud_config or CloudConfig()
    walls = _wall_maps(rooms, floors, heights, config)
    if not walls:
        return []

    camera_xy = np.array([frame.position[:2] for frame in capture.frames])
    for room in rooms:
        here = np.flatnonzero(shapely.contains_xy(room.polygon, camera_xy[:, 0], camera_xy[:, 1]))
        own = [wall for wall in walls if wall.room is room]
        for i in here:
            _cast_frame(capture, int(i), own, config, cloud_config)

    side_points = cloud.select(np.abs(cloud.normal[:, 2]) < 0.3)
    flat_points = cloud.select(np.abs(cloud.normal[:, 2]) > 0.8)
    openings: list[Opening] = []
    for wall in walls:
        openings.extend(_measure(wall, side_points, flat_points, config))

    _link_rooms(openings, rooms, config)
    openings = _merge_twins(openings, config)
    counters: dict[tuple[str, str], int] = {}
    for opening in openings:
        key = (opening.room, opening.kind)
        counters[key] = counters.get(key, 0) + 1
        prefix = {"door": "D", "window": "WIN", "passage": "P"}[opening.kind]
        opening.id = f"{opening.room}-{prefix}{counters[key]}"
    return openings


def _link_rooms(openings: list[Opening], rooms: list[Room], config: OpeningConfig) -> None:
    """Find the room on the far side of each opening and the wall thickness there."""
    by_name = {room.name: room for room in rooms}
    for opening in openings:
        outward = -by_name[opening.room].edges[opening.edge].inward
        for step in np.arange(0.06, config.max_thickness + 0.30, 0.03):
            probe = shapely.Point(opening.centre + step * outward)
            for room in rooms:
                if room.name != opening.room and room.polygon.contains(probe):
                    opening.other_room = room.name
                    opening.wall_thickness = float(
                        room.polygon.exterior.distance(shapely.Point(opening.centre))
                    )
                    break
            if opening.other_room is not None:
                break


def _merge_twins(openings: list[Opening], config: OpeningConfig) -> list[Opening]:
    """A door between two rooms is found once from each side; keep one record for it.

    The two width measurements are combined by inverse-variance weighting, which gives the
    better-seen side more say.
    """
    kept: list[Opening] = []
    used: set[int] = set()
    for i, a in enumerate(openings):
        if i in used:
            continue
        for j in range(i + 1, len(openings)):
            b = openings[j]
            if j in used or a.other_room != b.room or b.other_room != a.room:
                continue
            reach = (a.wall_thickness or 0.3) + 0.30
            if np.linalg.norm(a.centre - b.centre) > reach:
                continue
            wa, wb = 1 / a.width_sigma**2, 1 / b.width_sigma**2
            a.width = float((a.width * wa + b.width * wb) / (wa + wb))
            a.width_sigma = float(np.sqrt(1 / (wa + wb)))
            # one side often sees less of the opening's height than the other (furniture,
            # viewing angle); the opening is as tall as the taller of the two views
            top = max(a.sill + a.height, b.sill + b.height)
            a.sill = min(a.sill, b.sill)
            a.height = float(top - a.sill)
            a.kind = _kind(a.sill, a.height, top, None, config)
            a.method = a.method if a.method == b.method else "mixed"
            if "seen_through" in (a.evidence, b.evidence):
                a.evidence = "seen_through"
            used.add(j)
            break
        kept.append(a)
    return kept
