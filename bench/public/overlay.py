"""Put a capture's LiDAR points and its plan into the laser scan's frame, and measure the walls.

    python bench/public/overlay.py <capture dir> <plan.json> <laser scan.ply> <out.png>

Development tool for the public-data benchmark. The capture is aligned to the laser scan by
ICP (both are level, so the search is over the wall direction, then a rigid fit). It prints,
for each laser wall, how far in front of it the capture's points lie (positive: inside the
room), plus the best-fit scale between the two clouds, and draws the plan on top.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import open3d as o3d

sys.path.insert(0, str(Path(__file__).resolve().parent))
from laser_truth import levels, lines_in, read_scan, room_walls  # noqa: E402

from floorplan.geometry.cloud import backproject  # noqa: E402
from floorplan.io.arkitscenes import read_arkitscenes  # noqa: E402


def capture_points(scene: str, step: int = 4) -> np.ndarray:
    capture = read_arkitscenes(scene)
    points = []
    for i in range(0, len(capture.frames), step):
        depth = capture.depth(i).astype(np.float64)
        confidence = capture.confidence(i) if capture.confidence_loader else np.full(depth.shape, 2)
        ok = (depth > 0.2) & (depth < 4.0) & (confidence >= 2)
        T = capture.frames[i].T_world_cam
        points.append(backproject(depth, capture.frames[i].K)[ok] @ T[:3, :3].T + T[:3, 3])
    return np.concatenate(points)


def _cloud(xyz: np.ndarray, voxel: float = 0.02):
    cloud = o3d.geometry.PointCloud(o3d.utility.Vector3dVector(xyz)).voxel_down_sample(voxel)
    cloud.estimate_normals(o3d.geometry.KDTreeSearchParamHybrid(radius=0.08, max_nn=30))
    return cloud


def _wall_angle(cloud) -> float:
    normals = np.asarray(cloud.normals)
    side = np.abs(normals[:, 2]) < 0.2
    angles = np.degrees(np.arctan2(normals[side, 1], normals[side, 0])) % 90
    histogram, edges = np.histogram(angles, bins=180, range=(0, 90))
    return float(edges[np.argmax(histogram)] + 0.25)


def align(source_xyz: np.ndarray, target_xyz: np.ndarray):
    """Rigid transform taking the capture onto the laser scan, and the best-fit scale."""
    source, target = _cloud(source_xyz), _cloud(target_xyz)
    plane = o3d.pipelines.registration.TransformationEstimationPointToPlane()
    turn = _wall_angle(target) - _wall_angle(source)
    best = None
    for k in range(4):
        yaw = np.radians(turn + 90 * k)
        start = np.eye(4)
        start[:3, :3] = [[np.cos(yaw), -np.sin(yaw), 0], [np.sin(yaw), np.cos(yaw), 0], [0, 0, 1]]
        moved = np.asarray(source.points) @ start[:3, :3].T
        start[:3, 3] = np.median(np.asarray(target.points), 0) - np.median(moved, 0)
        start[2, 3] = np.percentile(np.asarray(target.points)[:, 2], 1) - np.percentile(
            moved[:, 2], 1
        )
        result = o3d.pipelines.registration.registration_icp(source, target, 0.15, start, plane)
        result = o3d.pipelines.registration.registration_icp(
            source, target, 0.05, result.transformation, plane
        )
        if best is None or result.fitness > best.fitness:
            best = result
    scaled = o3d.pipelines.registration.registration_icp(
        source,
        target,
        0.04,
        best.transformation,
        o3d.pipelines.registration.TransformationEstimationPointToPoint(with_scaling=True),
    )
    scale = float(np.cbrt(np.linalg.det(scaled.transformation[:3, :3])))
    return best.transformation, best.fitness, best.inlier_rmse, scale


def main() -> int:
    scene, plan_file, scan, out = (
        sys.argv[1],
        Path(sys.argv[2]),
        Path(sys.argv[3]),
        Path(sys.argv[4]),
    )
    laser = read_scan(scan)
    laser = laser[np.hypot(laser[:, 0], laser[:, 1]) < 4.0]
    ceiling, floor, _ = levels(laser)
    height_laser = laser[:, 2] - (floor[0] * laser[:, 0] + floor[1] * laser[:, 1] + floor[2])
    room_height = float(ceiling[2] - floor[2])
    band = laser[(height_laser > room_height - 0.40) & (height_laser < room_height - 0.08)][:, :2]
    walls = room_walls(lines_in(band))

    arkit = capture_points(scene)
    T, fitness, rmse, scale = align(arkit, laser)
    moved = arkit @ T[:3, :3].T + T[:3, 3]
    height = moved[:, 2] - (floor[0] * moved[:, 0] + floor[1] * moved[:, 1] + floor[2])
    print(
        f"alignment: fitness {fitness:.3f}, rmse {rmse * 1000:.1f} mm; best-fit scale "
        f"laser/capture {scale:.4f}"
    )
    for wall in walls:
        facing = np.degrees(np.arctan2(wall.normal[1], wall.normal[0]))
        signed = moved[:, :2] @ wall.normal + wall.distance  # 0 on the laser wall
        for lo, hi in [(0.3, 1.2), (1.2, 2.0), (2.0, room_height - 0.1)]:
            near = (np.abs(signed) < 0.20) & (height > lo) & (height < hi)
            if near.sum() > 50:
                print(
                    f"  wall facing {facing:7.2f} deg, {lo:.1f}-{hi:.1f} m up: {near.sum():6d} "
                    f"points, median {np.median(signed[near]) * 100:+5.1f} cm in front"
                )
    print(
        f"  capture ceiling: median {np.median(height[(height > 2.4) & (height < 2.9)]):.4f} m "
        f"above the laser floor (laser: {room_height:.4f} m)"
    )

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plan = json.loads(plan_file.read_text())
    figure, axis = plt.subplots(figsize=(7, 7))
    top = laser[(height_laser > 1.0) & (height_laser < room_height - 0.08)]
    axis.scatter(top[::8, 0], top[::8, 1], s=0.05, color="#9a9894", label="laser scan")
    seen = moved[(height > 1.0) & (height < room_height - 0.08)]
    axis.scatter(seen[::2, 0], seen[::2, 1], s=0.05, color="#2a78d6", label="iPad LiDAR")
    for room in plan["rooms"]:
        outline = np.array(room["polygon"] + [room["polygon"][0]])
        outline = np.c_[outline, np.zeros(len(outline))] @ T[:3, :3].T + T[:3, 3]
        axis.plot(outline[:, 0], outline[:, 1], color="#eb6834", linewidth=1.3, label="plan")
    centre = np.median(top[:, :2], axis=0)
    axis.set_xlim(centre[0] - 2.8, centre[0] + 2.8)
    axis.set_ylim(centre[1] - 2.8, centre[1] + 2.8)
    axis.set_aspect("equal")
    axis.legend(markerscale=40, fontsize=8, loc="upper left")
    axis.set_title(f"{Path(scene).name}: plan and LiDAR points on the laser scan", fontsize=9)
    out.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(out, dpi=150, bbox_inches="tight")
    print("wrote", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
