"""Turn posed depth frames into one world-frame point cloud.

Each depth pixel is pushed back into 3D with the frame's intrinsics and pose. Pixels that
cannot be trusted are dropped first: low sensor confidence, out of range, and pixels on a
depth edge (where one pixel covers both a near and a far surface and reports a distance
that belongs to neither). The surviving points are merged into small voxels so that a wall
seen in 300 frames becomes one clean layer of averaged points instead of 300 noisy copies.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from floorplan.capture import Capture


@dataclass(frozen=True)
class CloudConfig:
    voxel: float = 0.025  # metres
    min_confidence: int = 2
    min_depth: float = 0.25
    max_depth: float = 4.5
    edge_abs: float = 0.03  # a 3x3 depth range above max(edge_abs, edge_rel * depth) is an edge
    edge_rel: float = 0.04
    normal_step: int = 2  # pixels each side used for the surface-normal difference
    batch_frames: int = 24


@dataclass
class Cloud:
    xyz: np.ndarray  # (N, 3) world frame, metres
    normal: np.ndarray  # (N, 3) unit, pointing from the surface toward the camera that saw it
    weight: np.ndarray  # (N,) number of depth pixels merged into the point
    sigma: np.ndarray  # (N,) mean 1-sigma depth noise of those pixels, metres

    def __len__(self) -> int:
        return len(self.xyz)

    def select(self, mask: np.ndarray) -> Cloud:
        return Cloud(self.xyz[mask], self.normal[mask], self.weight[mask], self.sigma[mask])


def backproject(depth: np.ndarray, K: np.ndarray) -> np.ndarray:
    """Camera-frame points (H, W, 3) for a z-depth map. Pixel centres sit on integer
    coordinates, the convention Open3D and the capture app's own tools use."""
    height, width = depth.shape
    u = (np.arange(width) - K[0, 2]) / K[0, 0]
    v = (np.arange(height) - K[1, 2]) / K[1, 1]
    return np.stack([u[None, :] * depth, v[:, None] * depth, depth], axis=-1)


def trusted_pixels(
    depth: np.ndarray, confidence: np.ndarray | None, config: CloudConfig
) -> np.ndarray:
    """Boolean mask of depth pixels worth keeping."""
    valid = (depth > config.min_depth) & (depth < config.max_depth)
    if confidence is not None:
        valid &= confidence >= config.min_confidence
    kernel = np.ones((3, 3), np.uint8)
    spread = cv2.dilate(depth, kernel) - cv2.erode(depth, kernel)
    on_edge = spread > np.maximum(config.edge_abs, config.edge_rel * depth)
    return valid & ~on_edge


def _normals(points: np.ndarray, valid: np.ndarray, step: int) -> tuple[np.ndarray, np.ndarray]:
    """Surface normals from neighbouring pixels of the point map, facing the camera."""
    normals = np.zeros_like(points)
    ok = np.zeros(valid.shape, dtype=bool)
    s = step
    du = points[s:-s, 2 * s :] - points[s:-s, : -2 * s]
    dv = points[2 * s :, s:-s] - points[: -2 * s, s:-s]
    n = np.cross(dv, du)  # x right, y down, z forward: this order faces the camera
    length = np.linalg.norm(n, axis=-1)
    inner = (
        valid[s:-s, s:-s]
        & valid[s:-s, 2 * s :]
        & valid[s:-s, : -2 * s]
        & valid[2 * s :, s:-s]
        & valid[: -2 * s, s:-s]
        & (length > 1e-12)
    )
    n = n / np.maximum(length, 1e-12)[..., None]
    facing_away = np.einsum("ijk,ijk->ij", n, points[s:-s, s:-s]) > 0
    n[facing_away] *= -1
    normals[s:-s, s:-s] = n
    ok[s:-s, s:-s] = inner
    return normals, ok


