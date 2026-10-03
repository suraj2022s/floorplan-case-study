"""One still image turned into a levelled, metric depth view.

A photo or a video frame arrives with a metric depth map from a learned model, but with no
pose. Two things can be recovered from the single image itself, and both are done here:

* which way is up. Floors and ceilings face along gravity and walls face across it, so the
  up direction is the axis that floor and ceiling normals agree with and wall normals are
  perpendicular to;
* how the camera is turned relative to the walls. Rooms are mostly built square, so wall
  normals cluster in directions 90 degrees apart; turning the view until its walls line up
  with the axes leaves only a multiple of 90 degrees unknown.

What a single image cannot give is where in the room the camera stood, and the turn in
steps of 90 degrees. Those come from fitting several views to one room (`room.py`).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

from floorplan.capture import Capture, Frame
from floorplan.geometry.cloud import CloudConfig, _normals, backproject, fragment_clouds
from floorplan.geometry.planes import Level, PlaneConfig, WallLine, find_level, find_wall_lines

# Depth from a learned model is smooth but not exact: a flat wall comes out slightly bowed.
# Plane finding on such depth needs wider bands than on LiDAR depth.
VIEW_CLOUD = CloudConfig(
    voxel=0.03,
    min_confidence=0,
    min_depth=0.3,
    max_depth=9.0,
    edge_abs=0.05,
    edge_rel=0.05,
    normal_step=3,
    batch_frames=1,
)
VIEW_PLANES = PlaneConfig(
    level_band=0.10,
    inlier_band=0.07,
    min_points=200,
    max_rms=0.06,
    copy_offset=0.20,
    copy_angle_deg=6.0,
)


KEEP_POINTS = 4000  # points kept per view for frame-to-frame alignment


@dataclass
class View:
    """A still image with metric depth, as a depth model provides it."""

    name: str
    depth: np.ndarray  # (H, W) metres, 0 where invalid
    K: np.ndarray  # 3x3 intrinsics at the depth map's resolution
    image: np.ndarray | None = None  # (H, W, 3) uint8 RGB at the same resolution
    normal: np.ndarray | None = None  # (H, W, 3) unit normals in the camera frame
    source: Path | None = None
    detail: np.ndarray | None = None  # JPEG bytes of a larger copy of the image, for damage


@dataclass
class LevelView:
    """A view in its own levelled frame: z up, floor at z = 0, walls along the axes."""

    view: View
    R_local_cam: np.ndarray  # 3x3: camera axes -> levelled, wall-aligned local frame
    camera_height: float  # metres above the floor
    forward: np.ndarray  # (2,) unit, the camera's viewing direction in the local frame
    walls: list[WallLine]  # in the local frame, camera at the origin
    floor: Level | None
    ceiling_height: float | None
    notes: list[str] = field(default_factory=list)
    # a thinned copy of the view's points and normals in the local frame, used to measure
    # how far the camera moved between two consecutive video frames
    points: np.ndarray = field(default_factory=lambda: np.zeros((0, 3)), repr=False)
    normals: np.ndarray = field(default_factory=lambda: np.zeros((0, 3)), repr=False)

    @property
    def facing_axis(self) -> int:
        """The view looks mostly along local +x (0), +y (1), -x (2) or -y (3)."""
        angle = np.degrees(np.arctan2(self.forward[1], self.forward[0]))
        return int(np.round(angle / 90.0)) % 4


def estimate_up(normals: np.ndarray, initial: np.ndarray | None = None) -> np.ndarray:
    """The up direction in the camera frame, from surface normals.

    Minimises (wall normals . up)^2 while maximising (floor and ceiling normals . up)^2,
    which is one eigenvector problem. It starts from "the top of the picture is up" and
    reclassifies surfaces a few times as the estimate improves.
    """
    up = np.array([0.0, -1.0, 0.0]) if initial is None else initial / np.linalg.norm(initial)
    for _ in range(6):
        along = normals @ up
        level = np.abs(along) > np.cos(np.radians(25.0))
        wall = np.abs(along) < np.sin(np.radians(20.0))
        if level.sum() + wall.sum() < 100:
            break
        scatter = normals[wall].T @ normals[wall] - normals[level].T @ normals[level]
        _, vectors = np.linalg.eigh(scatter)
        candidate = vectors[:, 0]
        up = candidate if candidate @ up > 0 else -candidate
    return up


def single_frame_capture(
    view: View, R_world_cam: np.ndarray, position: np.ndarray, scale: float = 1.0
) -> Capture:
    """A one-frame capture, so the shared plane-finding code can run on a single view."""
    T = np.eye(4)
    T[:3, :3] = R_world_cam
    T[:3, 3] = position
    depth = (view.depth * scale).astype(np.float32)
    return Capture(
        tier="photo",
        source=view.source or Path(view.name),
        frames=[Frame(index=0, timestamp=0.0, K=view.K, T_world_cam=T)],
        depth_loader=lambda i: depth,
        depth_sigma_a=0.01,
        depth_sigma_b=0.01,
        scale_sigma=0.05,
    )


def level_view(
    view: View,
    cloud_config: CloudConfig = VIEW_CLOUD,
    plane_config: PlaneConfig = VIEW_PLANES,
    wall_min_top: float | None = None,
) -> LevelView:
    """Level a view, put its floor at z = 0 and align its walls with the axes.

    `wall_min_top` is how high a vertical surface must reach to count as a wall. Left as
    None it follows the ceiling, which suits a photo taken from across the room. A video
    frame is often a close-up that shows a wall only up to head height; the tracker passes
    a low value so such frames still give it something to hold on to.
    """
    notes: list[str] = []
    valid = view.depth > 0
    points = backproject(view.depth.astype(np.float64), view.K)
    if view.normal is not None:
        normals = view.normal[valid]
    else:
        computed, has_normal = _normals(points, valid, cloud_config.normal_step)
        normals = computed[has_normal]
    up = estimate_up(normals[:: max(1, len(normals) // 60000)])

    # levelled frame: z up, x along the viewing direction projected onto the floor
    forward = np.array([0.0, 0.0, 1.0]) - up[2] * up
    forward /= np.linalg.norm(forward)
    R_level_cam = np.stack([forward, np.cross(up, forward), up])

    capture = single_frame_capture(view, R_level_cam, np.zeros(3))
    cloud = fragment_clouds(capture, cloud_config)[0][0]
    if len(cloud) == 0:
        raise ValueError(f"{view.name}: no usable depth")
    floor = find_level(cloud, facing_up=True, config=plane_config)
    ceiling = find_level(cloud, facing_up=False, config=plane_config)
    origin = np.zeros((1, 2))
    if floor is not None and float(floor.z_at(origin)[0]) < -0.5:
        camera_height = -float(floor.z_at(origin)[0])
    else:
        floor = None
        camera_height = 1.40
        notes.append("floor not visible; camera height assumed to be 1.40 m")
    ceiling_height = None
    if ceiling is not None and floor is not None:
        gap = float(ceiling.z_at(origin)[0] - floor.z_at(origin)[0])
        ceiling_height = gap if 1.8 < gap < 6.0 else None

    # re-run with the floor at z = 0, then turn the frame so the walls lie along the axes
    capture = single_frame_capture(view, R_level_cam, np.array([0.0, 0.0, camera_height]))
    cloud = fragment_clouds(capture, cloud_config)[0][0]
    floor0 = find_level(cloud, facing_up=True, config=plane_config) or Level(np.zeros(3), 0.0, 0)
    ceiling0 = find_level(cloud, facing_up=False, config=plane_config)
    walls = _own_walls(find_wall_lines(cloud, floor0, ceiling0, plane_config, min_top=wall_min_top))
    turn = 0.0
    if walls:
        strongest = max(walls, key=lambda wall: wall.count)
        angle = np.arctan2(strongest.normal[1], strongest.normal[0])
        turn = -((angle + np.pi / 4) % (np.pi / 2) - np.pi / 4)
    else:
        notes.append("no wall found in this view")
    c, s = np.cos(turn), np.sin(turn)
    R_turn = np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])
    aligned = [_turn_wall(wall, R_turn[:2, :2]) for wall in walls]
    step = max(1, len(cloud) // KEEP_POINTS)
    return LevelView(
        points=(cloud.xyz[::step] @ R_turn.T).astype(np.float32),
        normals=(cloud.normal[::step] @ R_turn.T).astype(np.float32),
        view=view,
        R_local_cam=R_turn @ R_level_cam,
        camera_height=camera_height,
        forward=R_turn[:2, :2] @ np.array([1.0, 0.0]),
        walls=aligned,
        floor=floor,
        ceiling_height=ceiling_height,
        notes=notes,
    )


def image_loader(view: View, depth: np.ndarray, long_side: int = 1600):
    """A loader for the damage stage: (RGB image, intrinsics for that image, depth).

    The image is the original file when there is one, at a higher resolution than the depth
    map, because small damage needs pixels. Returns None when the view has no image.
    """

    def load():
        if (
            view.source is not None
            and Path(view.source).suffix.lower() in (".heic", ".heif", ".jpg", ".jpeg", ".png")
            and Path(view.source).is_file()
        ):
            from floorplan.models.depth import load_image

            image, _ = load_image(Path(view.source))
            scale = min(1.0, long_side / max(image.shape[:2]))
            if scale < 1.0:
                image = cv2.resize(
                    image,
                    (round(image.shape[1] * scale), round(image.shape[0] * scale)),
                    interpolation=cv2.INTER_AREA,
                )
        elif view.detail is not None:
            image = cv2.cvtColor(cv2.imdecode(view.detail, cv2.IMREAD_COLOR), cv2.COLOR_BGR2RGB)
        elif view.image is not None:
            image = view.image
        else:
            return None
        factor_x = image.shape[1] / view.depth.shape[1]
        factor_y = image.shape[0] / view.depth.shape[0]
        K = view.K.copy()
        K[0, 0], K[1, 1] = K[0, 0] * factor_x, K[1, 1] * factor_y
        K[0, 2] = (view.K[0, 2] + 0.5) * factor_x - 0.5
        K[1, 2] = (view.K[1, 2] + 0.5) * factor_y - 0.5
        return image, K, depth

    return load


def _own_walls(walls: list[WallLine]) -> list[WallLine]:
    """Drop walls that lie behind another wall of the same view.

    Through an open door a photo also shows walls of the next room. Seen from this room
    they are behind one of its own walls: behind the side wall the door is in, or behind
    the far wall. A wall most of whose points are behind another wall is therefore not a
    wall of this room.

    Two details matter, both found on a corridor photographed from its end: a wall hides
    only what lies behind its own extent, not behind the whole infinite line through it; and
    only a wall of this room can hide another. Walls are taken nearest first, so a stretch of
    the next room's wall seen through a side door is dropped before it can "hide" the
    corridor's far end wall.
    """

    def behind(wall: WallLine, other: WallLine) -> bool:
        along = other.along(wall.points_xy)
        span = other.points_t
        inside = (along >= span.min() - 0.10) & (along <= span.max() + 0.10)
        return float(np.mean(inside & (other.distance(wall.points_xy) < -0.08))) > 0.7

    nearest_first = sorted(
        walls, key=lambda wall: float(np.median(np.linalg.norm(wall.points_xy, axis=1)))
    )
    kept: list[WallLine] = []
    for wall in nearest_first:
        if not any(behind(wall, other) for other in kept):
            kept.append(wall)
    return [wall for wall in walls if any(wall is k for k in kept)]


def _turn_wall(wall: WallLine, R: np.ndarray) -> WallLine:
    return WallLine(
        normal=R @ wall.normal,
        offset=wall.offset,
        rms=wall.rms,
        sigma_offset=wall.sigma_offset,
        sigma_angle=wall.sigma_angle,
        points_xy=wall.points_xy @ R.T,
        points_z=wall.points_z,
        points_w=wall.points_w,
        min_top=wall.min_top,
    )
