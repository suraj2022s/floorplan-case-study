"""The surfaces of a finished plan (walls, ceilings, floors) and where a camera ray meets them.

Damage is found in images, but it has to be reported on a surface, in metres. The bridge is
a ray: a pixel in a posed image defines a ray from the camera into the room, and the first
surface of the plan that ray meets is the surface the pixel shows. The corners of a box
drawn in the image, pushed along their rays onto that surface, give the box's size on the
surface in metres.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from shapely.geometry import Point, Polygon

from floorplan.pipeline import Plan


@dataclass
class Surface:
    id: str
    room: str
    kind: str  # "wall" | "ceiling" | "floor"
    origin: np.ndarray  # (3,) a corner of the surface: for a wall, its first corner at floor level
    along: np.ndarray  # (3,) unit, the u axis: along the wall, or along the room's first wall
    up: np.ndarray  # (3,) unit, the v axis: up the wall, or across the room
    normal: np.ndarray  # (3,) unit, pointing into the room
    width: float  # extent along u, metres
    height: float  # extent along v, metres
    polygon: Polygon | None = None  # ceilings and floors: the room outline

    def meet(self, origin: np.ndarray, direction: np.ndarray) -> tuple[float, float, float] | None:
        """Where a ray meets this surface's plane: (distance along ray, u, v), or None if the
        ray runs away from it or parallel to it."""
        closing = float(direction @ self.normal)
        if closing > -1e-6:  # must travel against the inward normal to arrive from inside
            return None
        t = float((self.origin - origin) @ self.normal) / closing
        if t <= 0:
            return None
        hit = origin + t * direction - self.origin
        return t, float(hit @ self.along), float(hit @ self.up)

    def contains(self, u: float, v: float) -> bool:
        if self.kind == "wall":
            return -0.02 <= u <= self.width + 0.02 and -0.02 <= v <= self.height + 0.02
        point = self.origin + u * self.along + v * self.up
        return bool(self.polygon.buffer(0.02).contains(Point(point[:2])))


def surfaces_of(plan: Plan) -> list[Surface]:
    """Every wall, ceiling and floor of the plan."""
    surfaces = []
    for room in plan.rooms:
        height = room.ceiling_height.value if room.ceiling_height.available else 2.6
        floor_z = room.floor_z
        for wall in room.walls:
            direction = wall.end - wall.start
            length = float(np.linalg.norm(direction))
            direction = direction / max(length, 1e-9)
            surfaces.append(
                Surface(
                    id=wall.id,
                    room=room.id,
                    kind="wall",
                    origin=np.array([wall.start[0], wall.start[1], floor_z]),
                    along=np.array([direction[0], direction[1], 0.0]),
                    up=np.array([0.0, 0.0, 1.0]),
                    normal=np.array([-direction[1], direction[0], 0.0]),  # rooms run anticlockwise
                    width=length,
                    height=height,
                )
            )
        first = room.walls[0]
        direction = (first.end - first.start) / max(np.linalg.norm(first.end - first.start), 1e-9)
        across = np.array([-direction[1], direction[0]])
        polygon = Polygon(room.polygon)
        local = (room.polygon - first.start) @ np.stack([direction, across]).T
        span = local.max(axis=0) - local.min(axis=0)
        corner = first.start + local[:, 0].min() * direction + local[:, 1].min() * across
        for kind, z, normal in (("floor", floor_z, 1.0), ("ceiling", floor_z + height, -1.0)):
            surfaces.append(
                Surface(
                    id=f"{room.id}-{kind}",
                    room=room.id,
                    kind=kind,
                    origin=np.array([corner[0], corner[1], z]),
                    along=np.array([direction[0], direction[1], 0.0]),
                    up=np.array([across[0], across[1], 0.0]),
                    normal=np.array([0.0, 0.0, normal]),
                    width=float(span[0]),
                    height=float(span[1]),
                    polygon=polygon,
                )
            )
    return surfaces


def first_hit(surfaces: list[Surface], origin: np.ndarray, direction: np.ndarray):
    """The first surface a ray meets, with (distance, u, v) on it; None if it meets none."""
    best = None
    for surface in surfaces:
        met = surface.meet(origin, direction)
        if met is None or not surface.contains(met[1], met[2]):
            continue
        if best is None or met[0] < best[1][0]:
            best = (surface, met)
    return best


def pixel_rays(K: np.ndarray, T_world_cam: np.ndarray, pixels: np.ndarray) -> tuple:
    """Camera position and unit ray directions in the plan's frame for (N, 2) pixels."""
    homogeneous = np.column_stack([pixels, np.ones(len(pixels))])
    directions = (np.linalg.inv(K) @ homogeneous.T).T @ T_world_cam[:3, :3].T
    directions /= np.linalg.norm(directions, axis=1)[:, None]
    return T_world_cam[:3, 3], directions
