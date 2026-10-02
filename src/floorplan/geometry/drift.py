"""Correct accumulated pose drift by anchoring the walk to the walls.

Phone tracking is accurate over a metre or two and drifts over a whole walk: by the time the
person is back where they started, the recorded position can be several centimetres and a
fraction of a degree off. A wall seen at the start and again at the end then shows up as a
thick or doubled wall, and every dimension that spans the walk inherits the error.

A wall does not move. So every time the phone sees a wall it should see it in the same
place, and any disagreement is drift. That is the whole idea:

1. the walk is cut into short fragments (about a second each). Inside one fragment the
   recorded poses are trusted;
2. walls are fitted to the points of all fragments together. Copies of the same wall that
   drift has pulled apart (same facing direction, a few centimetres apart, overlapping
   along their length) are merged into one;
3. each fragment gets a small correction - a turn about the vertical axis and a horizontal
   shift - chosen so that its wall points lie on the walls they belong to. All fragments
   are solved together, with the correction required to change only slowly from one
   fragment to the next, so a fragment that sees too little to fix itself (one bare wall in
   a corridor) follows its neighbours;
4. steps 2 and 3 are repeated a few times, since better poses give sharper walls.

Only yaw and horizontal position are corrected. The phone's accelerometer keeps gravity
observable, so tilt does not drift, and height is left alone so that a real step between
two rooms is never flattened.

The first fragment is held fixed: it defines the frame. If the capture has no drift the
points already lie on their walls, the corrections come out as zero, and nothing changes.
This property is why this method replaced pairwise cloud registration, which moved good
poses when two fragments shared only a thin strip of wall.

The stage can be switched off, which is how the with/without ablation is produced.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np

from floorplan.capture import Capture
from floorplan.geometry.cloud import Cloud, turn_and_shift
from floorplan.geometry.planes import (
    PlaneConfig,
    find_level,
    find_wall_lines,
    merge_wall_copies,
)


@dataclass(frozen=True)
class DriftConfig:
    # metres, one per iteration: how far from a wall a point may be and still belong to it
    assign_distance: tuple[float, ...] = (0.15, 0.12, 0.10, 0.08, 0.06, 0.05)
    normal_agreement: float = 0.9  # cosine between a point's normal and its wall's
    merge_offset: float = 0.15  # metres; wall copies closer than this may be one wall
    merge_angle_deg: float = 4.0
    merge_overlap: float = 0.5  # share of the shorter copy's length that must overlap
    thin: int = 3  # every n-th point of a fragment is enough to estimate its correction
    point_sigma: float = 0.01  # metres, 1-sigma of one point's distance to its wall
    correlation: float = 20.0  # voxel points that count as one independent reading
    step_sigma_shift: float = 0.01  # metres the correction may change per fragment
    step_sigma_turn_deg: float = 0.10
    max_weight: float = 40.0
    wall_min_height: float = 0.10
    max_wall_rms: float = 0.05  # metres; how thick a drifted wall may be and still be used


def _apply(theta: float, shift: np.ndarray, delta: np.ndarray) -> tuple[float, np.ndarray]:
    """Compose a correction (theta, shift) with a further small one `delta`."""
    c, s = np.cos(delta[0]), np.sin(delta[0])
    turned = np.array([c * shift[0] - s * shift[1], s * shift[0] + c * shift[1]])
    return theta + delta[0], turned + delta[1:]


def estimate_drift(
    fragments: list[Cloud],
    config: DriftConfig | None = None,
    plane_config: PlaneConfig | None = None,
) -> tuple[np.ndarray, dict]:
    """Per-fragment corrections (theta, shift_x, shift_y) in the world frame, and a summary.

    A corrected point is `R(theta) p + shift`.
    """
    config = config or DriftConfig()
    # before correction a drifted wall is thick; accept looser fits here than the layout does
    plane_config = replace(plane_config or PlaneConfig(), max_rms=config.max_wall_rms)
    count = len(fragments)
    populated = [f for f in fragments if len(f)]
    if count < 3 or not populated:
        return np.zeros((count, 3)), {"applied": False, "reason": "capture too short"}

    # work about the middle of the scene so turns and shifts are not confounded
    origin = np.concatenate([f.xyz[:, :2] for f in populated]).mean(axis=0)
    thinned = []
    for fragment in fragments:
        keep = np.zeros(len(fragment), dtype=bool)
        keep[:: config.thin] = True
        thinned.append(turn_and_shift(fragment.select(keep), 0.0, -origin))

    theta = np.zeros(count)
    shift = np.zeros((count, 2))
    precision = np.diag(
        [
            1 / np.radians(config.step_sigma_turn_deg) ** 2,
            1 / config.step_sigma_shift**2,
            1 / config.step_sigma_shift**2,
        ]
    )
    history: list[float] = []
    walls_used = merged_total = 0

    passes = len(config.assign_distance)
    for iteration in range(passes + 1):  # the extra pass only measures the result
        # the measuring pass uses the first pass's reach, so before and after are comparable
        reach = config.assign_distance[iteration if iteration < passes else 0]
        moved = [turn_and_shift(f, theta[k], shift[k]) for k, f in enumerate(thinned)]
        union = Cloud(
            np.concatenate([m.xyz for m in moved]),
            np.concatenate([m.normal for m in moved]),
            np.concatenate([m.weight for m in moved]),
            np.concatenate([m.sigma for m in moved]),
        )
        floor = find_level(union, facing_up=True, config=plane_config)
        if floor is None:
            return np.zeros((count, 3)), {"applied": False, "reason": "no floor to anchor to"}
        ceiling = find_level(union, facing_up=False, config=plane_config)
        lines, merged = merge_wall_copies(
            find_wall_lines(union, floor, ceiling, plane_config),
            config.merge_offset,
            config.merge_angle_deg,
            config.merge_overlap,
        )
        if iteration == 0:
            merged_total = merged
        if len(lines) < 2:
            return np.zeros((count, 3)), {"applied": False, "reason": "fewer than two walls"}
        walls_used = len(lines)
        normals = np.stack([line.normal for line in lines])
        offsets = np.array([line.offset for line in lines])

        system = np.zeros((3 * count, 3 * count))
        target = np.zeros(3 * count)
        squares = weights = 0.0
        for k, cloud in enumerate(moved):
            if not len(cloud):
                continue
            height = cloud.xyz[:, 2] - floor.z_at(cloud.xyz[:, :2])
            vertical = (np.abs(cloud.normal[:, 2]) < 0.3) & (height > config.wall_min_height)
            xy = cloud.xyz[vertical, :2]
            facing = cloud.normal[vertical, :2]
            facing = facing / np.maximum(np.linalg.norm(facing, axis=1), 1e-9)[:, None]
            distance = xy @ normals.T - offsets
            allowed = (facing @ normals.T > config.normal_agreement) & (np.abs(distance) < reach)
            distance = np.where(allowed, np.abs(distance), np.inf)
            wall = np.argmin(distance, axis=1)
            assigned = np.isfinite(distance[np.arange(len(xy)), wall])
            if not assigned.any():
                continue
            xy, wall = xy[assigned], wall[assigned]
            n = normals[wall]
            residual = np.einsum("ij,ij->i", xy, n) - offsets[wall]
            # Each point counts as 1/sigma^2, scaled down because neighbouring points share
            # the same depth frames and are far from independent. Points far off their wall
            # (relative to the current reach) lose influence, so a door leaf or a picture
            # frame near a wall cannot drag a fragment.
            weight = np.minimum(cloud.weight[vertical][assigned], config.max_weight)
            squares += float(weight @ residual**2)
            weights += float(weight.sum())
            weight = weight / config.max_weight / config.correlation / config.point_sigma**2
            weight = weight / (1 + (residual / (reach / 3)) ** 2)
            # how the residual changes with a turn about the origin and with a shift
            jacobian = np.column_stack([n[:, 1] * xy[:, 0] - n[:, 0] * xy[:, 1], n])
            block = slice(3 * k, 3 * k + 3)
            system[block, block] += (jacobian * weight[:, None]).T @ jacobian
            target[block] -= (jacobian * weight[:, None]).T @ residual
        history.append(float(np.sqrt(squares / max(weights, 1e-12))))
        if iteration == passes:
            break

        # the correction changes slowly from one fragment to the next
        def linear(k: int) -> np.ndarray:
            return np.array([[1.0, 0, 0], [-shift[k, 1], 1, 0], [shift[k, 0], 0, 1]])

        for k in range(count - 1):
            gap = np.concatenate([[theta[k + 1] - theta[k]], shift[k + 1] - shift[k]])
            pair = np.hstack([-linear(k), linear(k + 1)])
            both = slice(3 * k, 3 * k + 6)
            system[both, both] += pair.T @ precision @ pair
            target[both] -= pair.T @ precision @ gap
        system[:3, :3] += np.eye(3) * 1e12  # the first fragment defines the frame

        delta = np.linalg.lstsq(system, target, rcond=None)[0].reshape(count, 3)
        for k in range(count):
            theta[k], shift[k] = _apply(theta[k], shift[k], delta[k])

    # express the corrections about the true world origin again
    corrections = np.zeros((count, 3))
    for k in range(count):
        c, s = np.cos(theta[k]), np.sin(theta[k])
        turned_origin = np.array([c * origin[0] - s * origin[1], s * origin[0] + c * origin[1]])
        corrections[k] = [theta[k], *(shift[k] + origin - turned_origin)]

    # how far each fragment's own points were moved
    moved_by = []
    for k, fragment in enumerate(fragments):
        if len(fragment):
            centre = fragment.xyz[:, :2].mean(axis=0)
            c, s = np.cos(corrections[k, 0]), np.sin(corrections[k, 0])
            after = np.array([c * centre[0] - s * centre[1], s * centre[0] + c * centre[1]])
            moved_by.append(float(np.linalg.norm(after + corrections[k, 1:] - centre)))
    stats = {
        "applied": True,
        "method": "plane-anchored: fragments turned and shifted onto shared wall planes, "
        "solved jointly with a smoothness prior; yaw and horizontal position only",
        "fragments": count,
        "iterations": passes,
        "walls_used": walls_used,
        "wall_copies_merged": merged_total,
        "wall_residual_rms_before_m": round(history[0], 5),
        "wall_residual_rms_after_m": round(history[-1], 5),
        "mean_shift_m": round(float(np.mean(moved_by)), 4),
        "max_shift_m": round(float(np.max(moved_by)), 4),
        "max_turn_deg": round(float(np.degrees(np.abs(corrections[:, 0]).max())), 4),
    }
    return corrections, stats


def correct_drift(
    capture: Capture,
    fragments: list[Cloud],
    ranges: list[range],
    config: DriftConfig | None = None,
    plane_config: PlaneConfig | None = None,
) -> tuple[Capture, list[Cloud], dict]:
    """Drift-corrected capture poses and fragment clouds, plus a summary of what changed."""
    corrections, stats = estimate_drift(fragments, config, plane_config)
    if not stats["applied"]:
        return capture, fragments, stats
    poses: list[np.ndarray] = [frame.T_world_cam for frame in capture.frames]
    corrected = []
    for (theta, sx, sy), fragment, positions in zip(corrections, fragments, ranges, strict=True):
        c, s = np.cos(theta), np.sin(theta)
        move = np.eye(4)
        move[:2, :2] = [[c, -s], [s, c]]
        move[:2, 3] = [sx, sy]
        for i in positions:
            poses[i] = move @ capture.frames[i].T_world_cam
        corrected.append(turn_and_shift(fragment, theta, np.array([sx, sy])))
    return capture.with_poses(poses), corrected, stats
