"""Load ground truth and match a predicted plan to it.

Ground truth is coordinate-free: a tape gives lengths, not positions. For each room it holds
the walls in order (W1 has the door you came in through, then turning right, which is
clockwise seen from above), the ceiling height, and the openings with the wall they are in
and their distance from that wall's left corner.

The pipeline produces polygons in an arbitrary frame, with walls in counter-clockwise order
starting anywhere. So matching has to find, for each room, which predicted room it is and
which predicted wall is W1. It does that from the numbers alone:

* rooms: the assignment of predicted rooms to measured rooms that minimises the total
  mismatch in wall lengths (Hungarian algorithm);
* walls: the rotation of the predicted wall sequence that best fits the measured sequence,
  using the openings to break ties in rooms whose walls repeat (a rectangle looks the same
  rotated by half a turn until you ask which wall has the door);
* openings: an opening is matched when it is on the matched wall and its centre is within
  30 cm of the measured position. Anything measured but unmatched is a miss; anything
  predicted but unmatched is a phantom.

The scorer never reads pipeline internals, only `plan.json`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import yaml
from scipy.optimize import linear_sum_assignment

POSITION_TOLERANCE = 0.30  # metres along the wall for two openings to be the same opening
UNMATCHED_WALL_COST = 1.0  # metres charged per wall that has no partner


@dataclass
class TruthOpening:
    id: str
    room: str
    wall: int  # index into the room's wall list
    kind: str
    width: float
    height: float | None
    sill: float
    centre_from_left: float  # along the wall, clockwise direction, to the opening's middle
    connects: str | None  # room id on the other side, or None for outside


@dataclass
class TruthRoom:
    id: str
    walls: list[float]  # lengths, clockwise seen from above
    wall_ids: list[str]
    ceiling_height: float | None
    floor_area: float | None
    openings: list[TruthOpening] = field(default_factory=list)


@dataclass
class Truth:
    site: str
    rooms: list[TruthRoom]
    adjacency: list[tuple[str, str]]
    footprint_area: float | None
    cross_room_distances: list[dict]
    source: str


def load_truth(path: Path) -> Truth:
    """Read a hand-measured YAML file or the JSON a synthetic scene writes."""
    path = Path(path)
    if path.suffix == ".json":
        return _from_synthetic(json.loads(path.read_text()), path.parent.name)
    data = yaml.safe_load(path.read_text())
    rooms = []
    for entry in data["rooms"]:
        walls = [float(w["length"]) for w in entry["walls"]]
        wall_ids = [str(w["id"]) for w in entry["walls"]]
        ceiling = entry.get("ceiling_height") or {}
        room = TruthRoom(
            id=str(entry["id"]),
            walls=walls,
            wall_ids=wall_ids,
            ceiling_height=float(ceiling["middle"]) if ceiling.get("middle") else None,
            floor_area=float(entry["floor_area"]) if entry.get("floor_area") else None,
        )
        for opening in entry.get("openings") or []:
            width = opening["width"]
            width = float(width["middle"] if isinstance(width, dict) else width)
            connects = opening.get("connects")
            room.openings.append(
                TruthOpening(
                    id=f"{room.id}-{opening['id']}",
                    room=room.id,
                    wall=wall_ids.index(str(opening["wall"])),
                    kind=str(opening.get("kind", "door")),
                    width=width,
                    height=float(opening["height"]) if opening.get("height") else None,
                    sill=float(opening.get("sill") or 0.0),
                    centre_from_left=float(opening["from_left_corner"]) + width / 2,
                    connects=None if connects in (None, "outside") else str(connects),
                )
            )
        rooms.append(room)
    return Truth(
        site=str(data.get("site", path.stem)),
        rooms=rooms,
        adjacency=[tuple(sorted(map(str, pair))) for pair in data.get("adjacency") or []],
        footprint_area=float(data["footprint_area"]) if data.get("footprint_area") else None,
        cross_room_distances=list(data.get("cross_room_distances") or []),
        source=f"measured: {data.get('instrument', {})}",
    )


def _from_synthetic(data: dict, site: str) -> Truth:
    """Synthetic scenes list walls S, E, N, W (counter-clockwise) with world positions.

    Converted here to the measured form: clockwise order S, W, N, E, and opening positions
    as a distance from the wall's left corner when facing the wall from inside the room.
    """
    clockwise = ["S", "W", "N", "E"]
    rooms = []
    for name, entry in data["rooms"].items():
        length = {wall["id"].rsplit("-", 1)[1]: float(wall["length"]) for wall in entry["walls"]}
        (x0, y0), _, (x1, y1), _ = entry["polygon"]
        room = TruthRoom(
            id=name,
            walls=[length[side] for side in clockwise],
            wall_ids=clockwise,
            ceiling_height=float(entry["ceiling_height"]),
            floor_area=float(entry["floor_area"]),
        )
        room._box = (x0, y0, x1, y1)  # type: ignore[attr-defined]
        rooms.append(room)
    by_name = {room.id: room for room in rooms}

    def from_left(room: TruthRoom, side: str, centre: list[float]) -> float:
        x0, y0, x1, y1 = room._box  # type: ignore[attr-defined]
        # facing a wall from inside, "left" is the end you meet first going clockwise
        return {"S": x1 - centre[0], "W": centre[1] - y0, "N": centre[0] - x0, "E": y1 - centre[1]}[
            side
        ]

    for opening in data["openings"]:
        room = by_name[opening["room"]]
        side = opening["wall"].rsplit("-", 1)[1]
        room.openings.append(
            TruthOpening(
                id=opening["id"],
                room=room.id,
                wall=clockwise.index(side),
                kind=opening["kind"],
                width=float(opening["width"]),
                height=float(opening["height"]),
                sill=float(opening["sill"]),
                centre_from_left=from_left(room, side, opening["centre"]),
                connects=opening["other_room"],
            )
        )
    return Truth(
        site=site,
        rooms=rooms,
        adjacency=[tuple(sorted(pair)) for pair in data["adjacency"]],
        footprint_area=float(data["footprint_area"]),
        cross_room_distances=[],
        source="synthetic scene, exact by construction",
    )


# ------------------------------------------------------------------ predictions


@dataclass
class PredictedOpening:
    id: str
    kind: str
    width: dict
    height: dict
    sill: float
    sides: list[tuple[str, int, float]]  # (room, clockwise wall index, centre from left)


@dataclass
class PredictedRoom:
    id: str
    walls: list[dict]  # length measurements, clockwise
    wall_ids: list[str]
    ceiling_height: dict
    floor_area: dict
    polygon: np.ndarray


@dataclass
class Prediction:
    rooms: list[PredictedRoom]
    openings: list[PredictedOpening]
    adjacency: list[tuple[str, str]]
    footprint_area: dict
    tier: str
    raw: dict


def load_prediction(path: Path) -> Prediction:
    """Read a `plan.json` and put every room's walls in clockwise order."""
    data = json.loads(Path(path).read_text())
    rooms = []
    lookup: dict[str, PredictedRoom] = {}
    for entry in data["rooms"]:
        walls = list(reversed(entry["walls"]))  # the pipeline writes counter-clockwise
        room = PredictedRoom(
            id=entry["id"],
            walls=[wall["length"] for wall in walls],
            wall_ids=[wall["id"] for wall in walls],
            ceiling_height=entry["ceiling_height"],
            floor_area=entry["floor_area"],
            polygon=np.array(entry["polygon"], dtype=float),
        )
        room._segments = [  # type: ignore[attr-defined]
            (np.array(wall["start"], float), np.array(wall["end"], float)) for wall in walls
        ]
        rooms.append(room)
        lookup[room.id] = room

    def side(room: PredictedRoom, centre: np.ndarray) -> tuple[str, int, float] | None:
        """The wall of `room` an opening sits on, and its centre measured clockwise."""
        best = None
        for index, (start, end) in enumerate(room._segments):  # type: ignore[attr-defined]
            direction = end - start
            length = float(np.linalg.norm(direction))
            direction = direction / max(length, 1e-9)
            along = float((centre - start) @ direction)
            across = abs(float((centre - start) @ np.array([-direction[1], direction[0]])))
            if (
                -0.2 <= along <= length + 0.2
                and across < 0.6
                and (best is None or across < best[0])
            ):
                # walls are stored counter-clockwise start -> end; clockwise runs end -> start
                best = (across, index, length - along)
        return None if best is None else (room.id, best[1], best[2])

    openings = []
    for entry in data["openings"]:
        centre = np.array(entry["centre"], dtype=float)
        sides = []
        for name in (entry["room"], entry.get("connects_to")):
            if name in lookup:
                found = side(lookup[name], centre)
                if found is not None:
                    sides.append(found)
        openings.append(
            PredictedOpening(
                id=entry["id"],
                kind=entry["kind"],
                width=entry["width"],
                height=entry["height"],
                sill=float(entry["sill_height"]),
                sides=sides,
            )
        )
    return Prediction(
        rooms=rooms,
        openings=openings,
        adjacency=[tuple(sorted(link["rooms"])) for link in data["adjacency"]],
        footprint_area=data["footprint_area"],
        tier=data["capture"]["tier"],
        raw=data,
    )


