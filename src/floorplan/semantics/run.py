"""Add damage regions, concealed-damage flags and scope items to a finished plan.

Geometry comes first and does not depend on any of this. With no detector weights present
the plan is returned as it is, with a warning, so the LiDAR tier still runs on a machine
that has no learned model installed.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from floorplan.pipeline import Plan
from floorplan.semantics.damage import (
    Sighting,
    damage_regions,
    find_sightings,
    load_semantics_config,
)
from floorplan.semantics.rules import raise_flags
from floorplan.semantics.scope import build_scope


def _spread(names: list[str], limit: int) -> list[str]:
    if len(names) <= limit:
        return names
    picks = np.linspace(0, len(names) - 1, limit).round().astype(int)
    return [names[i] for i in sorted(set(picks))]


def _reject_openings_on_reflectors(plan: Plan, sightings: list[Sighting]) -> list[str]:
    """Drop openings that sit where a mirror or a television was seen.

    To a depth sensor a mirror is a hole in the wall with a room behind it, and a dark
    screen returns nothing, which also reads as a hole. The image knows better.
    """
    notes = []
    kept = []
    for opening in plan.openings:
        u0 = opening.position_along_wall
        u1, v0, v1 = u0 + opening.width.value, opening.sill, opening.sill + opening.height.value
        culprit = None
        for sighting in sightings:
            if sighting.surface.id != opening.wall or sighting.kind not in ("mirror", "television"):
                continue
            width = min(u1, sighting.u1) - max(u0, sighting.u0)
            height = min(v1, sighting.v1) - max(v0, sighting.v0)
            if width > 0 and height > 0 and width * height > 0.5 * (u1 - u0) * (v1 - v0):
                culprit = sighting.kind
                break
        if culprit is None:
            kept.append(opening)
        else:
            notes.append(
                f"{opening.id} was dropped: a {culprit} is seen there, which reads as an "
                "opening to a depth sensor"
            )
    if notes:
        plan.openings = kept
        plan.adjacency = [link for link in plan.adjacency if any(o.id == link[2] for o in kept)]
    return notes


def add_semantics(plan: Plan, detector, config: dict | None = None) -> Plan:
    """Fill `plan.damage`, `plan.flags` and `plan.scope` from the plan's images."""
    config = config or load_semantics_config()
    if not plan.images:
        plan.warnings.append("no images are attached to this capture; damage was not assessed")
        return plan
    if detector is None or not detector.available:
        plan.warnings.append(
            "the detection model is not installed (python scripts/fetch_weights.py "
            "owlv2-base-patch16-ensemble); damage was not assessed"
        )
        return plan

    names = _spread(sorted(plan.images), int(config.get("max_images", 40)))
    images = {name: plan.images[name] for name in names}
    classes = {**config["damage"], **config["structure"]}
    sightings = find_sightings(plan, images, detector.detect, classes)
    damage = [s for s in sightings if s.kind in config["damage"]]
    structure = [s for s in sightings if s.kind in config["structure"]]

    plan.warnings.extend(_reject_openings_on_reflectors(plan, structure))
    min_views = int(config.get("min_views", {}).get(plan.tier, 1))
    plan.damage = damage_regions(
        damage,
        plan,
        float(plan.stats.get("scale_sigma", 0.05)),
        min_views=min(min_views, max(1, len(images))),
    )
    plan.flags = raise_flags(plan, plan.damage)
    plan.scope = build_scope(plan, plan.damage, plan.flags)
    plan.stats["semantics"] = {
        "detector": detector.describe(),
        "images_examined": len(images),
        "boxes_on_surfaces": len(sightings),
        "mirrors_or_screens_seen": sum(s.kind in ("mirror", "television") for s in structure),
    }
    return plan


def read_video_frames(path: Path, wanted: set[int], long_side: int = 1280) -> dict[int, tuple]:
    """Selected frames of a video as (RGB image, scale applied), read in one pass."""
    reader = cv2.VideoCapture(str(path))
    frames: dict[int, tuple] = {}
    try:
        index, last = 0, max(wanted) if wanted else -1
        while index <= last and reader.grab():
            if index in wanted:
                ok, frame = reader.retrieve()
                if ok:
                    height, width = frame.shape[:2]
                    scale = min(1.0, long_side / max(height, width))
                    if scale < 1.0:
                        frame = cv2.resize(
                            frame,
                            (round(width * scale), round(height * scale)),
                            interpolation=cv2.INTER_AREA,
                        )
                    frames[index] = (cv2.cvtColor(frame, cv2.COLOR_BGR2RGB), scale)
            index += 1
    finally:
        reader.release()
    return frames
