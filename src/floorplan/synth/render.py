"""Render a synthetic scene into a Stray Scanner capture folder.

A virtual phone is walked through the scene. At each pose the scene mesh is ray cast into a
depth map with the resolution, field of view and range of an iPhone LiDAR depth map, noise is
added, and the frames are written in the same layout the real capture app writes. The
pipeline then reads the folder exactly as it would read a real capture.

What is modelled: per-pixel range noise that grows with distance, mixed ("flying") pixels at
depth edges, a maximum range, low confidence at edges and at long range, optional scale
bias, and optional pose drift. What is not modelled: glass, mirrors, glossy floors, motion
blur, and the learned smoothing ARKit applies to its depth maps.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import open3d as o3d

from floorplan.io.stray import write_stray
from floorplan.synth.scene import SCENES, SceneSpec


@dataclass(frozen=True)
class PhoneModel:
    rgb_size: tuple[int, int] = (1920, 1440)
    depth_size: tuple[int, int] = (256, 192)
    focal_rgb: float = 1450.0  # pixels at RGB resolution, close to an iPhone main camera
    max_range: float = 5.0  # metres; beyond this the depth is not trustworthy
    camera_height: float = 1.40
    supersample: int = 2

    @property
    def K_rgb(self) -> np.ndarray:
        w, h = self.rgb_size
        return np.array([[self.focal_rgb, 0, w / 2], [0, self.focal_rgb, h / 2], [0, 0, 1.0]])

    @property
    def K_depth(self) -> np.ndarray:
        K = self.K_rgb.copy()
        K[0] *= self.depth_size[0] / self.rgb_size[0]
        K[1] *= self.depth_size[1] / self.rgb_size[1]
        return K


@dataclass(frozen=True)
class NoiseModel:
    sigma_a: float = 0.0015  # metres
    sigma_b: float = 0.002  # fraction of depth
    scale_bias: float = 0.0  # relative error applied to every depth (0.01 = reads 1% long)


@dataclass(frozen=True)
class DriftModel:
    """Odometry error that accumulates with distance travelled, as real tracking does.

    Yaw and position drift only: the phone's accelerometer keeps gravity observable, so
    roll and pitch do not drift.
    """

    yaw_bias_deg_per_m: float = 0.0
    yaw_sigma_deg_per_sqrt_m: float = 0.0
    translation_bias_per_m: float = 0.0
    translation_sigma_per_sqrt_m: float = 0.0


def look_rotation(yaw: float, pitch: float) -> np.ndarray:
    """Camera-to-world rotation for a level phone looking along `yaw`, tilted up by `pitch`."""
    forward = np.array([np.cos(pitch) * np.cos(yaw), np.cos(pitch) * np.sin(yaw), np.sin(pitch)])
    right = np.array([np.sin(yaw), -np.cos(yaw), 0.0])
    down = np.cross(forward, right)
    return np.stack([right, down, forward], axis=1)


def pose(x: float, y: float, z: float, yaw: float, pitch: float) -> np.ndarray:
    T = np.eye(4)
    T[:3, :3] = look_rotation(yaw, pitch)
    T[:3, 3] = [x, y, z]
    return T


def walk_route(
    route: list[tuple[float, float, bool]],
    phone: PhoneModel,
    floor_z: float = 0.0,
    step: float = 0.10,
    spin_step_deg: float = 6.0,
    tilt_deg: float = 25.0,
) -> list[np.ndarray]:
    """Poses for walking through `route`, a list of (x, y, spin_here).

    Between waypoints the phone looks along the direction of travel and sweeps side to side
    and up and down. At a waypoint flagged `spin_here` the person turns a full circle twice,
    once tilted up to take in the ceiling and once tilted down to take in the floor.
    """
    poses: list[np.ndarray] = []
    z = floor_z + phone.camera_height
    tilt = np.radians(tilt_deg)
    heading = 0.0
    travelled = 0.0
    for k, (x, y, spin_here) in enumerate(route):
        if k > 0:
            px, py, _ = route[k - 1]
            length = float(np.hypot(x - px, y - py))
            heading = float(np.arctan2(y - py, x - px))
            count = max(1, int(np.ceil(length / step)))
            for i in range(1, count + 1):
                f = i / count
                travelled += length / count
                yaw = heading + np.radians(35.0) * np.sin(travelled * 3.1)
                pitch = tilt * np.sin(travelled * 4.7)
                poses.append(pose(px + f * (x - px), py + f * (y - py), z, yaw, pitch))
        if spin_here:
            for tilt_sign in (1.0, -1.0):
                for angle in np.arange(0.0, 360.0, spin_step_deg):
                    poses.append(pose(x, y, z, heading + np.radians(angle), tilt_sign * tilt))
    return poses


ROUTES: dict[str, list[tuple[float, float, bool]]] = {
    "box_room": [(1.05, 0.70, False), (1.40, 1.20, True), (2.90, 2.10, True)],
    "furnished_room": [(0.70, 0.72, False), (1.00, 0.90, True), (2.00, 0.90, True),
                       (0.95, 1.70, True)],
    "flat": [
        (0.60, 0.80, True),
        (0.60, 1.45, False), (1.26, 1.45, False), (2.20, 1.45, False),
        (3.40, 1.70, True), (4.70, 1.30, True),
        (2.20, 1.45, False), (1.26, 1.45, False), (0.60, 1.45, False),
        (0.60, 3.50, True),
        (-0.06, 3.50, False), (-1.00, 3.60, False),
        (-1.90, 4.30, True), (-2.80, 3.30, True),
        (-1.00, 3.60, False), (-0.06, 3.50, False), (0.60, 3.50, False),
        (0.60, 4.675, False), (1.26, 4.675, False),
        (2.70, 4.80, True),
        (1.26, 4.675, False), (0.60, 4.675, False),
        (0.60, 5.40, True),
        (0.60, 3.00, False), (0.60, 0.80, True),
    ],
}


def apply_drift(
    poses: list[np.ndarray], drift: DriftModel, rng: np.random.Generator
) -> list[np.ndarray]:
    """Corrupt true poses with yaw and position error that accumulates along the path."""
    out = [poses[0].copy()]
    C = np.eye(4)  # accumulated error: reported pose = C @ true pose
    for k in range(1, len(poses)):
        prev, cur = poses[k - 1], poses[k]
        moved = float(np.linalg.norm(cur[:3, 3] - prev[:3, 3]))
        cos_angle = np.clip((np.trace(prev[:3, :3].T @ cur[:3, :3]) - 1) / 2, -1, 1)
        distance = moved + 0.10 * float(np.arccos(cos_angle))  # turning also costs accuracy
        root = np.sqrt(distance)
        yaw = np.radians(
            drift.yaw_bias_deg_per_m * distance
            + drift.yaw_sigma_deg_per_sqrt_m * root * rng.standard_normal()
        )
        direction = cur[:3, 3] - prev[:3, 3]
        shift = drift.translation_bias_per_m * direction
        shift[:2] += drift.translation_sigma_per_sqrt_m * root * rng.standard_normal(2)

        centre = (C @ cur)[:3, 3]  # rotate about the phone's current (reported) position
        c, s = np.cos(yaw), np.sin(yaw)
        step = np.eye(4)
        step[:2, :2] = [[c, -s], [s, c]]
        step[:3, 3] = centre - step[:3, :3] @ centre + shift
        C = step @ C
        out.append(C @ cur)
    return out


def render_depth(
    scene: o3d.t.geometry.RaycastingScene,
    T_world_cam: np.ndarray,
    phone: PhoneModel,
    noise: NoiseModel,
    rng: np.random.Generator,
) -> tuple[np.ndarray, np.ndarray]:
    """One depth map (metres, 0 = no measurement) and its confidence map (0, 1, 2)."""
    width, height = phone.depth_size
    s = phone.supersample
    K = phone.K_depth
    # sub-pixel sample positions, centred on integer pixel coordinates
    offsets = (np.arange(s) + 0.5) / s - 0.5
    us = (np.arange(width)[:, None] + offsets[None, :]).reshape(-1)
    vs = (np.arange(height)[:, None] + offsets[None, :]).reshape(-1)
    uu, vv = np.meshgrid(us, vs)
    directions_cam = np.stack(
        [(uu - K[0, 2]) / K[0, 0], (vv - K[1, 2]) / K[1, 1], np.ones_like(uu)], axis=-1
    )
    directions = directions_cam @ T_world_cam[:3, :3].T
    origins = np.broadcast_to(T_world_cam[:3, 3], directions.shape)
    rays = np.concatenate([origins, directions], axis=-1).astype(np.float32)
    # the ray direction has z = 1 in the camera frame, so t_hit is already z-depth
    z = scene.cast_rays(o3d.core.Tensor(rays))["t_hit"].numpy()

    blocks = z.reshape(height, s, width, s).transpose(0, 2, 1, 3).reshape(height, width, s * s)
    hit = np.isfinite(blocks)
    hits = hit.sum(axis=-1)
    total = np.where(hit, blocks, 0.0).sum(axis=-1)
    depth = np.where(hits > 0, total / np.maximum(hits, 1), 0.0)
    near = np.where(hit, blocks, np.inf).min(axis=-1)
    far = np.where(hit, blocks, -np.inf).max(axis=-1)
    spread = np.where(hits > 0, (far - near) / np.maximum(depth, 1e-6), 1.0)

    valid = hits == s * s
    depth = depth * (1.0 + noise.scale_bias)
    depth = depth + rng.standard_normal(depth.shape) * (noise.sigma_a + noise.sigma_b * depth)
    depth = np.where(valid, depth, 0.0)

    confidence = np.full(depth.shape, 2, dtype=np.uint8)
    confidence[spread > 0.02] = 1
    confidence[(spread > 0.10) | (depth > phone.max_range) | ~valid] = 0
    return depth.astype(np.float32), confidence


def make_capture(
    scene_name: str,
    out_dir: Path | str,
    seed: int = 0,
    phone: PhoneModel | None = None,
    noise: NoiseModel | None = None,
    drift: DriftModel | None = None,
    route: list[tuple[float, float, bool]] | None = None,
    scene: SceneSpec | None = None,
) -> Path:
    """Render a named scene to `out_dir` in Stray Scanner layout, with its ground truth."""
    out_dir = Path(out_dir)
    phone = phone or PhoneModel()
    noise = noise or NoiseModel()
    scene = scene or SCENES[scene_name]()
    rng = np.random.default_rng(seed)

    vertices, triangles = scene.mesh()
    raycaster = o3d.t.geometry.RaycastingScene()
    raycaster.add_triangles(o3d.core.Tensor(vertices), o3d.core.Tensor(triangles))

    true_poses = walk_route(route or ROUTES[scene_name], phone)
    depths, confidences = [], []
    for T in true_poses:
        depth, confidence = render_depth(raycaster, T, phone, noise, rng)
        depths.append(depth)
        confidences.append(confidence)

    reported = apply_drift(true_poses, drift, rng) if drift is not None else true_poses
    timestamps = [i / 30.0 for i in range(len(true_poses))]
    write_stray(out_dir, reported, depths, confidences, phone.K_rgb, timestamps)

    truth = scene.ground_truth()
    truth["synthetic"] = {
        "scene": scene_name,
        "seed": seed,
        "frames": len(true_poses),
        "noise": noise.__dict__,
        "drift": None if drift is None else drift.__dict__,
    }
    (out_dir / "ground_truth.json").write_text(json.dumps(truth, indent=2) + "\n", newline="\n")
    return out_dir