# --------------------------------------------------------------------- matching


@dataclass
class RoomMatch:
    truth: TruthRoom
    predicted: PredictedRoom | None
    shift: int = 0  # predicted wall (i + shift) % n is the truth wall i
    wall_count_matches: bool = False

    def predicted_wall(self, truth_index: int) -> int | None:
        if self.predicted is None or not self.wall_count_matches:
            return None
        return (truth_index + self.shift) % len(self.predicted.walls)


def _best_shift(truth: TruthRoom, predicted: PredictedRoom, openings: list[PredictedOpening]):
    """Rotation of the predicted walls that best fits the measured ones, and its cost."""
    count = len(truth.walls)
    measured = np.array(truth.walls)
    lengths = np.array([wall["value"] for wall in predicted.walls])
    if len(lengths) != count:
        # different number of walls: compare the sorted lengths, charge the unmatched ones
        a, b = np.sort(measured)[::-1], np.sort(lengths)[::-1]
        shared = min(len(a), len(b))
        cost = float(np.abs(a[:shared] - b[:shared]).sum())
        return 0, cost + UNMATCHED_WALL_COST * abs(len(a) - len(b))
    best_shift, best_cost = 0, np.inf
    for shift in range(count):
        cost = float(np.abs(measured - np.roll(lengths, -shift)).sum())
        # openings break the tie between rotations of a room with repeating walls
        for item in truth.openings:
            wall = (item.wall + shift) % count
            near = [
                abs(centre - item.centre_from_left)
                for opening in openings
                for room, index, centre in opening.sides
                if room == predicted.id and index == wall
            ]
            cost += 0.5 if not near or min(near) > POSITION_TOLERANCE else 0.1 * min(near)
        if cost < best_cost - 1e-9:
            best_shift, best_cost = shift, cost
    return best_shift, best_cost


