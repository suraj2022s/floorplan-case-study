"""Draw room finding's internals for one capture: wall lines, seen stretches, cells, rooms.

    python bench/public/layout_debug.py <ARKitScenes capture dir> <out.png>

Development tool. Grey: where floor or ceiling was seen; blue cells: counted as inside (with
their evidence share); orange dots: stretches of wall seen to full height; green: the path;
red: the rooms found.
"""

import sys

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import shapely
from shapely.geometry import LineString
from shapely.ops import polygonize, unary_union

from floorplan.capture import select_keyframes
from floorplan.geometry import layout as L
from floorplan.geometry.cloud import fragment_clouds, merge_clouds
from floorplan.geometry.drift import correct_drift
from floorplan.geometry.planes import SUPPORT_BIN, find_level, find_wall_lines
from floorplan.io.arkitscenes import read_arkitscenes
from floorplan.pipeline import config_for

scene, out = sys.argv[1], sys.argv[2]
config = config_for("lidar")
capture = read_arkitscenes(scene)
keyframes = capture.subset(select_keyframes(capture.frames))
fragments, ranges = fragment_clouds(keyframes, config.cloud)
keyframes, fragments, _ = correct_drift(keyframes, fragments, ranges, config.drift, config.planes)
cloud = merge_clouds(fragments, config.cloud.voxel)
floor = find_level(cloud, facing_up=True, config=config.planes)
ceiling = find_level(cloud, facing_up=False, config=config.planes)
lines = find_wall_lines(cloud, floor, ceiling, config.planes)
camera_xy = np.array([f.position[:2] for f in keyframes.frames])
print(len(lines), "wall lines")
for k, line in enumerate(lines):
    t = (line.supported_bins + 0.5) * SUPPORT_BIN
    span = f"{t.min():.2f}..{t.max():.2f}" if len(t) else "none"
    facing = np.degrees(np.arctan2(line.normal[1], line.normal[0]))
    print(
        f"  line {k}: facing {facing:7.1f}, offset {line.offset:6.3f}, seen "
        f"{line.supported_length:.2f} m over {span}, rms {line.rms * 1000:.1f} mm"
    )

cfg = config.layout
wall_xy = np.concatenate([line.points_xy for line in lines])
x0, y0 = wall_xy.min(axis=0) - cfg.margin
x1, y1 = wall_xy.max(axis=0) + cfg.margin
bounds = (float(x0), float(y0), float(x1), float(y1))
border = shapely.box(*bounds)
reach = float(np.hypot(x1 - x0, y1 - y0)) + 1.0
centre = np.array([(x0 + x1) / 2, (y0 + y1) / 2])
cutters = [border.exterior]
for line in lines:
    middle = line.point(float(line.along(centre)[0]))
    cutters.append(
        LineString([middle - reach * line.direction, middle + reach * line.direction]).intersection(
            border
        )
    )
cells = [c for c in polygonize(unary_union(cutters)) if c.area > 1e-6]
evidence, xs, ys = L._evidence_map(cloud, floor, camera_xy, bounds, cfg)
share = np.array([L._cell_share(c, evidence, xs, ys) for c in cells])

figure, axis = plt.subplots(figsize=(9, 9))
axis.imshow(
    evidence, extent=(xs[0], xs[-1], ys[0], ys[-1]), origin="lower", cmap="Greys", alpha=0.35
)
for c, s in zip(cells, share, strict=True):
    xx, yy = c.exterior.xy
    axis.fill(xx, yy, alpha=0.15 if s >= 0.5 else 0.0, color="#2a78d6")
    axis.plot(xx, yy, color="#c3c2be", linewidth=0.4)
    p = c.representative_point()
    axis.text(p.x, p.y, f"{s:.2f}", fontsize=5, ha="center")
for k, line in enumerate(lines):
    t = (line.supported_bins + 0.5) * SUPPORT_BIN
    pts = np.array([line.point(v) for v in t]) if len(t) else np.zeros((0, 2))
    axis.scatter(pts[:, 0], pts[:, 1], s=2, color="#eb6834")
    a = line.point(float(line.points_t.min()))
    b = line.point(float(line.points_t.max()))
    axis.plot([a[0], b[0]], [a[1], b[1]], color="#0b0b0b", linewidth=0.6)
    axis.text(a[0], a[1], str(k), fontsize=7, color="#b0272c")
axis.plot(camera_xy[:, 0], camera_xy[:, 1], color="#1baf7a", linewidth=0.8)
rooms = L.find_rooms(cloud, lines, floor, camera_xy, cfg)
for room in rooms:
    xx, yy = room.polygon.exterior.xy
    axis.plot(xx, yy, color="#b0272c", linewidth=1.5)
axis.set_aspect("equal")
figure.savefig(out, dpi=170, bbox_inches="tight")
print("wrote", out, "rooms", [(r.name, round(r.polygon.area, 2), r.entered) for r in rooms])
