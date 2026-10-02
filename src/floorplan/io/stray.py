"""Reader and writer for Stray Scanner captures (the LiDAR tier's capture app).

Layout of a capture folder, from the app's own `docs/format.md`:

    rgb.mp4              HEVC video, normally 1920x1440
    depth/000000.png     16-bit PNG, millimetres, normally 256x192, one per video frame
    confidence/000000.png  8-bit PNG with values 0, 1, 2 (2 is the most confident)
    odometry.csv         timestamp, frame, x, y, z, qx, qy, qz, qw[, fx, fy, cx, cy, ...]
    camera_matrix.csv    3x3 intrinsics of the RGB frame (kept by the app for old readers)
    imu.csv              accelerometer and gyroscope samples

Pose convention, checked against the app's source (`OdometryEncoder.swift`) and its example
script (`stray_visualize.py`), not assumed:

* position is the ARKit camera position in the ARKit world frame, which is gravity-aligned
  with +y up;
* the quaternion is the ARKit camera orientation multiplied by a half turn about the camera
  x axis, so the camera axes are already OpenCV style (x right, y down, z forward). No
  further camera-axis flip is needed, and applying one would mirror the scene.

So the only conversion done here is rotating the y-up world into our z-up world.
"""

from __future__ import annotations

import csv
from pathlib import Path

import cv2
import numpy as np
from scipy.spatial.transform import Rotation

from floorplan.capture import Capture, Frame

# Rotation taking ARKit world coordinates (x, y up, z) to ours (x, -z, y up->z). det = +1.
ARKIT_TO_ZUP = np.array(
    [
        [1.0, 0.0, 0.0, 0.0],
        [0.0, 0.0, -1.0, 0.0],
        [0.0, 1.0, 0.0, 0.0],
        [0.0, 0.0, 0.0, 1.0],
    ]
)

DEFAULT_RGB_SIZE = (1920, 1440)  # (width, height) when rgb.mp4 is absent or unreadable
ODOMETRY_HEADER = (
    "timestamp, frame, x, y, z, qx, qy, qz, qw, fx, fy, cx, cy, "
    "distortion_center_x, distortion_center_y"
)

# Starting noise model for ARKit scene depth; replaced by measured values once a real
# device has been characterised against a laser.
LIDAR_DEPTH_SIGMA_A = 0.002
LIDAR_DEPTH_SIGMA_B = 0.0025
LIDAR_SCALE_SIGMA = 0.005


def is_stray_capture(path: Path) -> bool:
    path = Path(path)
    return (path / "odometry.csv").is_file() and (path / "depth").is_dir()


def _read_image(path: Path) -> np.ndarray:
    """cv2.imread fails on non-ASCII Windows paths; decode from bytes instead."""
    data = np.fromfile(str(path), dtype=np.uint8)
    image = cv2.imdecode(data, cv2.IMREAD_UNCHANGED)
    if image is None:
        raise OSError(f"could not decode image {path}")
    return image


def _write_image(path: Path, image: np.ndarray) -> None:
    ok, buffer = cv2.imencode(path.suffix, image)
    if not ok:
        raise OSError(f"could not encode image {path}")
    buffer.tofile(str(path))


