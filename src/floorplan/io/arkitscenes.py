"""Reader for an ARKitScenes scene (Apple's public dataset of iPad LiDAR room scans).

Used for one purpose only: to run the LiDAR tier on real ARKit depth and poses when no
phone is at hand. It is a development check. ARKitScenes has no tape-measured ground truth,
so nothing read through here is reported as benchmark accuracy.

Layout of a scene from the `threedod` split:

    <id>_frames/lowres_depth/<id>_<time>.png      16-bit depth, millimetres, 256x192
    <id>_frames/lowres_wide/<id>_<time>.png       RGB at the same size
    <id>_frames/lowres_wide_intrinsics/<id>_<time>.pincam   width height fx fy cx cy
    <id>_frames/lowres_wide.traj                  time, axis-angle rotation, translation

The trajectory stores world-to-camera transforms (the dataset's own tools invert them), with
OpenCV camera axes and a gravity-aligned, z-up world.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation

from floorplan.capture import Capture, Frame
from floorplan.io.stray import (
    LIDAR_DEPTH_SIGMA_A,
    LIDAR_DEPTH_SIGMA_B,
    LIDAR_SCALE_SIGMA,
    _load_depth_file,
    _read_image,
)


def is_arkitscenes(path: Path) -> bool:
    path = Path(path)
    return any(path.glob("*_frames/lowres_wide.traj"))


def read_arkitscenes(path: Path | str) -> Capture:
    path = Path(path)
    frames_dir = next(path.glob("*_frames"))
    trajectory = np.loadtxt(frames_dir / "lowres_wide.traj")
    times = trajectory[:, 0]

    depth_files = sorted((frames_dir / "lowres_depth").glob("*.png"))
    frames: list[Frame] = []
    kept: list[Path] = []
    for number, file in enumerate(depth_files):
        stamp = float(file.stem.split("_", 1)[1])
        nearest = int(np.argmin(np.abs(times - stamp)))
        if abs(times[nearest] - stamp) > 0.06:
            continue  # no pose close enough in time to this depth frame
        world_to_camera = np.eye(4)
        world_to_camera[:3, :3] = Rotation.from_rotvec(trajectory[nearest, 1:4]).as_matrix()
        world_to_camera[:3, 3] = trajectory[nearest, 4:7]
        pincam = frames_dir / "lowres_wide_intrinsics" / f"{file.stem}.pincam"
        _, _, fx, fy, cx, cy = np.loadtxt(pincam)
        K = np.array([[fx, 0.0, cx], [0.0, fy, cy], [0.0, 0.0, 1.0]])
        frames.append(
            Frame(
                index=number,
                timestamp=stamp,
                K=K,
                T_world_cam=np.linalg.inv(world_to_camera),
                name=file.stem,
            )
        )
        kept.append(file)
    if not frames:
        raise ValueError(f"{path} has no depth frame with a matching pose")

    rgb_dir = frames_dir / "lowres_wide"

    def image_loader(file: Path, frame: Frame):
        def load():
            rgb = rgb_dir / file.name
            if not rgb.is_file():
                return None
            return _read_image(rgb)[:, :, ::-1], frame.K, _load_depth_file(file)

        return load

    return Capture(
        tier="lidar",
        source=path,
        frames=frames,
        depth_loader=lambda i: _load_depth_file(kept[i]),
        confidence_loader=None,
        depth_sigma_a=LIDAR_DEPTH_SIGMA_A,
        depth_sigma_b=LIDAR_DEPTH_SIGMA_B,
        scale_sigma=LIDAR_SCALE_SIGMA,
        notes={"format": "arkitscenes", "frames_without_pose": len(depth_files) - len(frames)},
        images={
            frame.name: image_loader(file, frame) for frame, file in zip(frames, kept, strict=True)
        },
    )
