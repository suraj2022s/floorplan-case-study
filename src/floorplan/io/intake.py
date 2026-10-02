"""Finding the capture inside whatever was handed over.

A capture reaches the pipeline the way a phone hands it over, which is rarely a tidy folder:

* a .zip from the share sheet, or a folder wrapped in another folder after unzipping;
* a single clip passed as a file;
* photo folders that also hold what an iPhone writes next to a still: the short .MOV of a
  Live Photo (same name as the still), .AAE edit sidecars, and, after a trip through a Mac,
  `._IMG_0001.HEIC` resource files and a `__MACOSX` folder.

None of that is the user's problem. This module finds the capture, names its tier and lists
what it left out, so the rest of the pipeline only ever sees files it can read.
"""

from __future__ import annotations

import hashlib
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from floorplan.io.arkitscenes import is_arkitscenes
from floorplan.io.stray import is_stray_capture

IMAGE_SUFFIXES = (".heic", ".heif", ".jpg", ".jpeg", ".png")
VIDEO_SUFFIXES = (".mov", ".mp4", ".m4v")
RAW_SUFFIXES = (".dng",)  # Apple ProRAW: not read, and said so
JUNK_FOLDERS = {"__MACOSX", ".Spotlight-V100", ".Trashes", ".fseventsd"}
JUNK_FILES = {"thumbs.db", "desktop.ini"}
MAX_DEPTH = 3  # wrapper folders to look through


class CaptureNotFound(ValueError):
    """Nothing the pipeline can read was found where the user pointed."""


@dataclass
class Intake:
    path: Path  # what the tier's reader is given
    tier: str  # lidar, video or photo
    name: str  # names the output folder
    source: Path  # what the user pointed at
    notes: list[str] = field(default_factory=list)


def is_junk(path: Path) -> bool:
    name = path.name
    return name.startswith(".") or name in JUNK_FOLDERS or name.lower() in JUNK_FILES


def _files(folder: Path, suffixes: tuple[str, ...]) -> list[Path]:
    return sorted(
        p
        for p in folder.iterdir()
        if p.is_file() and not is_junk(p) and p.suffix.lower() in suffixes
    )


def images_in(folder: Path) -> list[Path]:
    """Still images in a folder, in file-name order (the order an iPhone took them in)."""
    return _files(folder, IMAGE_SUFFIXES)


def live_photo_clips(folder: Path) -> list[Path]:
    """The .MOV halves of Live Photos: clips named like a still in the same folder."""
    stills = {p.stem.lower() for p in images_in(folder)}
    return [p for p in _files(folder, VIDEO_SUFFIXES) if p.stem.lower() in stills]


def videos_in(folder: Path) -> list[Path]:
    """Clips in a folder, leaving out the Live Photo halves."""
    live = set(live_photo_clips(folder))
    return [p for p in _files(folder, VIDEO_SUFFIXES) if p not in live]


def raw_photos_in(folder: Path) -> list[Path]:
    return _files(folder, RAW_SUFFIXES)


def _subfolders(folder: Path) -> list[Path]:
    return sorted(p for p in folder.iterdir() if p.is_dir() and not is_junk(p))


def room_folders(capture: Path) -> dict[str, list[Path]]:
    """Room name -> its photos. A folder of photos with no sub-folders is one room."""
    capture = Path(capture)
    if capture.is_file():
        return {capture.stem: [capture]}
    rooms = {folder.name: images_in(folder) for folder in _subfolders(capture)}
    rooms = {name: files for name, files in rooms.items() if files}
    if not rooms and images_in(capture):
        rooms = {capture.name: images_in(capture)}
    if not rooms:
        raise CaptureNotFound(f"no photos found in {capture}")
    return rooms


def _unzip(archive: Path, workdir: Path | None) -> Path:
    """Extract a .zip once; a second run on the same file reuses the extraction."""
    digest = hashlib.sha256()
    with open(archive, "rb") as handle:
        digest.update(handle.read(1 << 20))
    digest.update(str(archive.stat().st_size).encode())
    base = Path(workdir) if workdir else Path(tempfile.gettempdir()) / "floorplan-intake"
    target = base / f"{archive.stem}-{digest.hexdigest()[:10]}"
    done = target / ".extracted"
    if not done.is_file():
        target.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(archive) as bundle:
            members = [
                m
                for m in bundle.namelist()
                if not any(part in JUNK_FOLDERS or part.startswith(".") for part in Path(m).parts)
            ]
            bundle.extractall(target, members)
        done.write_text(str(archive))
    return target


