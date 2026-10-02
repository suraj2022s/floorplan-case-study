"""End-to-end checks on synthetic rooms whose dimensions are known exactly.

These prove the geometry code is right. They do not prove anything about real sensors.
"""

import numpy as np


def _sorted_lengths(room):
    return sorted(wall.length.value for wall in room.walls)


def _opening(plan, kind):
    found = [o for o in plan.openings if o.kind == kind]
    assert len(found) == 1, f"expected one {kind}, found {[o.id for o in plan.openings]}"
    return found[0]


def test_box_room_dimensions(box_room_plan, truth):
    plan, expected = box_room_plan, truth["box_room"]["rooms"]["room"]
    assert len(plan.rooms) == 1
    room = plan.rooms[0]
    assert len(room.walls) == 4
    assert np.allclose(_sorted_lengths(room), [3.35, 3.35, 4.20, 4.20], atol=0.01)
    assert abs(room.ceiling_height.value - expected["ceiling_height"]) < 0.01
    assert abs(room.floor_area.value - expected["floor_area"]) / expected["floor_area"] < 0.01


def test_box_room_openings(box_room_plan):
    door = _opening(box_room_plan, "door")
    window = _opening(box_room_plan, "window")
    assert abs(door.width.value - 0.90) < 0.02
    assert abs(door.height.value - 2.05) < 0.03
    assert abs(window.width.value - 1.20) < 0.02
    assert abs(window.sill - 0.90) < 0.03
    assert len(box_room_plan.openings) == 2  # no phantom openings


def test_intervals_contain_the_truth(box_room_plan):
    room = box_room_plan.rooms[0]
    for wall in room.walls:
        target = 4.20 if abs(wall.length.value - 4.20) < 0.5 else 3.35
        assert wall.length.lo <= target <= wall.length.hi
    assert room.ceiling_height.lo <= 2.74 <= room.ceiling_height.hi


def test_furniture_does_not_change_the_room(furnished_room_plan, truth):
    """A bed, a table and a tall wardrobe hide walls and floor; the room must still be the
    plain rectangle, measured wall to wall."""
    plan, expected = furnished_room_plan, truth["furnished_room"]["rooms"]["bedroom"]
    assert len(plan.rooms) == 1
    room = plan.rooms[0]
    assert len(room.walls) == 4
    assert np.allclose(_sorted_lengths(room), [3.20, 3.20, 3.80, 3.80], atol=0.015)
    assert abs(room.ceiling_height.value - expected["ceiling_height"]) < 0.01


def test_flat_rooms_and_adjacency(flat_plan, truth):
    plan, expected = flat_plan, truth["flat"]
    assert len(plan.rooms) == 4
    found = sorted(round(room.floor_area.value, 1) for room in plan.rooms)
    wanted = sorted(round(room["floor_area"], 1) for room in expected["rooms"].values())
    assert np.allclose(found, wanted, atol=0.15)

    # three doors off the corridor: the corridor is linked to every other room
    links = {}
    for a, b, _ in plan.adjacency:
        links.setdefault(a, set()).add(b)
        links.setdefault(b, set()).add(a)
    assert max(len(v) for v in links.values()) == 3
    assert len(plan.adjacency) == 3

    # no two rooms overlap
    from shapely.geometry import Polygon

    polygons = [Polygon(room.polygon) for room in plan.rooms]
    for i in range(len(polygons)):
        for j in range(i + 1, len(polygons)):
            assert polygons[i].intersection(polygons[j]).area < 0.01

    total = expected["footprint_area"]
    assert abs(plan.footprint_area.value - total) / total < 0.01


def test_same_capture_gives_the_same_plan(box_room_folder, box_room_plan):
    """Determinism: a second run on the same files reproduces every number exactly."""
    from floorplan.io.stray import read_stray
    from floorplan.pipeline import PipelineConfig, run

    again = run(read_stray(box_room_folder), PipelineConfig())
    first = [wall.length.value for wall in box_room_plan.rooms[0].walls]
    second = [wall.length.value for wall in again.rooms[0].walls]
    assert first == second