def _rgb_size(path: Path) -> tuple[int, int]:
    video = path / "rgb.mp4"
    if video.is_file():
        reader = cv2.VideoCapture(str(video))
        try:
            width = int(reader.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(reader.get(cv2.CAP_PROP_FRAME_HEIGHT))
        finally:
            reader.release()
        if width > 0 and height > 0:
            return width, height
    return DEFAULT_RGB_SIZE


def _load_depth_file(path: Path) -> np.ndarray:
    if path.suffix == ".npy":
        millimetres = np.load(path)
    else:
        millimetres = _read_image(path)
    return millimetres.astype(np.float32) / 1000.0


def read_stray(path: Path | str) -> Capture:
    """Read a Stray Scanner folder into a `Capture` with a z-up world frame."""
    path = Path(path)
    if not is_stray_capture(path):
        raise FileNotFoundError(f"{path} is not a Stray Scanner capture (odometry.csv, depth/)")

    with open(path / "odometry.csv", newline="") as handle:
        rows = list(csv.reader(handle))
    header = [name.strip() for name in rows[0]]
    column = {name: i for i, name in enumerate(header)}
    for required in ("timestamp", "frame", "x", "y", "z", "qx", "qy", "qz", "qw"):
        if required not in column:
            raise ValueError(f"odometry.csv has no {required!r} column; header is {header}")

    fallback_K = None
    if (path / "camera_matrix.csv").is_file():
        fallback_K = np.loadtxt(path / "camera_matrix.csv", delimiter=",").reshape(3, 3)

    rgb_width, rgb_height = _rgb_size(path)
    depth_dir = path / "depth"
    confidence_dir = path / "confidence"

    frames: list[Frame] = []
    depth_files: list[Path] = []
    confidence_files: list[Path | None] = []
    missing = 0
    depth_size: tuple[int, int] | None = None

    def value(row: list[str], name: str) -> float | None:
        if name not in column or column[name] >= len(row):
            return None
        text = row[column[name]].strip()
        return float(text) if text else None

    for row in rows[1:]:
        if not row or not "".join(row).strip():
            continue
        number = int(float(row[column["frame"]]))
        depth_file = depth_dir / f"{number:06d}.png"
        if not depth_file.is_file():
            depth_file = depth_dir / f"{number:06d}.npy"
        if not depth_file.is_file():
            missing += 1
            continue
        if depth_size is None:
            first = _load_depth_file(depth_file)
            depth_size = (first.shape[1], first.shape[0])

        intrinsics = [value(row, name) for name in ("fx", "fy", "cx", "cy")]
        if all(v is not None for v in intrinsics):
            fx, fy, cx, cy = intrinsics
        elif fallback_K is not None:
            fx, fy, cx, cy = fallback_K[0, 0], fallback_K[1, 1], fallback_K[0, 2], fallback_K[1, 2]
        else:
            raise ValueError(
                "no intrinsics: odometry.csv has no fx/fy/cx/cy and there is no camera_matrix.csv"
            )
        sx = depth_size[0] / rgb_width
        sy = depth_size[1] / rgb_height
        K = np.array([[fx * sx, 0.0, cx * sx], [0.0, fy * sy, cy * sy], [0.0, 0.0, 1.0]])

        T_arkit_cam = np.eye(4)
        quaternion = [value(row, name) for name in ("qx", "qy", "qz", "qw")]
        T_arkit_cam[:3, :3] = Rotation.from_quat(quaternion).as_matrix()
        T_arkit_cam[:3, 3] = [value(row, name) for name in ("x", "y", "z")]

        frames.append(
            Frame(
                index=number,
                timestamp=float(value(row, "timestamp")),
                K=K,
                T_world_cam=ARKIT_TO_ZUP @ T_arkit_cam,
            )
        )
        depth_files.append(depth_file)
        confidence_file = confidence_dir / f"{number:06d}.png"
        confidence_files.append(confidence_file if confidence_file.is_file() else None)

    if not frames:
        raise ValueError(f"{path} has no frame with both a pose and a depth map")

    has_confidence = any(f is not None for f in confidence_files)

    def load_confidence(i: int) -> np.ndarray:
        file = confidence_files[i]
        if file is None:  # treat a missing confidence map as fully confident
            return np.full((depth_size[1], depth_size[0]), 2, dtype=np.uint8)
        return _read_image(file)

    return Capture(
        tier="lidar",
        source=path,
        frames=frames,
        depth_loader=lambda i: _load_depth_file(depth_files[i]),
        confidence_loader=load_confidence if has_confidence else None,
        depth_sigma_a=LIDAR_DEPTH_SIGMA_A,
        depth_sigma_b=LIDAR_DEPTH_SIGMA_B,
        scale_sigma=LIDAR_SCALE_SIGMA,
        notes={
            "format": "stray_scanner",
            "rgb_size": [rgb_width, rgb_height],
            "depth_size": list(depth_size),
            "frames_without_depth": missing,
        },
    )


def write_stray(
    path: Path | str,
    poses_world_cam: list[np.ndarray],
    depths_m: list[np.ndarray],
    confidences: list[np.ndarray],
    K_rgb: np.ndarray,
    timestamps: list[float],
) -> None:
    """Write posed depth frames in Stray Scanner layout (used by the synthetic rooms).

    Poses are given in our z-up world and are converted back to the ARKit y-up world, so a
    capture written here and read with `read_stray` round-trips exactly.
    """
    path = Path(path)
    (path / "depth").mkdir(parents=True, exist_ok=True)
    (path / "confidence").mkdir(parents=True, exist_ok=True)
    zup_to_arkit = np.linalg.inv(ARKIT_TO_ZUP)

    lines = [ODOMETRY_HEADER]
    for i, (T_world_cam, depth, confidence, stamp) in enumerate(
        zip(poses_world_cam, depths_m, confidences, timestamps, strict=True)
    ):
        T_arkit_cam = zup_to_arkit @ T_world_cam
        x, y, z = T_arkit_cam[:3, 3]
        qx, qy, qz, qw = Rotation.from_matrix(T_arkit_cam[:3, :3]).as_quat()
        lines.append(
            f"{stamp:.6f}, {i:06d}, {x:.6f}, {y:.6f}, {z:.6f}, "
            f"{qx:.8f}, {qy:.8f}, {qz:.8f}, {qw:.8f}, "
            f"{K_rgb[0, 0]:.4f}, {K_rgb[1, 1]:.4f}, {K_rgb[0, 2]:.4f}, {K_rgb[1, 2]:.4f}, , "
        )
        millimetres = np.clip(np.round(depth * 1000.0), 0, 65535).astype(np.uint16)
        _write_image(path / "depth" / f"{i:06d}.png", millimetres)
        _write_image(path / "confidence" / f"{i:06d}.png", confidence.astype(np.uint8))

    (path / "odometry.csv").write_text("\n".join(lines) + "\n", newline="\n")
    np.savetxt(path / "camera_matrix.csv", K_rgb, delimiter=",", fmt="%.6f")
