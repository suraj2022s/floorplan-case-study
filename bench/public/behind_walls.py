"""How much of each found room lies behind a clearly seen wall (fix loop, round 2 evidence).

    python bench/public/behind_walls.py <ARKitScenes capture dir> [...]


Does not change the pipeline. For each scan: the room the current code finds, the strong wall
lines (seen >= 1.0 m, scatter <= 15 mm), and the area of the room that lies behind one of
them (beyond its face, within its length) together with the share of the phone's path there.
"""

import sys

import numpy as np
import shapely

from floorplan.capture import select_keyframes
from floorplan.geometry import layout as L
from floorplan.geometry.cloud import fragment_clouds, merge_clouds
from floorplan.geometry.drift import correct_drift
from floorplan.geometry.planes import SUPPORT_BIN, find_level, find_wall_lines
from floorplan.io.arkitscenes import read_arkitscenes
from floorplan.pipeline import config_for

for scene in sys.argv[1:]:
    config = config_for("lidar")
    capture = read_arkitscenes(scene)
    keyframes = capture.subset(select_keyframes(capture.frames))
    fragments, ranges = fragment_clouds(keyframes, config.cloud)
    keyframes, fragments, _ = correct_drift(
        keyframes, fragments, ranges, config.drift, config.planes
    )
    cloud = merge_clouds(fragments, config.cloud.voxel)
    floor = find_level(cloud, facing_up=True, config=config.planes)
    ceiling = find_level(cloud, facing_up=False, config=config.planes)
    lines = find_wall_lines(cloud, floor, ceiling, config.planes)
    camera = np.array([f.position[:2] for f in keyframes.frames])
    rooms = L.find_rooms(cloud, lines, floor, camera, config.layout)
    room = rooms[0].polygon
    strong = [line for line in lines if line.supported_length >= 1.0 and line.rms <= 0.015]
    print(f"\n{scene}: room {room.area:.2f} m2, {len(lines)} lines, {len(strong)} strong")
    # sample the room on a 5 cm grid; mark samples behind a strong line within its length
    x0, y0, x1, y1 = room.bounds
    xs, ys = np.meshgrid(np.arange(x0, x1, 0.05), np.arange(y0, y1, 0.05))
    grid = np.c_[xs.ravel(), ys.ravel()]
    grid = grid[shapely.contains(room, shapely.points(grid))]
    behind_any = np.zeros(len(grid), bool)
    for line in strong:
        t = (line.supported_bins + 0.5) * SUPPORT_BIN
        along = line.along(grid)
        depth = line.distance(grid)  # positive in front of the face
        behind = (depth < -0.05) & (along > t.min() - 0.3) & (along < t.max() + 0.3)
        if behind.any():
            facing = np.degrees(np.arctan2(line.normal[1], line.normal[0]))
            path_along = line.along(camera)
            cam_behind = (
                (line.distance(camera) < -0.05)
                & (path_along > t.min() - 0.3)
                & (path_along < t.max() + 0.3)
            )
            print(
                f"  behind line facing {facing:7.1f} (seen {line.supported_length:.2f} m, rms "
                f"{line.rms * 1000:.1f} mm): {behind.sum() * 0.0025:.2f} m2 of the room, "
                f"{cam_behind.mean() * 100:.1f}% of the path"
            )
        behind_any |= behind
    print(f"  total behind a strong wall: {behind_any.sum() * 0.0025:.2f} m2 of {room.area:.2f} m2")