def frame_points(
    capture: Capture, i: int, config: CloudConfig
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """World-frame points, normals and depth sigmas for the trusted pixels of frame `i`."""
    depth = capture.depth(i)
    frame = capture.frames[i]
    valid = trusted_pixels(depth, capture.confidence(i), config)
    points = backproject(depth.astype(np.float64), frame.K)
    normals, has_normal = _normals(points, valid, config.normal_step)
    keep = valid & has_normal
    R, t = frame.T_world_cam[:3, :3], frame.T_world_cam[:3, 3]
    xyz = points[keep] @ R.T + t
    normal = normals[keep] @ R.T
    sigma = capture.depth_sigma(depth[keep].astype(np.float64))
    return xyz, normal, sigma


def _normal_bin(normal: np.ndarray) -> np.ndarray:
    """Whether a point faces up, down or sideways.

    Points in the same voxel are averaged only within the same class, so the floor and the
    foot of a wall stay separate points. The class must never depend on the compass
    direction a wall faces: an earlier version binned that direction in 30-degree sectors,
    and a wall whose normal sat on a sector boundary was split into two half-populations
    whose averaged normals were biased about 7 degrees either way.
    """
    bins = np.full(len(normal), 2, dtype=np.int64)
    bins[normal[:, 2] > 0.7] = 0
    bins[normal[:, 2] < -0.7] = 1
    return bins


def _merge(
    xyz: np.ndarray, normal: np.ndarray, weight: np.ndarray, sigma: np.ndarray, voxel: float
) -> Cloud:
    """Average all points that share a voxel and a facing class (up, down, sideways)."""
    cell = np.floor(xyz / voxel).astype(np.int64) + (1 << 15)
    if cell.size and (cell.min() < 0 or cell.max() >= (1 << 16)):
        raise ValueError("point cloud extends beyond the supported +-800 m range")
    key = (((cell[:, 0] << 16) | cell[:, 1]) << 16 | cell[:, 2]) << 4 | _normal_bin(normal)
    _, inverse = np.unique(key, return_inverse=True)
    count = int(inverse.max()) + 1 if len(inverse) else 0
    total = np.bincount(inverse, weights=weight, minlength=count)

    def average(values: np.ndarray) -> np.ndarray:
        return np.bincount(inverse, weights=values * weight, minlength=count) / total

    merged_xyz = np.stack([average(xyz[:, k]) for k in range(3)], axis=1)
    merged_normal = np.stack([average(normal[:, k]) for k in range(3)], axis=1)
    merged_normal /= np.maximum(np.linalg.norm(merged_normal, axis=1), 1e-12)[:, None]
    return Cloud(merged_xyz, merged_normal, total, average(sigma))


def empty_cloud() -> Cloud:
    return Cloud(np.zeros((0, 3)), np.zeros((0, 3)), np.zeros(0), np.zeros(0))


def fragment_clouds(
    capture: Capture, config: CloudConfig | None = None
) -> tuple[list[Cloud], list[range]]:
    """Cut the capture into short runs of consecutive frames and merge each run on its own.

    A fragment is short enough (about a second of walking) that the recorded poses inside
    it can be trusted even when the walk as a whole has drifted. Drift correction moves
    whole fragments; the final cloud is the merge of the fragments.
    """
    config = config or CloudConfig()
    fragments: list[Cloud] = []
    ranges: list[range] = []
    for start in range(0, len(capture), config.batch_frames):
        positions = range(start, min(start + config.batch_frames, len(capture)))
        points = [frame_points(capture, i, config) for i in positions]
        xyz = np.concatenate([p[0] for p in points])
        if len(xyz):
            normal = np.concatenate([p[1] for p in points])
            sigma = np.concatenate([p[2] for p in points])
            fragments.append(_merge(xyz, normal, np.ones(len(xyz)), sigma, config.voxel))
        else:
            fragments.append(empty_cloud())
        ranges.append(positions)
    return fragments, ranges


def merge_clouds(clouds: list[Cloud], voxel: float) -> Cloud:
    """Merge already-thinned clouds. Averages are weighted by pixel count, so this gives
    the same result as merging every raw pixel at once."""
    clouds = [cloud for cloud in clouds if len(cloud)]
    if not clouds:
        raise ValueError("capture has no usable depth")
    return _merge(
        np.concatenate([c.xyz for c in clouds]),
        np.concatenate([c.normal for c in clouds]),
        np.concatenate([c.weight for c in clouds]),
        np.concatenate([c.sigma for c in clouds]),
        voxel,
    )


def accumulate(capture: Capture, config: CloudConfig | None = None) -> Cloud:
    """Merge every frame of `capture` into one voxel-averaged world-frame cloud."""
    config = config or CloudConfig()
    fragments, _ = fragment_clouds(capture, config)
    return merge_clouds(fragments, config.voxel)


def turn_and_shift(cloud: Cloud, theta: float, shift: np.ndarray) -> Cloud:
    """Rotate a cloud about the vertical axis by `theta` and shift it horizontally."""
    c, s = np.cos(theta), np.sin(theta)
    xyz = cloud.xyz.copy()
    xyz[:, 0] = c * cloud.xyz[:, 0] - s * cloud.xyz[:, 1] + shift[0]
    xyz[:, 1] = s * cloud.xyz[:, 0] + c * cloud.xyz[:, 1] + shift[1]
    normal = cloud.normal.copy()
    normal[:, 0] = c * cloud.normal[:, 0] - s * cloud.normal[:, 1]
    normal[:, 1] = s * cloud.normal[:, 0] + c * cloud.normal[:, 1]
    return Cloud(xyz, normal, cloud.weight, cloud.sigma)
