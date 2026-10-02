"""From wall faces to rooms.

Every wall face found in the cloud is extended into an infinite line. Together the lines cut
the floor plane into cells (a "cell complex"). Each cell is then labelled inside or outside,
and inside cells are glued together across cell borders that have no wall on them. What is
left is one polygon per room, whose corners are exact intersections of fitted wall lines.

Why do it this way instead of tracing the edge of the observed floor? Because furniture
hides the bottom of walls and the floor outline follows the furniture. Here a wall only
needs to be seen somewhere along its length and height; the line supplies the rest.

A cell is inside when either
* enough of it has ceiling above it, floor (or a bed or table top) in it, or the phone
  itself passed through it; or
* a wall face looks into it. Wall faces are only ever seen from inside a room, so the side
  a wall faces is inside even if a wardrobe hides everything else there.

A border between two inside cells is a wall when at least 15% of its length has real wall
on it. A doorway does not join two rooms, because the wall beside and above the door is
still there. A line that merely passes through a room has no wall on it, so the cells on
both sides join into one room.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np
import shapely
from shapely.geometry import LineString, Polygon
from shapely.geometry.polygon import orient
from shapely.ops import polygonize, unary_union
from shapely.strtree import STRtree

from floorplan.geometry.cloud import Cloud
from floorplan.geometry.planes import SUPPORT_BIN, Level, WallLine, refit_stretch


@dataclass(frozen=True)
class LayoutConfig:
    grid: float = 0.05  # metres, resolution of the inside-evidence map
    inside_share: float = 0.5  # share of a cell that must show evidence of being inside
    facing_length: float = 0.30  # metres of wall looking into a cell that make it inside
    wall_share: float = 0.15  # share of a border that must be wall to separate two rooms
    opening_reach: float = 3.0  # metres; wall within this on both sides makes a gap an opening
    min_shared: float = 0.05  # metres; shorter borders between cells are ignored
    min_room_area: float = 1.0  # m2
    max_jog: float = 0.12  # metres; a shorter step between two parallel walls is noise
    keep_unentered: bool = False  # report rooms that were only seen through a doorway
    furniture_area: float = 2.5  # m2; smaller regions nobody walked into are furniture
    margin: float = 0.6  # metres added around the wall points for the working area
    ceiling_min_height: float = 1.9
    floor_max_height: float = 1.2
    person_radius: float = 0.25
    evidence_min_points: int = 2


@dataclass
class RoomEdge:
    """One wall of a room, as a segment of the room polygon (counter-clockwise order)."""

    p0: np.ndarray
    p1: np.ndarray
    line: WallLine | None  # the fitted wall face; None when nothing was seen there
    coverage: float  # share of the edge's length where wall was actually seen

    @property
    def length(self) -> float:
        return float(np.linalg.norm(self.p1 - self.p0))

    @property
    def direction(self) -> np.ndarray:
        return (self.p1 - self.p0) / max(self.length, 1e-12)

    @property
    def inward(self) -> np.ndarray:
        """Unit normal pointing into the room (the interior is on the left of each edge)."""
        d = self.direction
        return np.array([-d[1], d[0]])


@dataclass
class Room:
    name: str
    polygon: Polygon
    edges: list[RoomEdge]
    entered: bool  # the phone was carried into this room
    cells: int = 0
    notes: list[str] = field(default_factory=list)

    @property
    def area(self) -> float:
        return float(self.polygon.area)


def _evidence_map(
    cloud: Cloud,
    floor: Level,
    camera_xy: np.ndarray,
    bounds: tuple[float, float, float, float],
    config: LayoutConfig,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Top-down boolean map of places known to be inside, with its cell-centre coordinates."""
    x0, y0, x1, y1 = bounds
    nx = int(np.ceil((x1 - x0) / config.grid))
    ny = int(np.ceil((y1 - y0) / config.grid))
    evidence = np.zeros((ny, nx), dtype=bool)

    height = cloud.xyz[:, 2] - floor.z_at(cloud.xyz[:, :2])
    ceiling_like = (cloud.normal[:, 2] < -0.9) & (height > config.ceiling_min_height)
    floor_like = (cloud.normal[:, 2] > 0.9) & (height < config.floor_max_height)
    points = cloud.xyz[ceiling_like | floor_like, :2]
    ix = ((points[:, 0] - x0) / config.grid).astype(int)
    iy = ((points[:, 1] - y0) / config.grid).astype(int)
    ok = (ix >= 0) & (ix < nx) & (iy >= 0) & (iy < ny)
    counts = np.bincount(iy[ok] * nx + ix[ok], minlength=nx * ny).reshape(ny, nx)
    # A cell needs more than a stray point, and the one-cell fringe along every wall is
    # dropped: noisy floor and ceiling points spill a centimetre or two into the wall, which
    # is enough to make the 12 cm sliver between two rooms look like floor.
    seen = (counts >= config.evidence_min_points).astype(np.uint8)
    evidence = cv2.erode(seen, np.ones((3, 3), np.uint8)).astype(bool)

    xs = x0 + (np.arange(nx) + 0.5) * config.grid
    ys = y0 + (np.arange(ny) + 0.5) * config.grid
    reach = int(np.ceil(config.person_radius / config.grid))
    for cx, cy in camera_xy[:: max(1, len(camera_xy) // 2000)]:
        i = int((cx - x0) / config.grid)
        j = int((cy - y0) / config.grid)
        evidence[max(0, j - reach) : j + reach + 1, max(0, i - reach) : i + reach + 1] = True
    return evidence, xs, ys


def _cell_share(cell: Polygon, evidence: np.ndarray, xs: np.ndarray, ys: np.ndarray) -> float:
    """Share of the evidence-map cells inside `cell` that are marked inside."""
    x0, y0, x1, y1 = cell.bounds
    i0, i1 = np.searchsorted(xs, [x0, x1])
    j0, j1 = np.searchsorted(ys, [y0, y1])
    if i1 <= i0 or j1 <= j0:
        return 0.0
    gx, gy = np.meshgrid(xs[i0:i1], ys[j0:j1])
    within = shapely.contains_xy(cell, gx, gy)
    if not within.any():
        return 0.0
    return float(evidence[j0:j1, i0:i1][within].mean())


def _line_of(a: np.ndarray, b: np.ndarray, lines: list[WallLine]) -> int | None:
    """Index of the wall line a segment lies on, or None for the working-area border."""
    best, best_error = None, 1e-4
    for index, line in enumerate(lines):
        error = abs(line.distance(a)[0]) + abs(line.distance(b)[0])
        if error < best_error:
            best, best_error = index, error
    return best


def _coverage(a: np.ndarray, b: np.ndarray, line: WallLine | None) -> float:
    if line is None:
        return 0.0
    return line.coverage(float(line.along(a)[0]), float(line.along(b)[0]))


def _gap_in_wall(a: np.ndarray, b: np.ndarray, line: WallLine | None, reach: float) -> bool:
    """Whether the stretch a-b of a wall line is a gap in a wall: an opening.

    It is when real wall was seen on the line on both sides of the stretch, within `reach`:
    a doorway, a window or a passage has wall to its left and to its right. The extension
    of a line beyond the end of its wall (across the open floor of an L-shaped room, say)
    has wall on one side only, and is not a gap.
    """
    if line is None or len(line.supported_bins) == 0:
        return False
    t0, t1 = sorted((float(line.along(a)[0]), float(line.along(b)[0])))
    seen = (line.supported_bins + 0.5) * SUPPORT_BIN
    before = np.any((seen <= t0 + SUPPORT_BIN) & (seen >= t0 - reach))
    after = np.any((seen >= t1 - SUPPORT_BIN) & (seen <= t1 + reach))
    return bool(before and after)


def _segments(geometry) -> list[tuple[np.ndarray, np.ndarray]]:
    """Straight pieces of a (multi)line geometry as endpoint pairs."""
    if geometry.is_empty:
        return []
    parts = getattr(geometry, "geoms", [geometry])
    out = []
    for part in parts:
        if part.geom_type != "LineString":
            continue
        coordinates = np.asarray(part.coords)
        for a, b in zip(coordinates[:-1], coordinates[1:], strict=True):
            out.append((a, b))
    return out


class _UnionFind:
    def __init__(self, items: list[int]) -> None:
        self.parent = {i: i for i in items}

    def find(self, i: int) -> int:
        while self.parent[i] != i:
            self.parent[i] = self.parent[self.parent[i]]
            i = self.parent[i]
        return i

    def union(self, i: int, j: int) -> None:
        self.parent[self.find(i)] = self.find(j)


def find_rooms(
    cloud: Cloud,
    lines: list[WallLine],
    floor: Level,
    camera_xy: np.ndarray,
    config: LayoutConfig | None = None,
) -> list[Room]:
    """Room polygons from wall lines, inside evidence and the phone's path."""
    config = config or LayoutConfig()
    if len(lines) < 3:
        return []

    wall_xy = np.concatenate([line.points_xy for line in lines])
    x0, y0 = wall_xy.min(axis=0) - config.margin
    x1, y1 = wall_xy.max(axis=0) + config.margin
    bounds = (float(x0), float(y0), float(x1), float(y1))
    border = shapely.box(*bounds)
    reach = float(np.hypot(x1 - x0, y1 - y0)) + 1.0
    centre = np.array([(x0 + x1) / 2, (y0 + y1) / 2])

    # 1. cut the working area into cells with every wall line, extended end to end
    cutters = [border.exterior]
    for line in lines:
        middle = line.point(float(line.along(centre)[0]))
        a, b = middle - reach * line.direction, middle + reach * line.direction
        clipped = LineString([a, b]).intersection(border)
        if not clipped.is_empty:
            cutters.append(clipped)
    cells = [cell for cell in polygonize(unary_union(cutters)) if cell.area > 1e-6]

    # 2. borders between neighbouring cells, each with the wall line it lies on, and whether
    #    it is a gap in a wall (an opening) rather than open floor
    tree = STRtree(cells)
    borders: list[tuple[int, int, float, float, int | None]] = []  # i, j, length, coverage, line
    gaps: list[bool] = []
    faced = np.zeros(len(cells))  # metres of wall face looking into each cell
    for i, cell in enumerate(cells):
        for j in tree.query(cell, predicate="touches"):
            j = int(j)
            if j <= i:
                continue
            for a, b in _segments(cell.boundary.intersection(cells[j].boundary)):
                length = float(np.linalg.norm(b - a))
                if length < config.min_shared:
                    continue
                index = _line_of(a, b, lines)
                line = None if index is None else lines[index]
                coverage = _coverage(a, b, line)
                borders.append((i, j, length, coverage, index))
                gaps.append(_gap_in_wall(a, b, line, config.opening_reach))
                if index is not None and coverage > 0:
                    line = lines[index]
                    side_i = line.distance(np.array(cells[i].representative_point().coords[0]))[0]
                    faced[i if side_i > 0 else j] += coverage * length

    # 3. inside or outside
    evidence, xs, ys = _evidence_map(cloud, floor, camera_xy, bounds, config)
    share = np.array([_cell_share(cell, evidence, xs, ys) for cell in cells])
    on_border = np.array([cell.boundary.intersects(border.exterior) for cell in cells])
    inside = ((share >= config.inside_share) | (faced >= config.facing_length)) & ~on_border

    # 4. glue inside cells across borders that carry no wall. A gap in a wall is not such a
    #    border: it is an opening, and the space seen through it is another space
    groups = _UnionFind([i for i in range(len(cells)) if inside[i]])
    for (i, j, _, coverage, _), gap in zip(borders, gaps, strict=True):
        if inside[i] and inside[j] and coverage < config.wall_share and not gap:
            groups.union(i, j)

    def members_of() -> dict[int, list[int]]:
        out: dict[int, list[int]] = {}
        for i in np.flatnonzero(inside):
            out.setdefault(groups.find(int(i)), []).append(int(i))
        return out

    camera_points = shapely.points(camera_xy[:: max(1, len(camera_xy) // 2000)])

    def entered(cell_ids: list[int]) -> bool:
        region = unary_union([cells[k] for k in cell_ids])
        return bool(shapely.contains(region, camera_points).any())

    # 5. a small region nobody walked into is the footprint of tall furniture: the wall
    #    behind it is real, so give the region back to the room it borders most
    while True:
        members = members_of()
        merged_any = False
        for root, cell_ids in sorted(members.items(), key=lambda kv: (len(kv[1]), kv[0])):
            area = sum(cells[k].area for k in cell_ids)
            if area >= config.furniture_area or entered(cell_ids):
                continue
            shared: dict[int, float] = {}
            for (i, j, length, _, _), gap in zip(borders, gaps, strict=True):
                if not (inside[i] and inside[j]) or gap:
                    continue
                ri, rj = groups.find(i), groups.find(j)
                if ri == root and rj != root:
                    shared[rj] = shared.get(rj, 0.0) + length
                elif rj == root and ri != root:
                    shared[ri] = shared.get(ri, 0.0) + length
            if shared:
                groups.union(root, max(sorted(shared), key=lambda r: shared[r]))
                merged_any = True
                break
        if not merged_any:
            break

    # 6. one polygon per room
    rooms: list[Room] = []
    for cell_ids in members_of().values():
        region = unary_union([cells[k] for k in cell_ids])
        if region.geom_type == "MultiPolygon":
            region = max(region.geoms, key=lambda g: g.area)
        if region.area < config.min_room_area:
            continue
        polygon = orient(Polygon(region.exterior).simplify(1e-6), sign=1.0)
        polygon = _remove_jogs(polygon, config.max_jog)
        rooms.append(
            Room(
                name="",
                polygon=polygon,
                edges=_edges(polygon, lines),
                entered=entered(cell_ids),
                cells=len(cell_ids),
            )
        )

    # A space glimpsed through a doorway but never walked into has walls that were mostly
    # not seen; any dimensions for it would be guesses. It is left out, and said so.
    if not config.keep_unentered and any(room.entered for room in rooms):
        skipped = [room for room in rooms if not room.entered]
        rooms = [room for room in rooms if room.entered]
        if skipped:
            rooms[0].notes.append(
                f"{len(skipped)} space(s) seen through an opening were not walked into and "
                "are not measured"
            )

    # name rooms in the order the phone first walked into them, so reruns agree
    def first_visit(room: Room) -> tuple[int, float]:
        hits = np.flatnonzero(shapely.contains(room.polygon, shapely.points(camera_xy)))
        return (int(hits[0]) if len(hits) else len(camera_xy), -room.area)

    rooms.sort(key=first_visit)
    for number, room in enumerate(rooms, start=1):
        room.name = f"room_{number}"
    return rooms


def _remove_jogs(polygon: Polygon, max_jog: float) -> Polygon:
    """Straighten a wall that is drawn as two parallel pieces joined by a tiny step.

    Clutter near a wall, or one wall found as two lines a few centimetres apart, leaves a
    step of a few centimetres in the outline. A step shorter than `max_jog` between two
    near-parallel edges is removed: the longer edge's line is kept and the next corner is
    recomputed on it. A real pilaster or chimney breast projects further and is kept.
    """

    def crossing(p, d, q, e):
        """Intersection of the line through p along d with the line through q along e."""
        denominator = d[0] * e[1] - d[1] * e[0]
        if abs(denominator) < 1e-6:
            return None
        s = ((q[0] - p[0]) * e[1] - (q[1] - p[1]) * e[0]) / denominator
        return p + s * d

    points = [np.array(c) for c in list(polygon.exterior.coords)[:-1]]
    for _ in range(40):
        count = len(points)
        if count <= 4:
            break
        changed = False
        for k in range(count):
            a, b, c, d = (points[(k + i) % count] for i in range(-1, 3))
            jog = np.linalg.norm(c - b)
            before, after = b - a, d - c
            if jog >= max_jog or np.linalg.norm(before) < 1e-9 or np.linalg.norm(after) < 1e-9:
                continue
            u, v = before / np.linalg.norm(before), after / np.linalg.norm(after)
            if abs(u[0] * v[1] - u[1] * v[0]) > np.sin(np.radians(8.0)) or u @ v < 0:
                continue
            if np.linalg.norm(before) >= np.linalg.norm(after):
                # keep the earlier wall's line; move the far end of the later one onto it
                e = points[(k + 3) % count] - d
                corner = crossing(a, u, d, e) if np.linalg.norm(e) > 1e-9 else None
                if corner is None:
                    continue
                points[(k + 2) % count] = corner
            else:
                e = a - points[(k - 2) % count]
                corner = crossing(d, v, a, e) if np.linalg.norm(e) > 1e-9 else None
                if corner is None:
                    continue
                points[(k - 1) % count] = corner
            drop = {k % count, (k + 1) % count}
            points = [p for i, p in enumerate(points) if i not in drop]
            changed = True
            break
        if not changed:
            break
    cleaned = orient(Polygon(points), sign=1.0)
    if not cleaned.is_valid or abs(cleaned.area - polygon.area) > 0.05 * polygon.area:
        return polygon
    return cleaned


def _edges(polygon: Polygon, lines: list[WallLine]) -> list[RoomEdge]:
    coordinates = np.asarray(polygon.exterior.coords)[:-1]
    edges = []
    for k in range(len(coordinates)):
        a, b = coordinates[k], coordinates[(k + 1) % len(coordinates)]
        index = _line_of(a, b, lines)
        line = None if index is None else lines[index]
        edges.append(RoomEdge(a.copy(), b.copy(), line, _coverage(a, b, line)))
    return edges


def fallback_room(
    cloud: Cloud,
    lines: list[WallLine],
    floor: Level,
    camera_xy: np.ndarray,
    config: LayoutConfig | None = None,
) -> Room | None:
    """A room for a capture whose walls do not close: the rectangle around what was seen.

    Used only when the cell complex finds no closed room, which means at least one wall was
    never captured. The rectangle is laid along the dominant wall direction and around the
    floor and ceiling that were observed and the path the camera took. A side that has a
    captured wall near it takes that wall's position; a side that does not is drawn where
    the observations stop and is marked as not seen, so it carries a wide interval.
    """
    config = config or LayoutConfig()
    height = cloud.xyz[:, 2] - floor.z_at(cloud.xyz[:, :2])
    seen = ((cloud.normal[:, 2] < -0.9) & (height > config.ceiling_min_height)) | (
        (cloud.normal[:, 2] > 0.9) & (height < config.floor_max_height)
    )
    points = np.concatenate([cloud.xyz[seen, :2], camera_xy])
    if len(points) < 50:
        return None
    angle = 0.0
    if lines:
        strongest = max(lines, key=lambda line: line.count)
        angle = (np.arctan2(strongest.normal[1], strongest.normal[0]) + np.pi / 4) % (
            np.pi / 2
        ) - np.pi / 4
    c, s = np.cos(angle), np.sin(angle)
    to_room = np.array([[c, s], [-s, c]])  # world -> rectangle axes
    local = points @ to_room.T
    low, high = np.percentile(local, 1, axis=0), np.percentile(local, 99, axis=0)
    if np.any(high - low < 0.5):
        return None

    # sides in counter-clockwise order: south, east, north, west, each with its inward normal
    sides = [
        (np.array([0.0, 1.0]), low[1]),
        (np.array([-1.0, 0.0]), -high[0]),
        (np.array([0.0, -1.0]), -high[1]),
        (np.array([1.0, 0.0]), low[0]),
    ]
    chosen: list[WallLine | None] = []
    offsets = []
    for inward, offset in sides:
        best = None
        for line in lines:
            normal = to_room @ line.normal
            if normal @ inward > np.cos(np.radians(15.0)) and abs(line.offset - offset) < 0.6:
                if best is None or line.count > best.count:
                    best = line
        chosen.append(best)
        offsets.append(best.offset if best is not None else offset)
    south, east, north, west = offsets
    x0, x1, y0, y1 = west, -east, south, -north
    if x1 - x0 < 0.5 or y1 - y0 < 0.5:
        return None
    corners = np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y1]]) @ to_room
    polygon = orient(Polygon(corners), sign=1.0)
    corners = np.asarray(polygon.exterior.coords)[:-1]
    edges = []
    for k in range(4):
        a, b = corners[k], corners[(k + 1) % 4]
        direction = (b - a) / max(np.linalg.norm(b - a), 1e-9)
        inward = np.array([-direction[1], direction[0]])
        line = next((ln for ln in chosen if ln is not None and ln.normal @ inward > 0.9), None)
        edges.append(RoomEdge(a.copy(), b.copy(), line, _coverage(a, b, line)))
    seen_sides = sum(edge.line is not None for edge in edges)
    return Room(
        name="room_1",
        polygon=polygon,
        edges=edges,
        entered=True,
        notes=[
            f"the walls captured do not close a room: {4 - seen_sides} of 4 sides were not "
            "seen and are drawn where the observations stop"
        ],
    )


def refine_room(room: Room) -> Room:
    """Refit each wall on its own stretch of points and rebuild the corners.

    The cell complex decides which walls a room has. This step sets where they are: each
    wall is refitted using only the points between its two corners, and each corner is
    recomputed as the intersection of its two refitted walls.
    """
    fitted: list[WallLine | None] = []
    for edge in room.edges:
        if edge.line is None:
            fitted.append(None)
            continue
        t0, t1 = float(edge.line.along(edge.p0)[0]), float(edge.line.along(edge.p1)[0])
        fitted.append(refit_stretch(edge.line, t0, t1))

    count = len(room.edges)
    corners = []
    for k in range(count):
        before, after = fitted[k - 1], fitted[k]
        corner = room.edges[k].p0
        if before is not None and after is not None:
            A = np.stack([before.normal, after.normal])
            if abs(np.linalg.det(A)) > 0.1:  # skip near-parallel pairs: no stable crossing
                candidate = np.linalg.solve(A, np.array([before.offset, after.offset]))
                if np.linalg.norm(candidate - corner) < 0.25:
                    corner = candidate
        corners.append(corner)

    polygon = orient(Polygon(corners), sign=1.0)
    if not polygon.is_valid or polygon.area < 0.5 * room.polygon.area:
        return room
    edges = [
        RoomEdge(corners[k], corners[(k + 1) % count], fitted[k], room.edges[k].coverage)
        for k in range(count)
    ]
    return Room(room.name, polygon, edges, room.entered, room.cells, list(room.notes))