def match_rooms(truth: Truth, prediction: Prediction) -> list[RoomMatch]:
    """Pair every measured room with a predicted room (or with nothing)."""
    if not prediction.rooms:
        return [RoomMatch(room, None) for room in truth.rooms]
    cost = np.zeros((len(truth.rooms), len(prediction.rooms)))
    shifts = np.zeros_like(cost, dtype=int)
    for i, room in enumerate(truth.rooms):
        for j, candidate in enumerate(prediction.rooms):
            shifts[i, j], cost[i, j] = _best_shift(room, candidate, prediction.openings)
    rows, columns = linear_sum_assignment(cost)
    matches = {i: RoomMatch(truth.rooms[i], None) for i in range(len(truth.rooms))}
    for i, j in zip(rows, columns, strict=True):
        predicted = prediction.rooms[j]
        matches[i] = RoomMatch(
            truth.rooms[i],
            predicted,
            int(shifts[i, j]),
            wall_count_matches=len(predicted.walls) == len(truth.rooms[i].walls),
        )
    return [matches[i] for i in range(len(truth.rooms))]


@dataclass
class OpeningMatch:
    truth: TruthOpening | None  # None for a phantom
    predicted: PredictedOpening | None  # None for a miss


def match_openings(matches: list[RoomMatch], prediction: Prediction) -> list[OpeningMatch]:
    """Pair measured openings with predicted ones; leftovers are misses and phantoms."""
    used: set[str] = set()
    results: list[OpeningMatch] = []
    seen_pairs: set[tuple] = set()
    for match in matches:
        for item in match.truth.openings:
            # a door between two rooms may be written down once in each room's list
            key = tuple(sorted([match.truth.id, item.connects or ""])) + (round(item.width, 3),)
            if item.connects is not None and key in seen_pairs:
                continue
            seen_pairs.add(key)
            wall = match.predicted_wall(item.wall)
            best, best_gap = None, POSITION_TOLERANCE
            if wall is not None:
                for opening in prediction.openings:
                    if opening.id in used:
                        continue
                    for room, index, centre in opening.sides:
                        gap = abs(centre - item.centre_from_left)
                        if room == match.predicted.id and index == wall and gap <= best_gap:
                            best, best_gap = opening, gap
            if best is not None:
                used.add(best.id)
            results.append(OpeningMatch(item, best))
    for opening in prediction.openings:
        if opening.id not in used:
            results.append(OpeningMatch(None, opening))
    return results
