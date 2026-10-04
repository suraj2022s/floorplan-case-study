"""Finding the capture in what an iPhone, a Mac or a zip actually hands over."""

import zipfile

import pytest

from floorplan.io.intake import CaptureNotFound, find_capture, images_in, room_folders, videos_in
from floorplan.io.stray import ODOMETRY_HEADER


def _touch(folder, *names):
    folder.mkdir(parents=True, exist_ok=True)
    for name in names:
        (folder / name).write_bytes(b"")


def _stray(folder):
    (folder / "depth").mkdir(parents=True)
    (folder / "odometry.csv").write_text(ODOMETRY_HEADER + "\n")
    _touch(folder, "rgb.mp4", "camera_matrix.csv")


def test_room_folders_of_photos(tmp_path):
    _touch(tmp_path / "kitchen", "IMG_0101.HEIC", "IMG_0102.HEIC")
    _touch(tmp_path / "bedroom", "IMG_0103.jpg", "IMG_0104.JPG")
    found = find_capture(tmp_path)
    assert found.tier == "photo" and found.path == tmp_path
    rooms = room_folders(found.path)
    assert list(rooms) == ["bedroom", "kitchen"]
    assert [p.name for p in rooms["kitchen"]] == ["IMG_0101.HEIC", "IMG_0102.HEIC"]


def test_live_photo_clips_do_not_make_a_photo_folder_a_video(tmp_path):
    # an iPhone with Live Photos on writes IMG_0101.HEIC and IMG_0101.MOV side by side
    _touch(tmp_path, "IMG_0101.HEIC", "IMG_0101.MOV", "IMG_0102.HEIC", "IMG_0102.MOV")
    _touch(tmp_path, "IMG_0101.AAE")
    found = find_capture(tmp_path)
    assert found.tier == "photo"
    assert videos_in(tmp_path) == []
    assert any("Live Photo" in note for note in found.notes)


def test_files_a_mac_leaves_behind_are_ignored(tmp_path):
    _touch(tmp_path / "hall", "IMG_0001.HEIC", "._IMG_0001.HEIC", ".DS_Store")
    _touch(tmp_path / "__MACOSX" / "hall", "._IMG_0001.HEIC")
    assert [p.name for p in images_in(tmp_path / "hall")] == ["IMG_0001.HEIC"]
    assert list(room_folders(find_capture(tmp_path).path)) == ["hall"]


def test_a_clip_can_be_passed_as_a_file_or_in_a_folder(tmp_path):
    _touch(tmp_path / "walk", "IMG_2210.MOV")
    as_file = find_capture(tmp_path / "walk" / "IMG_2210.MOV")
    assert as_file.tier == "video" and as_file.name == "IMG_2210"
    as_folder = find_capture(tmp_path / "walk")
    assert as_folder.tier == "video" and as_folder.name == "walk"


def test_recording_inside_a_wrapper_folder(tmp_path):
    _stray(tmp_path / "from_phone" / "3f2a9c41d0")
    found = find_capture(tmp_path / "from_phone")
    assert found.tier == "lidar"
    assert found.path == tmp_path / "from_phone" / "3f2a9c41d0"


def test_recording_in_a_zip(tmp_path):
    _stray(tmp_path / "source" / "3f2a9c41d0")
    archive = tmp_path / "scan.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        for file in (tmp_path / "source").rglob("*"):
            bundle.write(file, file.relative_to(tmp_path / "source"))
        bundle.writestr("__MACOSX/3f2a9c41d0/._odometry.csv", b"")
    found = find_capture(archive, workdir=tmp_path / "work")
    assert found.tier == "lidar" and found.name == "scan"  # outputs are named after the zip
    assert (found.path / "odometry.csv").is_file()
    assert not (found.path.parent / "__MACOSX").exists()
    # a second run reuses the extraction
    assert find_capture(archive, workdir=tmp_path / "work").path == found.path


def test_a_recording_can_be_run_as_a_plain_clip(tmp_path):
    _stray(tmp_path / "scan")
    assert find_capture(tmp_path / "scan").tier == "lidar"
    assert find_capture(tmp_path / "scan", tier="video").tier == "video"


def test_two_recordings_are_not_guessed_between(tmp_path):
    _stray(tmp_path / "a")
    _stray(tmp_path / "b")
    with pytest.raises(CaptureNotFound, match="one at a time"):
        find_capture(tmp_path)


def test_photos_and_a_clip_together_need_a_choice(tmp_path):
    _touch(tmp_path, "IMG_0001.HEIC", "IMG_0002.HEIC", "walkthrough.MOV")
    with pytest.raises(CaptureNotFound, match="--tier"):
        find_capture(tmp_path)
    assert find_capture(tmp_path, tier="photo").tier == "photo"
    assert find_capture(tmp_path, tier="video").tier == "video"


def test_proraw_is_reported_not_silently_dropped(tmp_path):
    _touch(tmp_path / "study", "IMG_0001.HEIC", "IMG_0002.DNG")
    found = find_capture(tmp_path)
    assert any("ProRAW" in note for note in found.notes)


def test_an_empty_folder_is_an_error_a_person_can_act_on(tmp_path):
    with pytest.raises(CaptureNotFound, match="not a recognised capture"):
        find_capture(tmp_path)
    with pytest.raises(CaptureNotFound, match="not a LiDAR recording"):
        _touch(tmp_path / "walk", "clip.mov")
        find_capture(tmp_path / "walk", tier="lidar")


def test_a_clip_followed_only_in_part_says_so():
    from floorplan.cli import partial_track_warning

    # the assessors' floor_only recording: 82 of 350 frames placed, in 18 pieces
    warning = partial_track_warning(
        {"frames_sampled": 350, "frames_placed": 82, "reconstructions": [74] + [10] * 17}
    )
    assert warning is not None and "23%" in warning and "18 pieces" in warning
    # the benchmark clip: 200 of 241 placed, no warning
    assert partial_track_warning({"frames_sampled": 241, "frames_placed": 200}) is None
