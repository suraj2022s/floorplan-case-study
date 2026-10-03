"""Photo tier on the synthetic four-room flat, photographed as the capture protocol asks.

The depth of each photo is the scene's true depth with the errors a depth model makes
(a scale error per photo, a slow warp, pixel noise), so this tests the geometry, the honesty
checks and the stitching, not the depth model. No learned model is loaded.
"""

import numpy as np
import pytest

from floorplan.frontend.photo import room_plan
from floorplan.stitch import stitch
from floorplan.synth.photos import protocol_views
from floorplan.synth.scene import SCENES


@pytest.fixture(scope="module")
def flat():
    scene = SCENES["flat"]()
    plans = {}
    for k, room in enumerate(scene.rooms):
        long, short = max(room.width, room.depth), min(room.width, room.depth)
        count = 2 if long / short > 2.5 else 4  # corridors: one photo from each end
        plans[room.name] = room_plan(
            room.name, protocol_views(scene, room.name, count=count, seed=100 + k)
        )
    return scene, plans


def test_every_room_is_measured_within_two_percent(flat):
    scene, plans = flat
    for room in scene.rooms:
        walls = sorted(w.length.value for w in plans[room.name].rooms[0].walls)
        truth = sorted([room.width, room.width, room.depth, room.depth])
        assert np.allclose(walls, truth, rtol=0.02), (room.name, walls, truth)


def test_doors_show_the_corridor_behind_them(flat):
    _, plans = flat
    for name in ("bedroom", "living", "kitchen"):
        door = next(o for o in plans[name].openings if o.kind == "door")
        # the corridor is 1.2 m wide and its wall 0.12 m thick
        assert door.depth_beyond == pytest.approx(1.32, abs=0.15), name


def test_stitch_never_joins_rooms_that_do_not_meet(flat):
    scene, plans = flat
    whole = stitch(list(plans.values()))
    found = {tuple(sorted(link[:2])) for link in whole.adjacency}
    truth = {tuple(sorted(pair)) for pair in scene.ground_truth()["adjacency"]}
    assert found <= truth, f"wrong adjacency: {found - truth}"
    assert len(found) >= 2
    assert (
        whole.footprint_area.lo <= scene.ground_truth()["footprint_area"] <= whole.footprint_area.hi
    )
