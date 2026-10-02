"""Synthetic rooms with exactly known dimensions.

A scene is a set of rectangular rooms, the openings between them, and furniture boxes. It is
turned into a triangle mesh, and that mesh is what the virtual phone is ray cast against.
Because every dimension is chosen by us, the pipeline can be scored to the millimetre on
these scenes before any real capture exists.

These scenes test the geometry code. They say nothing about real sensor behaviour (glass,
mirrors, drift, exposure), so results on them are development evidence, never benchmark
numbers.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

SIDES = ("S", "E", "N", "W")


@dataclass(frozen=True)
class RoomSpec:
    """An axis-aligned room given by its inner wall faces."""

    name: str
    x0: float
    y0: float
    x1: float
    y1: float
    ceiling: float = 2.70
    floor: float = 0.0

    @property
    def width(self) -> float:
        return self.x1 - self.x0

    @property
    def depth(self) -> float:
        return self.y1 - self.y0

    @property
    def area(self) -> float:
        return self.width * self.depth

    @property
    def centre(self) -> tuple[float, float]:
        return (self.x0 + self.x1) / 2, (self.y0 + self.y1) / 2

    def wall_length(self, side: str) -> float:
        return self.width if side in ("S", "N") else self.depth


@dataclass(frozen=True)
class OpeningSpec:
    """A rectangular hole in one wall of `room`.

    `side` names the wall: S is y = y0, N is y = y1, W is x = x0, E is x = x1. `start` is the
    world coordinate along the wall (x for S and N walls, y for E and W walls) of the jamb
    with the smaller coordinate. `other_room` is the room behind the opening; when it is
    None the opening leads outside and `depth` is the wall thickness there.
    """

    id: str
    kind: str  # "door" | "window" | "passage"
    room: str
    side: str
    start: float
    width: float
    height: float
    sill: float = 0.0
    other_room: str | None = None
    depth: float = 0.12


@dataclass(frozen=True)
class BoxSpec:
    """A furniture box."""

    name: str
    x0: float
    y0: float
    z0: float
    x1: float
    y1: float
    z1: float


@dataclass
class SceneSpec:
    rooms: list[RoomSpec]
    openings: list[OpeningSpec] = field(default_factory=list)
    boxes: list[BoxSpec] = field(default_factory=list)

    def room(self, name: str) -> RoomSpec:
        for room in self.rooms:
            if room.name == name:
                return room
        raise KeyError(name)

    # ------------------------------------------------------------------ mesh

    def mesh(self) -> tuple[np.ndarray, np.ndarray]:
        """Vertices (N, 3) and triangles (M, 3) of every surface a ray can hit."""
        quads: list[np.ndarray] = []
        for room in self.rooms:
            quads.append(_horizontal_quad(room.x0, room.y0, room.x1, room.y1, room.floor))
            quads.append(_horizontal_quad(room.x0, room.y0, room.x1, room.y1, room.ceiling))
            for side in SIDES:
                holes = [
                    (start, start + width, sill, sill + height)
                    for start, width, sill, height in self._holes(room, side)
                ]
                quads.extend(_wall_with_holes(room, side, holes))
        for opening in self.openings:
            quads.extend(self._reveal(opening))
        for box in self.boxes:
            quads.extend(_box_quads(box))

        vertices = np.concatenate(quads).astype(np.float32)
        count = len(quads)
        base = np.arange(count, dtype=np.uint32)[:, None] * 4
        triangles = np.concatenate([base + [0, 1, 2], base + [0, 2, 3]]).astype(np.uint32)
        return vertices, triangles

    def _holes(self, room: RoomSpec, side: str) -> list[tuple[float, float, float, float]]:
        """(start, width, sill, height) of every opening cut into this wall of this room."""
        holes = []
        for opening in self.openings:
            if opening.room == room.name and opening.side == side:
                holes.append((opening.start, opening.width, opening.sill, opening.height))
            elif opening.other_room == room.name and _opposite(opening.side) == side:
                # sill is measured from the floor of the room that owns the opening
                lift = self.room(opening.room).floor - room.floor
                holes.append((opening.start, opening.width, opening.sill + lift, opening.height))
        return sorted(holes)

    def _face_coordinates(self, opening: OpeningSpec) -> tuple[float, float]:
        """Wall-face coordinate on the room side and on the far side of the opening."""
        room = self.room(opening.room)
        near = {"S": room.y0, "N": room.y1, "W": room.x0, "E": room.x1}[opening.side]
        outward = 1.0 if opening.side in ("N", "E") else -1.0
        if opening.other_room is None:
            return near, near + outward * opening.depth
        other = self.room(opening.other_room)
        far = {"S": other.y1, "N": other.y0, "W": other.x1, "E": other.x0}[opening.side]
        return near, far

    def wall_thickness(self, opening: OpeningSpec) -> float:
        near, far = self._face_coordinates(opening)
        return abs(far - near)

    def _reveal(self, opening: OpeningSpec) -> list[np.ndarray]:
        """The four faces lining an opening: two jambs, the head, and the sill or threshold."""
        room = self.room(opening.room)
        near, far = self._face_coordinates(opening)
        a0, a1 = opening.start, opening.start + opening.width
        z0, z1 = room.floor + opening.sill, room.floor + opening.sill + opening.height
        along_x = opening.side in ("S", "N")

        def point(along: float, across: float, z: float) -> list[float]:
            return [along, across, z] if along_x else [across, along, z]

        def quad(corners: list[tuple[float, float, float]]) -> np.ndarray:
            return np.array([point(*corner) for corner in corners])

        return [
            quad([(a0, near, z0), (a0, far, z0), (a0, far, z1), (a0, near, z1)]),  # jamb
            quad([(a1, near, z0), (a1, far, z0), (a1, far, z1), (a1, near, z1)]),  # jamb
            quad([(a0, near, z1), (a1, near, z1), (a1, far, z1), (a0, far, z1)]),  # head
            quad([(a0, near, z0), (a1, near, z0), (a1, far, z0), (a0, far, z0)]),  # sill
        ]

    # ---------------------------------------------------------- ground truth

    def ground_truth(self) -> dict:
        """Dimensions in the same shape as a hand-measured ground-truth file."""
        rooms = {}
        for room in self.rooms:
            rooms[room.name] = {
                "ceiling_height": round(room.ceiling - room.floor, 4),
                "floor_area": round(room.area, 4),
                "walls": [
                    {"id": f"{room.name}-{side}", "length": round(room.wall_length(side), 4)}
                    for side in SIDES
                ],
                "polygon": [
                    [room.x0, room.y0],
                    [room.x1, room.y0],
                    [room.x1, room.y1],
                    [room.x0, room.y1],
                ],
            }
        openings = []
        for opening in self.openings:
            openings.append(
                {
                    "id": opening.id,
                    "kind": opening.kind,
                    "room": opening.room,
                    "wall": f"{opening.room}-{opening.side}",
                    "other_room": opening.other_room,
                    "width": round(opening.width, 4),
                    "height": round(opening.height, 4),
                    "sill": round(opening.sill, 4),
                    "wall_thickness": round(self.wall_thickness(opening), 4),
                    "centre": self._opening_centre(opening),
                }
            )
        adjacency = sorted(
            sorted([o.room, o.other_room]) for o in self.openings if o.other_room is not None
        )
        return {
            "units": "metres",
            "source": "synthetic scene, exact by construction",
            "rooms": rooms,
            "openings": openings,
            "adjacency": adjacency,
            "footprint_area": round(sum(room.area for room in self.rooms), 4),
        }

    def _opening_centre(self, opening: OpeningSpec) -> list[float]:
        near, _ = self._face_coordinates(opening)
        middle = opening.start + opening.width / 2
        if opening.side in ("S", "N"):
            return [round(middle, 4), round(near, 4)]
        return [round(near, 4), round(middle, 4)]


def _opposite(side: str) -> str:
    return {"S": "N", "N": "S", "E": "W", "W": "E"}[side]


def _horizontal_quad(x0: float, y0: float, x1: float, y1: float, z: float) -> np.ndarray:
    return np.array([[x0, y0, z], [x1, y0, z], [x1, y1, z], [x0, y1, z]])


def _wall_with_holes(
    room: RoomSpec, side: str, holes: list[tuple[float, float, float, float]]
) -> list[np.ndarray]:
    """A wall face as rectangles: full-height strips between holes, plus the bits above and
    below each hole. `holes` are (a0, a1, z0, z1) with z measured from the room's floor."""
    along_x = side in ("S", "N")
    lo, hi = (room.x0, room.x1) if along_x else (room.y0, room.y1)
    across = {"S": room.y0, "N": room.y1, "W": room.x0, "E": room.x1}[side]
    bottom, top = room.floor, room.ceiling

    def quad(a0: float, a1: float, z0: float, z1: float) -> np.ndarray:
        if along_x:
            return np.array(
                [[a0, across, z0], [a1, across, z0], [a1, across, z1], [a0, across, z1]]
            )
        return np.array([[across, a0, z0], [across, a1, z0], [across, a1, z1], [across, a0, z1]])

    quads = []
    cursor = lo
    for a0, a1, z0, z1 in holes:
        z0, z1 = bottom + z0, bottom + z1
        if a0 > cursor:
            quads.append(quad(cursor, a0, bottom, top))
        if z1 < top:
            quads.append(quad(a0, a1, z1, top))
        if z0 > bottom:
            quads.append(quad(a0, a1, bottom, z0))
        cursor = a1
    if cursor < hi:
        quads.append(quad(cursor, hi, bottom, top))
    return quads