def _kind(folder: Path) -> str | None:
    """What a folder holds, looking no deeper than its room sub-folders."""
    if is_stray_capture(folder) or is_arkitscenes(folder):
        return "lidar"
    photo_rooms = [sub for sub in _subfolders(folder) if images_in(sub)]
    clips, stills = videos_in(folder), images_in(folder)
    if photo_rooms and not clips:
        return "photo"
    if clips and not stills and not photo_rooms:
        return "video"
    if stills and not clips:
        return "photo"
    if clips or stills or photo_rooms:
        return "mixed"
    return None


def find_capture(path: Path | str, tier: str = "auto", workdir: Path | None = None) -> Intake:
    """Locate the capture at `path` and name its tier.

    `tier` other than "auto" forces the tier: a Stray Scanner folder run with tier "video"
    uses its rgb.mp4 as a plain clip, for instance.
    """
    source = Path(path)
    if not source.exists():
        raise CaptureNotFound(f"{source} does not exist")
    notes: list[str] = []
    name = source.stem if source.is_file() else source.name
    root = source

    if source.is_file():
        suffix = source.suffix.lower()
        if suffix == ".zip":
            root = _unzip(source, workdir)
            notes.append(f"unpacked {source.name}")
        elif suffix in VIDEO_SUFFIXES:
            return Intake(source, _forced(tier, "video", source), name, source, notes)
        elif suffix in IMAGE_SUFFIXES:
            return Intake(source, _forced(tier, "photo", source), name, source, notes)
        else:
            raise CaptureNotFound(
                f"{source.name} is not a capture: expected a folder, a .zip, a clip "
                f"({', '.join(VIDEO_SUFFIXES)}) or a photo"
            )

    # look through wrapper folders: capture/ -> capture/3f2a9c/ -> odometry.csv
    folder, kind = root, _kind(root)
    for _ in range(MAX_DEPTH):
        if kind is not None:
            break
        inner = _subfolders(folder)
        recordings = [sub for sub in inner if is_stray_capture(sub)]
        if len(recordings) > 1:
            raise CaptureNotFound(
                f"{folder} holds {len(recordings)} LiDAR recordings "
                f"({', '.join(sub.name for sub in recordings[:4])}...); run one at a time"
            )
        if len(inner) != 1:
            break
        folder = inner[0]
        kind = _kind(folder)
    if kind is None:
        raise CaptureNotFound(
            f"{source} is not a recognised capture: expected a Stray Scanner recording "
            "(odometry.csv and depth/), a walkthrough clip, or one folder of photos per room"
        )
    if kind == "mixed":
        if tier == "auto":
            raise CaptureNotFound(
                f"{folder} holds both photos and a walkthrough clip; say which to use with "
                "--tier photo or --tier video"
            )
        kind = tier
    raws = [p for sub in [folder, *_subfolders(folder)] for p in raw_photos_in(sub)]
    if raws and kind == "photo":
        notes.append(
            f"{len(raws)} ProRAW (.dng) file(s) were not read; shoot in the default photo format"
        )
    live = [p for sub in [folder, *_subfolders(folder)] for p in live_photo_clips(sub)]
    if live and kind == "photo":
        notes.append(f"{len(live)} Live Photo clip(s) next to the stills were left out")
    return Intake(folder, _forced(tier, kind, folder), name, source, notes)


def _forced(tier: str, found: str, where: Path) -> str:
    """The tier to run: the one found, unless the user forced one the files can serve."""
    if tier in ("auto", found):
        return found
    if tier not in ("lidar", "video", "photo"):
        raise CaptureNotFound(f"unknown tier {tier!r}; use auto, lidar, video or photo")
    if tier == "lidar":
        raise CaptureNotFound(
            f"{where} is not a LiDAR recording (no odometry.csv and depth/); "
            f"it looks like a {found} capture"
        )
    if tier == "video" and found == "lidar" and (where / "rgb.mp4").is_file():
        return "video"  # the recording's own clip, read without its depth and poses
    if tier == "video" and where.is_dir() and not videos_in(where):
        raise CaptureNotFound(f"no walkthrough clip found in {where}")
    if tier == "photo" and where.is_dir() and found != "photo" and not images_in(where):
        raise CaptureNotFound(f"no photos found in {where}")
    return tier
