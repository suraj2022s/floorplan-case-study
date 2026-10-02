"""Damage placement, concealed-damage rules and scope, with a stand-in for the detector.

The detector itself is a pretrained model and is not tested here. What is tested is
everything after it: that a box in an image lands on the right surface with the right size
in metres, that the rules fire on the right patterns, and that scope quantities follow from
the plan's measurements.
"""

from dataclasses import replace

import numpy as np
import pytest

from floorplan.capture import Frame
from floorplan.models.detect import Detection
from floorplan.semantics.damage import damage_regions, find_sightings
from floorplan.semantics.rules import raise_flags
from floorplan.semantics.scope import build_scope
from floorplan.synth.render import pose

K = np.array([[500.0, 0, 320.0], [0, 500.0, 240.0], [0, 0, 1.0]])
IMAGE = np.zeros((480, 640, 3), np.uint8)
CLASSES = {
    "water_stain": {"phrases": ["water stain"], "threshold": 0.2},
    "crack": {"phrases": ["crack in the wall"], "threshold": 0.2},
}


def _box_of(corners_world: np.ndarray, T_world_cam: np.ndarray) -> tuple:
    """The image box around 3D points, as a perfect detector would draw it."""
    camera = (corners_world - T_world_cam[:3, 3]) @ T_world_cam[:3, :3]
    pixels = (camera / camera[:, 2:3]) @ K.T
    return (pixels[:, 0].min(), pixels[:, 1].min(), pixels[:, 0].max(), pixels[:, 1].max())


def _plan_with_view(plan, T_world_cam):
    return replace(plan, frames=[Frame(0, 0.0, K, T_world_cam, name="view")])


def _run(plan, T_world_cam, label, corners):
    plan = _plan_with_view(plan, T_world_cam)
    box = _box_of(corners, T_world_cam)

    def detect(image, phrases, threshold):
        return [Detection(label, 0.8, box)]

    sightings = find_sightings(plan, {"view": lambda: (IMAGE, K, None)}, detect, CLASSES)
    regions = damage_regions(sightings, plan, scale_sigma=0.005)
    flags = raise_flags(plan, regions)
    return plan, regions, flags, build_scope(plan, regions, flags)


def _east_wall(plan):
    return next(
        w
        for w in plan.rooms[0].walls
        if abs(w.start[0] - 4.2) < 0.05 and abs(w.end[0] - 4.2) < 0.05
    )


def test_stain_at_the_foot_of_a_wall(box_room_plan):
    # a 0.60 x 0.40 m stain on the east wall (x = 4.20), its lower edge 0.10 m above the floor
    corners = np.array([[4.2, 1.0, 0.1], [4.2, 1.6, 0.1], [4.2, 1.6, 0.5], [4.2, 1.0, 0.5]])
    view = pose(2.1, 1.3, 1.4, 0.0, np.radians(-25.0))  # room centre, looking east and down
    plan, regions, flags, scope = _run(box_room_plan, view, "water stain", corners)

    assert len(regions) == 1
    region = regions[0]
    assert region.kind == "water_stain"
    assert region.surface == _east_wall(plan).id
    assert region.width.value == pytest.approx(0.60, abs=0.01)
    assert region.height.value == pytest.approx(0.40, abs=0.01)
    assert region.above_floor == pytest.approx(0.10, abs=0.01)
    assert region.width.lo < 0.60 < region.width.hi

    assert [flag.rule_id for flag in flags] == ["WALL_BASE_MOISTURE"]
    assert flags[0].damage_ids == [region.id]

    codes = [item.code for item in scope]
    assert codes == ["STAIN_BLOCK", "REPAINT_WALL", "MOISTURE_INSPECTION"]
    assert all(item.surface == region.surface for item in scope)
    assert scope[2].rule_id == "WALL_BASE_MOISTURE"
    # repaint is the whole wall: 3.35 m long, 2.74 m high, no opening in the east wall
    assert scope[1].quantity.value == pytest.approx(3.35 * 2.74, rel=0.01)
    assert scope[1].quantity.lo < 3.35 * 2.74 < scope[1].quantity.hi


def test_stain_on_the_ceiling(box_room_plan):
    corners = np.array([[1.8, 1.4, 2.74], [2.6, 1.4, 2.74], [2.6, 2.0, 2.74], [1.8, 2.0, 2.74]])
    view = pose(2.1, 1.0, 1.4, np.radians(90.0), np.radians(60.0))  # looking up and north
    plan, regions, flags, scope = _run(box_room_plan, view, "water stain", corners)

    assert len(regions) == 1
    assert regions[0].surface_kind == "ceiling"
    assert regions[0].area.value == pytest.approx(0.8 * 0.6, rel=0.05)
    assert [flag.rule_id for flag in flags] == ["CEIL_WATER"]
    assert [item.code for item in scope] == [
        "STAIN_BLOCK",
        "REPAINT_CEILING",
        "MOISTURE_INSPECTION",
    ]
    assert scope[1].quantity.value == pytest.approx(4.20 * 3.35, rel=0.01)


def test_crack_beside_the_door(box_room_plan):
    # the door is in the south wall (y = 0) from x = 0.60 to 1.50; a crack rises from its
    # top-right corner
    corners = np.array([[1.55, 0.0, 2.0], [1.75, 0.0, 2.0], [1.75, 0.0, 2.5], [1.55, 0.0, 2.5]])
    view = pose(1.6, 2.0, 1.4, np.radians(-90.0), np.radians(20.0))  # looking south, up a bit
    plan, regions, flags, scope = _run(box_room_plan, view, "crack in the wall", corners)

    assert len(regions) == 1 and regions[0].kind == "crack"
    assert [flag.rule_id for flag in flags] == ["CRACK_AT_OPENING"]
    assert flags[0].evidence["distance_to_opening_m"] < 0.3
    assert [item.code for item in scope] == ["CRACK_FILL", "REPAINT_WALL", "STRUCTURAL_INSPECTION"]
    assert scope[0].quantity.value == pytest.approx(0.5, abs=0.02)  # the crack's length


def test_a_box_on_furniture_is_not_wall_damage(box_room_plan):
    corners = np.array([[4.2, 1.0, 0.8], [4.2, 1.6, 0.8], [4.2, 1.6, 1.2], [4.2, 1.0, 1.2]])
    view = pose(2.1, 1.3, 1.4, 0.0, np.radians(-10.0))
    plan = _plan_with_view(box_room_plan, view)
    box = _box_of(corners, view)
    # the sensor says the pixel is 1 m away, but the wall is 2.1 m away: something is in front
    depth = np.full((480, 640), 1.0, np.float32)
    sightings = find_sightings(
        plan,
        {"view": lambda: (IMAGE, K, depth)},
        lambda image, phrases, threshold: [Detection("water stain", 0.8, box)],
        CLASSES,
    )
    assert sightings == []