def _box_quads(box: BoxSpec) -> list[np.ndarray]:
    x0, y0, z0, x1, y1, z1 = box.x0, box.y0, box.z0, box.x1, box.y1, box.z1
    return [
        np.array([[x0, y0, z0], [x1, y0, z0], [x1, y1, z0], [x0, y1, z0]]),
        np.array([[x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1]]),
        np.array([[x0, y0, z0], [x1, y0, z0], [x1, y0, z1], [x0, y0, z1]]),
        np.array([[x0, y1, z0], [x1, y1, z0], [x1, y1, z1], [x0, y1, z1]]),
        np.array([[x0, y0, z0], [x0, y1, z0], [x0, y1, z1], [x0, y0, z1]]),
        np.array([[x1, y0, z0], [x1, y1, z0], [x1, y1, z1], [x1, y0, z1]]),
    ]


# ------------------------------------------------------------- ready-made scenes


def box_room() -> SceneSpec:
    """One empty room, 4.20 x 3.35 x 2.74 m, with a door and a window."""
    return SceneSpec(
        rooms=[RoomSpec("room", 0.0, 0.0, 4.20, 3.35, ceiling=2.74)],
        openings=[
            OpeningSpec("room-D1", "door", "room", "S", start=0.60, width=0.90, height=2.05),
            OpeningSpec(
                "room-WIN1",
                "window",
                "room",
                "N",
                start=1.50,
                width=1.20,
                height=1.20,
                sill=0.90,
                depth=0.20,
            ),
        ],
    )


