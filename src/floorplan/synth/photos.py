"""Synthetic stand-ins for photos with model-predicted depth.

Used to test the photo-tier logic (levelling, room fitting, stitching) without a depth
model in the loop. A view is rendered from where the capture protocol puts the person: back
against the middle of a wall, looking at the opposite wall. Its depth gets the kind of error
a learned depth model makes: a scale error that is constant over the image and different for
each photo, and a slow tilt and bow across the image. Pixel-to-pixel noise is small, because
a network's output is smooth. How large these errors really are for a given model is not
known from this; that is measured on real photos.
"""

from __future__ import annotations

import numpy as np
import open3d as o3d

from floorplan.frontend.views import View
from floorplan.synth.render import NoiseModel, PhoneModel, pose, render_depth
from floorplan.synth.scene import SceneSpec

PHOTO = PhoneModel(
    rgb_size=(512, 384),
    depth_size=(512, 384),
    focal_rgb=384.0,
    max_range=15.0,
    camera_height=1.40,
    supersample=1,
)  # 67 degrees across, like an iPhone main camera held sideways
STANDOFF = 0.35


def protocol_views(
    scene: SceneSpec,
    room_name: str,
    count: int = 4,
    seed: int = 0,
    scale_sigma: float = 0.03,
    pixel_noise: float = 0.001,
    warp: float = 0.006,
    standoff: float = STANDOFF,
) -> list[View]:
    """The walk-round photos of one room: clockwise, each facing the opposite wall."""
    room = scene.room(room_name)
    rng = np.random.default_rng(seed)
    vertices, triangles = scene.mesh()
    raycaster = o3d.t.geometry.RaycastingScene()
    raycaster.add_triangles(o3d.core.Tensor(vertices), o3d.core.Tensor(triangles))

    cx, cy = room.centre
    z = room.floor + PHOTO.camera_height
    stations = [
        (cx, room.y0 + standoff, np.pi / 2),  # back to the south wall, looking north
        (room.x0 + standoff, cy, 0.0),  # back to the west wall, looking east
        (cx, room.y1 - standoff, -np.pi / 2),  # back to the north wall, looking south
        (room.x1 - standoff, cy, np.pi),  # back to the east wall, looking west
    ]
    order = {2: [0, 2], 3: [0, 1, 2]}.get(count, [0, 1, 2, 3])[:count]
    views = []
    for slot, index in enumerate(order):
        x, y, yaw = stations[index]
        # a hand-held photo is never perfectly level or square to the wall
        yaw += np.radians(rng.normal(0, 3.0))
        pitch = np.radians(rng.normal(0, 3.0))
        scale = float(np.exp(rng.normal(0, scale_sigma)))
        noise = NoiseModel(sigma_a=0.001, sigma_b=pixel_noise, scale_bias=scale - 1.0)
        depth, _ = render_depth(raycaster, pose(x, y, z, yaw, pitch), PHOTO, noise, rng)
        # A network's depth is smooth from pixel to pixel; what it gets wrong varies slowly
        # across the image. Model that as a gentle tilt and bow of the whole depth map.
        height, width = depth.shape
        u = np.linspace(-1, 1, width)[None, :]
        v = np.linspace(-1, 1, height)[:, None]
        a, b, c = rng.normal(0, warp, size=3)
        depth = np.where(depth > 0, depth * (1 + a * u + b * v + c * (u**2 + v**2 - 0.6)), 0)
        views.append(
            View(name=f"{room_name}_{slot + 1}", depth=depth.astype(np.float32), K=PHOTO.K_depth)
        )
    return views
