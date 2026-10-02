"""The photo and video readers against files written by a real iPhone 15 Pro.

The files are not in the repository (their licence does not allow redistribution);
`python scripts/fetch_samples.py` downloads them and these tests then run. Without them the
tests are skipped, and say so.
"""

from pathlib import Path

import numpy as np
import pytest

SAMPLES = Path(__file__).resolve().parents[1] / ".cache" / "samples"
IPHONE = SAMPLES / "iphone15pro"
RECORDING = SAMPLES / "stray_kitchen" / "pepper-dicing"

needs_iphone_files = pytest.mark.skipif(
    not (IPHONE / "iphone_15_pro.heic").is_file(),
    reason="real iPhone sample files not fetched (python scripts/fetch_samples.py iphone15pro)",
)
needs_recording = pytest.mark.skipif(
    not (RECORDING / "odometry.csv").is_file(),
    reason="real recording not fetched (python scripts/fetch_samples.py stray-kitchen)",
)
pytest.importorskip("pillow_heif", reason="the learned extra is not installed")


@needs_iphone_files
def test_portrait_heic_from_the_wide_lens_comes_out_upright():
    from floorplan.models.depth import load_image

    # stored with "rotate 90" set, taken with the 0.5x lens (35 mm equivalent: 14 mm)
    image, fov_x = load_image(IPHONE / "iphone_15_pro.heic")
    assert image.shape == (4032, 3024, 3)  # taller than wide: upright, and not turned twice
    assert fov_x == pytest.approx(85.67, abs=0.05)


@needs_iphone_files
def test_square_photo_keeps_the_lens_field_of_view():
    from floorplan.models.depth import load_image

    # a 1:1 photo from the 24 mm main camera: the full frame is 73.7 degrees wide, and the
    # square cut from it keeps the frame's height, so it is 56.8 degrees wide
    image, fov_x = load_image(IPHONE / "2024-03-28_17-26-14.jpg")
    assert image.shape == (3024, 3024, 3)
    assert fov_x == pytest.approx(56.8, abs=0.1)


@needs_iphone_files
def test_portrait_clip_is_read_upright():
    from floorplan.frontend.video import sample_frames

    # recorded holding the phone upright: stored 1920x1080 with a rotation flag
    frames, times = sample_frames(IPHONE / "2024-03-28_17-26-17.mov", rate=2.0, max_frames=8)
    assert 2 <= len(frames) <= 9
    assert all(frame.shape == (1920, 1080, 3) for frame in frames)
    assert times == sorted(times) and times[-1] > 5.0


@needs_iphone_files
def test_live_photo_is_one_photo_not_a_video(tmp_path):
    import shutil

    from floorplan.io.intake import find_capture, room_folders

    room = tmp_path / "hall"
    room.mkdir()
    for name in ("IMG_0011.heic", "IMG_0011.mov"):
        shutil.copyfile(IPHONE / name, room / name)
    found = find_capture(tmp_path)
    assert found.tier == "photo"
    assert [p.name for p in room_folders(found.path)["hall"]] == ["IMG_0011.heic"]


@needs_recording
def test_whole_real_recording_reads_and_its_video_matches():
    import cv2

    from floorplan.io.stray import read_stray

    capture = read_stray(RECORDING)
    assert len(capture.frames) == 2063 and capture.notes["frames_without_depth"] == 0
    assert capture.notes["rgb_size"] == [1920, 1440]
    stamps = np.array([frame.timestamp for frame in capture.frames])
    assert np.median(np.diff(stamps)) == pytest.approx(1 / 60, rel=0.02)  # 60 frames a second
    reader = cv2.VideoCapture(str(RECORDING / "rgb.mp4"))
    try:
        assert int(reader.get(cv2.CAP_PROP_FRAME_COUNT)) == len(capture.frames)
        ok, frame = reader.read()
        assert ok and frame.shape == (1440, 1920, 3)
    finally:
        reader.release()
