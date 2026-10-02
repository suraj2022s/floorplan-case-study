"""The capture reader against a real recording from the capture app.

Every other test reads files this repository wrote, so a shared misunderstanding of the
format would pass them all. These tests read four frames of a real Stray Scanner recording
made on a LiDAR iPhone (tests/data/stray_real_excerpt, CC BY 4.0, see its ATTRIBUTION.md).

The recording shows a kitchen worktop from about 25 cm. Two facts about it need no ground
truth: a worktop is level, and the worktop does not move between frames. Both hold only if
the camera poses are read the right way round.
"""

from pathlib import Path

import numpy as np
import pytest

from floorplan.geometry.cloud import backproject
from floorplan.io.stray import ODOMETRY_HEADER, read_stray

EXCERPT = Path(__file__).parent / "data" / "stray_real_excerpt"
# the other reading of the format: camera axes as ARKit has them (y up, z towards the user)
ARKIT_CAMERA_AXES = np.diag([1.0, -1.0, -1.0, 1.0])


@pytest.fixture(scope="module")
def capture():
    return read_stray(EXCERPT)


def _points(capture, i):
    depth = capture.depth(i).astype(np.float64)
    trusted = (depth > 0.05) & (capture.confidence(i) >= 2)
    return backproject(depth, capture.frames[i].K), trusted, depth


def _dominant_plane_normal(points: np.ndarray) -> np.ndarray:
    """Unit normal of the largest plane in a point set, facing the camera at the origin."""
    rng = np.random.default_rng(0)
    best_count, best = 0, None
    for _ in range(300):
        sample = points[rng.choice(len(points), 3, replace=False)]
        normal = np.cross(sample[1] - sample[0], sample[2] - sample[0])
        if np.linalg.norm(normal) < 1e-9:
            continue
        normal /= np.linalg.norm(normal)
        inliers = np.abs((points - sample[0]) @ normal) < 0.006
        if inliers.sum() > best_count:
            best_count, best = int(inliers.sum()), (normal, sample[0])
    normal, origin = best
    on_plane = points[np.abs((points - origin) @ normal) < 0.006]
    centre = on_plane.mean(axis=0)
    normal = np.linalg.svd(on_plane - centre, full_matrices=False)[2][2]
    return -normal if normal @ centre > 0 else normal


def test_the_app_writes_the_header_this_reader_expects():
    header = (EXCERPT / "odometry.csv").read_text().splitlines()[0]
    assert header == ODOMETRY_HEADER


def test_real_recording_is_read(capture):
    assert capture.tier == "lidar"
    assert [frame.index for frame in capture.frames] == [0, 1031, 1758, 2062]
    assert capture.notes["depth_size"] == [256, 192]
    depth = capture.depth(0)
    assert depth.shape == (192, 256) and depth.dtype == np.float32
    assert 0.1 < float(np.median(depth)) < 1.0  # metres: a worktop at arm's length
    assert set(np.unique(capture.confidence(0))) <= {0, 1, 2}
    # intrinsics are written for the 1920x1440 video and must be scaled to the depth image
    K = capture.frames[0].K
    assert K[0, 0] == pytest.approx(1382.7905 * 256 / 1920, rel=1e-6)
    assert K[0, 2] == pytest.approx(958.13293 * 256 / 1920, rel=1e-6)


@pytest.mark.parametrize("i", [0, 3])
def test_worktop_is_level_only_with_the_poses_as_written(capture, i):
    points, trusted, _ = _points(capture, i)
    normal = _dominant_plane_normal(points[trusted])
    as_written = capture.frames[i].T_world_cam[:3, :3] @ normal
    flipped = (capture.frames[i].T_world_cam @ ARKIT_CAMERA_AXES)[:3, :3] @ normal
    tilt = np.degrees(np.arccos(np.clip(as_written[2], -1, 1)))
    tilt_flipped = np.degrees(np.arccos(np.clip(flipped[2], -1, 1)))
    assert tilt < 5.0, f"worktop tilted {tilt:.1f} degrees with the poses as written"
    assert tilt_flipped > 150.0  # with the camera axes flipped the worktop faces the floor


def _reprojection_error(capture, i, j, camera_axes=None) -> float:
    """Median depth disagreement when frame i's points are viewed from frame j."""
    points, trusted, _ = _points(capture, i)
    Ti, Tj = capture.frames[i].T_world_cam, capture.frames[j].T_world_cam
    if camera_axes is not None:
        Ti, Tj = Ti @ camera_axes, Tj @ camera_axes
    world = points[trusted] @ Ti[:3, :3].T + Ti[:3, 3]
    seen = (world - Tj[:3, 3]) @ Tj[:3, :3]
    seen = seen[seen[:, 2] > 0.05]
    K = capture.frames[j].K
    u = np.round(K[0, 0] * seen[:, 0] / seen[:, 2] + K[0, 2]).astype(int)
    v = np.round(K[1, 1] * seen[:, 1] / seen[:, 2] + K[1, 2]).astype(int)
    depth, confidence = capture.depth(j), capture.confidence(j)
    inside = (u >= 0) & (u < depth.shape[1]) & (v >= 0) & (v < depth.shape[0])
    u, v, z = u[inside], v[inside], seen[inside, 2]
    valid = (depth[v, u] > 0.05) & (confidence[v, u] >= 2)
    assert valid.sum() > 5000
    return float(np.median(np.abs(depth[v, u][valid] - z[valid])))


def test_frames_agree_only_with_the_poses_as_written(capture):
    # frames 0 and 1758 are 23.5 degrees and 9 cm apart
    assert _reprojection_error(capture, 0, 2) < 0.006
    assert _reprojection_error(capture, 2, 0) < 0.006
    assert _reprojection_error(capture, 0, 2, ARKIT_CAMERA_AXES) > 0.05


def test_a_worktop_is_not_reported_as_a_room(capture):
    from floorplan.pipeline import config_for, run

    with pytest.raises(RuntimeError, match="no wall and no ceiling"):
        run(capture, config_for("lidar"))
