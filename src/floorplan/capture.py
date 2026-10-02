"""The common form every tier front-end produces.

A front-end's only job is to turn raw files into a `Capture`: posed metric depth frames
with an honest statement of how uncertain the depth and the overall scale are. Everything
after this point (planes, layout, openings, intervals, output) is one code path that does
not know which tier the capture came from.

Conventions used everywhere downstream:

* lengths are in metres;
* the world frame is gravity-aligned with +z up;
* camera axes follow the OpenCV convention: +x right, +y down, +z forward;
* `T_world_cam` maps camera coordinates to world coordinates.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

TIERS = ("lidar", "video", "photo")


@dataclass(frozen=True)
class Frame:
    """One posed depth frame."""

    index: int  # frame number in the source capture
    timestamp: float  # seconds
    K: np.ndarray  # 3x3 intrinsics at depth-map resolution
    T_world_cam: np.ndarray  # 4x4 camera-to-world

    @property
    def position(self) -> np.ndarray:
        return self.T_world_cam[:3, 3]


@dataclass
class Capture:
    """Posed metric depth frames plus the uncertainty the front-end claims for them.

    Depth noise is modelled as `sigma(d) = depth_sigma_a + depth_sigma_b * d`. It describes
    random per-pixel error. `scale_sigma` is the relative 1-sigma error on the metric scale
    of the whole capture, which no amount of averaging removes; it is what makes intervals
    widen at the thinner tiers.
    """

    tier: str
    source: Path
    frames: list[Frame]
    depth_loader: Callable[[int], np.ndarray]  # position in `frames` -> HxW float32 metres
    confidence_loader: Callable[[int], np.ndarray] | None = None  # -> HxW uint8, higher is better
    depth_sigma_a: float = 0.002
    depth_sigma_b: float = 0.0025
    scale_sigma: float = 0.005
    room_of_frame: list[str] | None = None  # photo tier: the room folder each frame came from
    notes: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.tier not in TIERS:
            raise ValueError(f"unknown tier {self.tier!r}, expected one of {TIERS}")

    def __len__(self) -> int:
        return len(self.frames)

    def depth(self, i: int) -> np.ndarray:
        """Depth map of `frames[i]` in metres; 0 marks pixels with no measurement."""
        return self.depth_loader(i)

    def confidence(self, i: int) -> np.ndarray | None:
        return None if self.confidence_loader is None else self.confidence_loader(i)

    def depth_sigma(self, depth: np.ndarray) -> np.ndarray:
        return self.depth_sigma_a + self.depth_sigma_b * depth

    def subset(self, positions: list[int]) -> Capture:
        """A capture holding only the frames at the given positions (used for keyframes)."""
        positions = list(positions)
        depth_loader = self.depth_loader
        confidence_loader = self.confidence_loader
        return Capture(
            tier=self.tier,
            source=self.source,
            frames=[self.frames[p] for p in positions],
            depth_loader=lambda i: depth_loader(positions[i]),
            confidence_loader=(
                None if confidence_loader is None else lambda i: confidence_loader(positions[i])
            ),
            depth_sigma_a=self.depth_sigma_a,
            depth_sigma_b=self.depth_sigma_b,
            scale_sigma=self.scale_sigma,
            room_of_frame=(
                None if self.room_of_frame is None else [self.room_of_frame[p] for p in positions]
            ),
            notes=dict(self.notes),
        )

    def with_poses(self, poses: list[np.ndarray]) -> Capture:
        """The same capture with every `T_world_cam` replaced (used by drift correction)."""
        if len(poses) != len(self.frames):
            raise ValueError("one pose per frame is required")
        frames = [
            Frame(index=f.index, timestamp=f.timestamp, K=f.K, T_world_cam=np.asarray(T, float))
            for f, T in zip(self.frames, poses, strict=True)
        ]
        return Capture(
            tier=self.tier,
            source=self.source,
            frames=frames,
            depth_loader=self.depth_loader,
            confidence_loader=self.confidence_loader,
            depth_sigma_a=self.depth_sigma_a,
            depth_sigma_b=self.depth_sigma_b,
            scale_sigma=self.scale_sigma,
            room_of_frame=self.room_of_frame,
            notes=dict(self.notes),
        )


def select_keyframes(
    frames: list[Frame], min_translation: float = 0.05, min_rotation_deg: float = 4.0
) -> list[int]:
    """Positions of frames that moved or turned enough since the last kept frame.

    A phone records 30 to 60 frames a second and most of them are near-duplicates. Keeping
    a frame only when the camera has moved 5 cm or turned 4 degrees keeps the coverage and
    drops the redundancy, and the result does not depend on how fast the person walked.
    """
    if not frames:
        return []
    kept = [0]
    last = frames[0].T_world_cam
    cos_limit = np.cos(np.radians(min_rotation_deg))
    for i in range(1, len(frames)):
        T = frames[i].T_world_cam
        moved = np.linalg.norm(T[:3, 3] - last[:3, 3]) >= min_translation
        # cos of the rotation angle between the two orientations, from the trace of R_rel
        cos_angle = (np.trace(last[:3, :3].T @ T[:3, :3]) - 1.0) / 2.0
        if moved or cos_angle <= cos_limit:
            kept.append(i)
            last = T
    return kept