def flat() -> SceneSpec:
    """Three rooms off a corridor: the multi-room case the stitched plan must handle.

    Walls between rooms are 0.12 m thick. Layout (not to scale):

        +-----------+----+----------+
        |  bedroom  | c  | kitchen  |
        |           | o  +----------+
        +-----------+ r  |          |
                    | r  |  living  |
                    +----+----------+
    """
    t = 0.12
    corridor = RoomSpec("corridor", 0.0, 0.0, 1.20, 6.00, ceiling=2.70)
    bedroom = RoomSpec("bedroom", -t - 3.60, 2.40, -t, 6.00, ceiling=2.70)
    living = RoomSpec("living", 1.20 + t, 0.0, 1.20 + t + 4.50, 3.40, ceiling=2.70)
    kitchen = RoomSpec("kitchen", 1.20 + t, 3.40 + t, 1.20 + t + 2.80, 6.00, ceiling=2.55)
    return SceneSpec(
        rooms=[corridor, bedroom, living, kitchen],
        openings=[
            OpeningSpec(
                "corridor-D1", "door", "corridor", "S", start=0.15, width=0.90, height=2.05
            ),
            OpeningSpec(
                "bedroom-D1",
                "door",
                "corridor",
                "W",
                start=3.10,
                width=0.80,
                height=2.05,
                other_room="bedroom",
            ),
            OpeningSpec(
                "living-D1",
                "door",
                "corridor",
                "E",
                start=1.00,
                width=0.90,
                height=2.05,
                other_room="living",
            ),
            OpeningSpec(
                "kitchen-D1",
                "door",
                "corridor",
                "E",
                start=4.30,
                width=0.75,
                height=2.05,
                other_room="kitchen",
            ),
            OpeningSpec(
                "bedroom-WIN1",
                "window",
                "bedroom",
                "N",
                start=-2.90,
                width=1.50,
                height=1.20,
                sill=0.90,
                depth=0.23,
            ),
            OpeningSpec(
                "living-WIN1",
                "window",
                "living",
                "S",
                start=2.60,
                width=1.80,
                height=1.35,
                sill=0.80,
                depth=0.23,
            ),
        ],
    )


def furnished_room() -> SceneSpec:
    """One room with a bed, a tall wardrobe and a table hiding parts of the walls and floor."""
    return SceneSpec(
        rooms=[RoomSpec("bedroom", 0.0, 0.0, 3.80, 3.20, ceiling=2.65)],
        openings=[
            OpeningSpec("bedroom-D1", "door", "bedroom", "W", start=0.30, width=0.85, height=2.03),
            OpeningSpec(
                "bedroom-WIN1",
                "window",
                "bedroom",
                "E",
                start=0.90,
                width=1.40,
                height=1.25,
                sill=0.85,
                depth=0.23,
            ),
        ],
        boxes=[
            BoxSpec("bed", 1.30, 1.30, 0.0, 3.30, 3.20, 0.50),
            BoxSpec("wardrobe", 0.0, 2.20, 0.0, 0.60, 3.20, 2.05),
            BoxSpec("table", 2.60, 0.0, 0.0, 3.80, 0.60, 0.75),
        ],
    )


SCENES = {"box_room": box_room, "flat": flat, "furnished_room": furnished_room}
