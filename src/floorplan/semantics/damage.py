"""Damage regions: found in the images, reported on a surface, in metres.

1. A detector looks at each image for the damage classes listed in `configs/semantics.yaml`
   and returns boxes with scores.
2. The middle of each box is followed along its camera ray to the first surface of the plan
   it meets. That decides which wall, ceiling or floor the damage is on. If the sensor's own
   depth says the pixel is well in front of that surface, the box is on furniture or on
   something hanging in the room, not on the surface, and it is left out.
3. The box's corners are pushed along their rays onto that surface. Their spread on the
   surface is the damage's extent: width, height and bounding area.
4. The same patch is usually seen in several images. Boxes of the same class on the same
   surface that overlap are merged, weighting each view by its score and by how squarely
   it looked at the surface (an oblique view stretches a box).

The extent reported is that of the bounding box on the surface. It bounds the damage from
outside, so it is an upper estimate of its area; it is what a repair is scoped from.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import yaml
from scipy.optimize import least_squares

from floorplan.pipeline import Plan
from floorplan.semantics.surfaces import Surface, first_hit, pixel_rays, surfaces_of
from floorplan.uncertainty.budget import Measurement, quadrature

ROOT = Path(__file__).resolve().parents[3]


def load_semantics_config(path: Path | None = None) -> dict:
    return yaml.safe_load((path or ROOT / "configs" / "semantics.yaml").read_text())


@dataclass
class Sighting:
    """One box in one image, placed on a surface."""

    kind: str
    surface: Surface
    u0: float
    u1: float
    v0: float
    v1: float
    score: float
    squareness: float  # 1 when the camera looked straight at the surface, toward 0 when oblique
    frame: str


@dataclass
class DamageRegion:
    id: str
    kind: str
    room: str
    surface: str
    surface_kind: str
    width: Measurement
    height: Measurement
    area: Measurement
    along_surface: float  # metres from the surface's first corner to the region's near edge
    above_floor: float  # walls: metres from the floor to the region's lower edge
    centre: np.ndarray  # (3,) in the plan's frame
    along: np.ndarray  # (3,) unit: the direction `width` is measured in
    score: float
    views: int
    frames: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "class": self.kind,
            "room": self.room,
            "surface": self.surface,
            "surface_kind": self.surface_kind,
            "extent": {
                "width": self.width.to_dict(),
                "height": self.height.to_dict(),
                "bounding_area": self.area.to_dict(),
            },
            "position": {
                "along_surface": round(self.along_surface, 3),
                "above_floor": round(self.above_floor, 3),
                "centre": [round(float(c), 3) for c in self.centre],
            },
            "detector_score": round(self.score, 3),
            "views": self.views,
            "frames": self.frames,
        }


def place_box(
    box: tuple[float, float, float, float],
    K: np.ndarray,
    T_world_cam: np.ndarray,
    surfaces: list[Surface],
    depth_at_centre: float | None = None,
) -> tuple[Surface, float, float, float, float, float] | None:
    """Put an image box on a surface: (surface, u0, u1, v0, v1, squareness) or None."""
    x0, y0, x1, y1 = box
    centre = np.array([[(x0 + x1) / 2, (y0 + y1) / 2]])
    origin, directions = pixel_rays(K, T_world_cam, centre)
    hit = first_hit(surfaces, origin, directions[0])
    if hit is None:
        return None
    surface, (distance, _, _) = hit
    if depth_at_centre is not None and depth_at_centre > 0:
        # depth is measured along the optical axis; compare like with like
        forward = T_world_cam[:3, 2]
        expected = distance * float(directions[0] @ forward)
        if depth_at_centre < expected - max(0.25, 0.12 * expected):
            return None  # something stands in front of the surface there
    corners = np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y1]])
    _, corner_rays = pixel_rays(K, T_world_cam, corners)
    met = [surface.meet(origin, ray) for ray in corner_rays]
    if any(m is None for m in met):
        return None
    u = np.clip([m[1] for m in met], 0.0, surface.width)
    v = np.clip([m[2] for m in met], 0.0, surface.height)
    squareness = float(abs(directions[0] @ surface.normal))

    # Pushing the box's corners onto the surface over-states the size when the view is
    # tilted: a rectangle on a wall appears as a trapezoid, and the box around a trapezoid
    # is wider than the rectangle at one end. So solve the question the right way round:
    # which rectangle on the surface would appear in the image with exactly this box?
    world_to_cam = np.linalg.inv(T_world_cam)

    def box_of(rectangle: np.ndarray) -> np.ndarray:
        ua, ub, va, vb = rectangle
        points = np.array(
            [
                surface.origin + a * surface.along + b * surface.up
                for a, b in ((ua, va), (ub, va), (ub, vb), (ua, vb))
            ]
        )
        camera = points @ world_to_cam[:3, :3].T + world_to_cam[:3, 3]
        if np.any(camera[:, 2] <= 1e-6):
            return np.full(4, 1e6)
        pixels = (camera / camera[:, 2:3]) @ K.T
        return np.array(
            [pixels[:, 0].min(), pixels[:, 1].min(), pixels[:, 0].max(), pixels[:, 1].max()]
        )

    start = np.array([u.min(), u.max(), v.min(), v.max()])
    solved = least_squares(
        lambda r: box_of(r) - np.array(box),
        start,
        bounds=(
            [0.0, 0.0, 0.0, 0.0],
            [surface.width, surface.width, surface.height, surface.height],
        ),
    )
    if solved.success and np.abs(solved.fun).max() < 3.0:  # within three pixels on every side
        ua, ub, va, vb = solved.x
        u, v = np.array(sorted((ua, ub))), np.array(sorted((va, vb)))
    return surface, float(u.min()), float(u.max()), float(v.min()), float(v.max()), squareness


def _overlap(a: Sighting, b: Sighting) -> float:
    """Intersection over union of two boxes on the same surface."""
    width = min(a.u1, b.u1) - max(a.u0, b.u0)
    height = min(a.v1, b.v1) - max(a.v0, b.v0)
    if width <= 0 or height <= 0:
        return 0.0
    both = width * height
    return both / ((a.u1 - a.u0) * (a.v1 - a.v0) + (b.u1 - b.u0) * (b.v1 - b.v0) - both)


def merge_sightings(sightings: list[Sighting], min_overlap: float = 0.2) -> list[list[Sighting]]:
    """Group sightings that show the same patch."""
    groups: list[list[Sighting]] = []
    for sighting in sorted(sightings, key=lambda s: -s.score):
        for group in groups:
            first = group[0]
            if (
                first.kind == sighting.kind
                and first.surface.id == sighting.surface.id
                and any(_overlap(sighting, other) >= min_overlap for other in group)
            ):
                group.append(sighting)
                break
        else:
            groups.append([sighting])
    return groups


def find_sightings(
    plan: Plan,
    images: dict[str, Callable[[], tuple[np.ndarray, np.ndarray, np.ndarray | None]]],
    detect: Callable[[np.ndarray, list[str], float], list],
    classes: dict[str, dict],
) -> list[Sighting]:
    """Every box of every class in every image, placed on a surface.

    `images` maps a frame name to a loader returning (RGB image, intrinsics for that image,
    depth map aligned with the image or None). `detect` is `Detector.detect`.
    """
    surfaces = surfaces_of(plan)
    phrase_class = {phrase: kind for kind, spec in classes.items() for phrase in spec["phrases"]}
    phrases = list(phrase_class)
    lowest = min(spec["threshold"] for spec in classes.values())
    poses = {frame.name: frame.T_world_cam for frame in plan.frames}
    sightings = []
    for name, loader in images.items():
        if name not in poses:
            continue
        loaded = loader()
        if loaded is None:
            continue
        image, K, depth = loaded
        for detection in detect(image, phrases, lowest):
            kind = phrase_class[detection.label]
            if detection.score < classes[kind]["threshold"]:
                continue
            x0, y0, x1, y1 = detection.box
            # a box that fills most of the image is the model describing the scene, not a patch
            if (x1 - x0) * (y1 - y0) > 0.6 * image.shape[0] * image.shape[1]:
                continue
            centre_depth = None
            if depth is not None:
                row = int(
                    np.clip((y0 + y1) / 2 * depth.shape[0] / image.shape[0], 0, depth.shape[0] - 1)
                )
                column = int(
                    np.clip((x0 + x1) / 2 * depth.shape[1] / image.shape[1], 0, depth.shape[1] - 1)
                )
                centre_depth = float(depth[row, column])
            placed = place_box(detection.box, K, poses[name], surfaces, centre_depth)
            if placed is None:
                continue
            surface, u0, u1, v0, v1, squareness = placed
            if u1 - u0 < 0.02 or v1 - v0 < 0.02:
                continue
            sightings.append(
                Sighting(kind, surface, u0, u1, v0, v1, detection.score, squareness, name)
            )
    return sightings


def damage_regions(
    sightings: list[Sighting], plan: Plan, scale_sigma: float, min_views: int = 1
) -> list[DamageRegion]:
    """Merged, measured damage regions."""
    regions = []
    counters: dict[str, int] = {}
    for group in merge_sightings(sightings):
        if len({s.frame for s in group}) < min_views:
            continue
        weights = np.array([s.score * s.squareness**2 for s in group])
        weights = weights / weights.sum()
        u0, u1, v0, v1 = (
            float(weights @ np.array([getattr(s, key) for s in group]))
            for key in ("u0", "u1", "v0", "v1")
        )
        surface = group[0].surface
        width, height = u1 - u0, v1 - v0
        # the spread between views, a floor for where a box edge really is, and scale
        spread_w = float(np.std([s.u1 - s.u0 for s in group])) if len(group) > 1 else 0.15 * width
        spread_h = float(np.std([s.v1 - s.v0 for s in group])) if len(group) > 1 else 0.15 * height
        sigma_w = quadrature(spread_w, 0.03, scale_sigma * width)
        sigma_h = quadrature(spread_h, 0.03, scale_sigma * height)
        counters[surface.room] = counters.get(surface.room, 0) + 1
        centre = surface.origin + (u0 + u1) / 2 * surface.along + (v0 + v1) / 2 * surface.up
        regions.append(
            DamageRegion(
                id=f"{surface.room}-DMG{counters[surface.room]}",
                kind=group[0].kind,
                room=surface.room,
                surface=surface.id,
                surface_kind=surface.kind,
                width=Measurement(width, sigma_w),
                height=Measurement(height, sigma_h),
                area=Measurement(
                    width * height, quadrature(height * sigma_w, width * sigma_h), unit="m2"
                ),
                along_surface=u0,
                above_floor=v0 if surface.kind == "wall" else 0.0,
                centre=centre,
                along=surface.along,
                score=float(max(s.score for s in group)),
                views=len({s.frame for s in group}),
                frames=sorted({s.frame for s in group}),
            )
        )
    return regions
