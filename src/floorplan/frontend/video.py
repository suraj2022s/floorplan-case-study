"""Video tier: a handheld walkthrough clip to a capture of posed depth frames.

1. Frames are sampled from the clip at about two per second, taking the sharper of two
   neighbouring frames each time, and capped so a long clip still runs in a few minutes.
2. The lens does not change during a clip, so its field of view is estimated once, as the
   median of the depth model's estimate over the first frames, and then held fixed. Letting
   it float per frame would change the scale of the room from frame to frame.
3. Each frame gets metric depth from the depth model and is levelled (`views.py`).
4. The camera path is recovered from the frames themselves (`track.py`).

The result is the same kind of capture the LiDAR tier produces, with larger uncertainties,
and goes through the same back-end.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from floorplan.capture import Capture
from floorplan.frontend.track import track_capture, track_views
from floorplan.frontend.views import LevelView, level_view

VIDEO_SUFFIXES = (".mov", ".mp4", ".m4v")
VIDEO_SCALE_SIGMA = 0.04  # relative 1-sigma of the depth model's scale, averaged over a clip
TRACKING_WALL_MIN_TOP = 1.0  # metres: lower surfaces still help follow the camera


def find_video(capture: Path) -> Path:
    capture = Path(capture)
    if capture.is_file():
        return capture
    videos = sorted(p for p in capture.iterdir() if p.suffix.lower() in VIDEO_SUFFIXES)
    if not videos:
        raise FileNotFoundError(f"no video clip (.mov, .mp4) found in {capture}")
    return videos[0]


def sample_frames(path: Path, rate: float = 2.0, max_frames: int = 300) -> tuple[list, list]:
    """Sharp RGB frames sampled through the clip, and their times in seconds."""
    reader = cv2.VideoCapture(str(path))
    if not reader.isOpened():
        raise OSError(f"could not open video {path}")
    try:
        video_rate = reader.get(cv2.CAP_PROP_FPS) or 30.0
        total = int(reader.get(cv2.CAP_PROP_FRAME_COUNT))
        stride = max(1, round(video_rate / rate))
        if total > 0 and total / stride > max_frames:
            stride = int(np.ceil(total / max_frames))
        frames, times = [], []
        index = 0
        while True:
            if not reader.grab():
                break
            if index % stride == 0:
                ok, first = reader.retrieve()
                if not ok:
                    break
                best, best_sharpness = first, _sharpness(first)
                # the next frame costs one more decode; keep whichever is sharper
                if reader.grab():
                    index += 1
                    ok, second = reader.retrieve()
                    if ok and _sharpness(second) > best_sharpness:
                        best = second
                frames.append(cv2.cvtColor(best, cv2.COLOR_BGR2RGB))
                times.append(index / video_rate)
            index += 1
    finally:
        reader.release()
    if len(frames) < 2:
        raise ValueError(f"{path} has fewer than two readable frames")
    return frames, times


def _sharpness(frame: np.ndarray) -> float:
    small = cv2.resize(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), (320, 240))
    return float(cv2.Laplacian(small, cv2.CV_64F).var())


def video_capture(path: Path, model, rate: float = 2.0, max_frames: int = 300) -> Capture:
    """A capture of posed depth frames for a walkthrough clip. `model` is a `DepthModel`."""
    path = find_video(path)
    frames, times = sample_frames(path, rate, max_frames)

    # one lens, one field of view: estimate it from the first frames, then fix it
    estimates = []
    for k, frame in enumerate(frames[:8]):
        view = model.predict(frame, None, name=f"{path.stem}_fov_{k}")
        estimates.append(np.degrees(2 * np.arctan(view.depth.shape[1] / (2 * view.K[0, 0]))))
    fov_x = float(np.median(estimates))

    levelled: list[LevelView] = []
    kept_times: list[float] = []
    for k, frame in enumerate(frames):
        view = model.predict(frame, fov_x, name=f"{path.stem}_{k:04d}", source=path)
        try:
            levelled.append(level_view(view, wall_min_top=TRACKING_WALL_MIN_TOP))
            kept_times.append(times[k])
        except ValueError:
            continue  # a frame with no usable depth (lens covered, all sky) is skipped
    track = track_views(levelled)
    capture = track_capture(levelled, track, path, kept_times, scale_sigma=VIDEO_SCALE_SIGMA)
    capture.notes.update(
        {
            "frames_sampled": len(frames),
            "field_of_view_deg": round(fov_x, 2),
            "tracking_notes": track.notes,
        }
    )
    return capture
