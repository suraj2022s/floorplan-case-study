"""The capture reader: file format and, above all, the pose convention."""

import numpy as np
from scipy.spatial.transform import Rotation

from floorplan.capture import select_keyframes
from floorplan.io.stray import ODOMETRY_HEADER, read_stray, write_stray


def _write_minimal_capture(folder, rotation_file, position_arkit, depth_mm=2000):
    """A one-frame capture written by hand, without using our own writer."""
    (folder / "depth").mkdir(parents=True)
    (folder / "confidence").mkdir()
    qx, qy, qz, qw = Rotation.from_matrix(rotation_file).as_quat()
    x, y, z = position_arkit
    (folder / "odometry.csv").write_text(
        ODOMETRY_HEADER + "\n"
        f"0.0, 000000, {x}, {y}, {z}, {qx}, {qy}, {qz}, {qw}, 1450.0, 1450.0, 960.0, 720.0, , \n"
    )
    import cv2

    cv2.imwrite(str(folder / "depth" / "000000.png"), np.full((192, 256), depth_mm, np.uint16))
    cv2.imwrite(str(folder / "confidence" / "000000.png"), np.full((192, 256), 2, np.uint8))


def test_pose_convention_matches_the_capture_app(tmp_path):
    """Derived from the app's source, independently of our writer.

    The app writes the ARKit camera orientation times a half turn about the camera x axis,
    and the ARKit camera position, in a y-up world. An ARKit camera with identity
    orientation looks along -z of the world. So a point 2 m straight ahead of a camera at
    (1, 1.4, -2) is at (1, 1.4, -4) in ARKit's world, which is (1, 4, 1.4) in our z-up world.
    """
    half_turn_about_x = np.diag([1.0, -1.0, -1.0])
    rotation_file = np.eye(3) @ half_turn_about_x
    _write_minimal_capture(tmp_path, rotation_file, (1.0, 1.4, -2.0))

    capture = read_stray(tmp_path)
    T = capture.frames[0].T_world_cam

    ahead = T @ np.array([0.0, 0.0, 2.0, 1.0])
    assert np.allclose(ahead[:3], [1.0, 4.0, 1.4], atol=1e-9)
    # a pixel below the image centre (camera +y) must land lower in the world
    below = T @ np.array([0.0, 1.0, 2.0, 1.0])
    assert np.allclose(below[:3], [1.0, 4.0, 0.4], atol=1e-9)
    # a pixel right of centre (camera +x) lands to the right when looking along +y
    right = T @ np.array([1.0, 0.0, 2.0, 1.0])
    assert np.allclose(right[:3], [2.0, 4.0, 1.4], atol=1e-9)


def test_intrinsics_are_scaled_to_the_depth_map(tmp_path):
    _write_minimal_capture(tmp_path, np.diag([1.0, -1.0, -1.0]), (0.0, 1.4, 0.0))
    capture = read_stray(tmp_path)
    K = capture.frames[0].K
    scale = 256 / 1920
    assert np.isclose(K[0, 0], 1450.0 * scale) and np.isclose(K[1, 1], 1450.0 * scale)
    assert np.isclose(K[0, 2], 960.0 * scale) and np.isclose(K[1, 2], 720.0 * scale)
    assert capture.depth(0).shape == (192, 256)
    assert np.allclose(capture.depth(0), 2.0)


def test_old_format_without_per_frame_intrinsics(tmp_path):
    """Captures from older app versions have nine columns and rely on camera_matrix.csv."""
    (tmp_path / "depth").mkdir()
    import cv2

    cv2.imwrite(str(tmp_path / "depth" / "000000.png"), np.full((192, 256), 1500, np.uint16))
    (tmp_path / "odometry.csv").write_text(
        "timestamp, frame, x, y, z, qx, qy, qz, qw\n0.0, 000000, 0, 0, 0, 1, 0, 0, 0\n"
    )
    np.savetxt(
        tmp_path / "camera_matrix.csv",
        [[1500.0, 0, 950.0], [0, 1500.0, 715.0], [0, 0, 1]],
        delimiter=",",
    )
    capture = read_stray(tmp_path)
    assert np.isclose(capture.frames[0].K[0, 0], 1500.0 * 256 / 1920)
    assert capture.confidence(0) is None


def test_write_then_read_round_trips(tmp_path):
    rng = np.random.default_rng(0)
    poses = []
    for _ in range(4):
        T = np.eye(4)
        T[:3, :3] = Rotation.random(random_state=rng.integers(1 << 30)).as_matrix()
        T[:3, 3] = rng.uniform(-3, 3, size=3)
        poses.append(T)
    depths = [rng.uniform(0.5, 4.0, size=(192, 256)).astype(np.float32) for _ in poses]
    confidences = [np.full((192, 256), 2, np.uint8) for _ in poses]
    K_rgb = np.array([[1450.0, 0, 960.0], [0, 1450.0, 720.0], [0, 0, 1]])
    write_stray(tmp_path, poses, depths, confidences, K_rgb, [0.0, 0.1, 0.2, 0.3])

    capture = read_stray(tmp_path)
    assert len(capture) == 4
    for frame, T in zip(capture.frames, poses, strict=True):
        assert np.allclose(frame.T_world_cam, T, atol=1e-5)
    assert np.abs(capture.depth(2) - depths[2]).max() <= 0.0005 + 1e-6  # millimetre storage


def test_keyframes_drop_near_duplicates():
    from floorplan.capture import Frame

    def frame(i, x):
        T = np.eye(4)
        T[0, 3] = x
        return Frame(index=i, timestamp=i / 60, K=np.eye(3), T_world_cam=T)

    frames = [frame(i, 0.011 * i) for i in range(21)]  # 1.1 cm steps: every 5th clears 5 cm
    assert select_keyframes(frames, min_translation=0.05) == [0, 5, 10, 15, 20]
