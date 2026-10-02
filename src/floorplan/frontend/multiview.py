"""Photo and video tiers on a multi-view model: images in, a capture of posed depth out.

    images of one scene  ->  MapAnything (poses, metric depth, intrinsics)
                         ->  level the frame (z up, floor at z = 0)
                         ->  Capture  ->  the same back-end as the LiDAR tier

For photos each room folder is one scene; the rooms are joined afterwards at their doors
(`stitch.py`). For video the clip is one scene, sampled to a bounded number of frames so the
model's run time stays bounded on a laptop.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import cv2
import numpy as np
from shapely.geometry import Point, Polygon

from floorplan.capture import Capture, Frame
from floorplan.frontend.photo import IMAGE_SUFFIXES, _rename, room_folders
from floorplan.frontend.video import find_video, sample_frames
from floorplan.frontend.views import image_loader
from floorplan.models.multiview import MultiViewModel, level_views
from floorplan.pipeline import PipelineConfig, Plan, config_for, run
from floorplan.stitch import stitch

# Relative 1-sigma of the metric scale of a scene reconstructed from images. Replaced by
# benchmark values once there are any; until then this is the spread measured for image
# depth against LiDAR on one real room.
PHOTO_SCALE_SIGMA = 0.06
VIDEO_SCALE_SIGMA = 0.05
MAX_VIDEO_FRAMES = 32


def images_to_capture(
    images: list[np.ndarray],
    names: list[str],
    sources: list[Path | None],
    model: MultiViewModel,
    tier: str,
    scale_sigma: float,
    source: Path,
    room: str | None = None,
) -> Capture:
    """Posed, levelled metric depth frames for images of one scene."""
    posed = model.reconstruct(images, names, sources)
    poses, _ = level_views(posed)
    frames = [
        Frame(index=k, timestamp=float(k), K=item.view.K, T_world_cam=poses[k], name=names[k])
        for k, item in enumerate(posed)
    ]
    depths = [item.view.depth for item in posed]
    return Capture(
        tier=tier,
        source=source,
        frames=frames,
        depth_loader=lambda i: depths[i],
        depth_sigma_a=0.01,
        depth_sigma_b=0.01,
        scale_sigma=scale_sigma,
        room_of_frame=None if room is None else [room] * len(frames),
        notes={"views": names, "multi_view_model": model.describe()},
        images={
            frame.name: image_loader(item.view, depths[k])
            for k, (frame, item) in enumerate(zip(frames, posed, strict=True))
        },
    )


def room_plan(
    name: str, files: list[Path], model: MultiViewModel, config: PipelineConfig | None = None
) -> Plan:
    """A single-room plan from the photos of one room."""
    from floorplan.models.depth import load_image

    config = config or config_for("photo")
    images = [load_image(path)[0] for path in files]
    names = [f"{name}/{path.stem}" for path in files]
    capture = images_to_capture(
        images, names, list(files), model, "photo", PHOTO_SCALE_SIGMA, files[0].parent, room=name
    )
    plan = run(capture, config)

    # keep the room the photos were taken in; anything else was seen through a doorway
    cameras = np.array([frame.position[:2] for frame in capture.frames])

    def cameras_inside(room) -> int:
        polygon = Polygon(room.polygon)
        return sum(polygon.contains(Point(c)) for c in cameras)

    main = max(plan.rooms, key=lambda room: (cameras_inside(room), room.floor_area.value))
    openings = [o for o in plan.openings if o.room == main.id]
    for opening in openings:
        opening.other_room = None  # neighbours are assigned when the rooms are joined
    plan = replace(
        plan, rooms=[main], openings=openings, adjacency=[], footprint_area=main.floor_area
    )
    plan.stats["photos"] = len(files)
    _rename(plan, main.id, name)
    return plan


def photo_plan(capture: Path, model: MultiViewModel, config: PipelineConfig | None = None) -> Plan:
    """The stitched property plan for a photo capture (one folder of photos per room)."""
    plans, failed = [], []
    for name, files in room_folders(capture).items():
        try:
            plans.append(room_plan(name, files, model, config))
        except (ValueError, RuntimeError) as problem:
            failed.append(f"{name}: {problem}")
    if not plans:
        raise RuntimeError("no room could be rebuilt from the photos: " + "; ".join(failed))
    plan = stitch(plans)
    plan.warnings.extend(failed)
    return plan


def video_capture(path: Path, model: MultiViewModel, max_frames: int = MAX_VIDEO_FRAMES) -> Capture:
    """A capture of posed depth frames for a walkthrough clip."""
    path = find_video(path)
    frames, times = sample_frames(path, rate=2.0, max_frames=max_frames)
    names = [f"{path.stem}_{k:04d}" for k in range(len(frames))]
    capture = images_to_capture(
        frames, names, [None] * len(frames), model, "video", VIDEO_SCALE_SIGMA, path
    )
    capture.notes.update(
        {"frames_sampled": len(frames), "clip_seconds": round(times[-1], 1) if times else 0.0}
    )
    return capture


def write_frames(images: list[np.ndarray], folder: Path) -> list[Path]:
    """Save RGB arrays as image files (used by tests and by the cache)."""
    folder.mkdir(parents=True, exist_ok=True)
    paths = []
    for k, image in enumerate(images):
        path = folder / f"{k:04d}.jpg"
        cv2.imwrite(str(path), cv2.cvtColor(image, cv2.COLOR_RGB2BGR))
        paths.append(path)
    return paths


__all__ = ["IMAGE_SUFFIXES", "images_to_capture", "photo_plan", "room_plan", "video_capture"]
