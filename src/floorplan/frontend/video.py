"""Reading walkthrough clips: finding the clip in a capture and sampling sharp frames.

The video tier itself (camera poses from structure from motion, depth from a depth model)
is in `sfm.py`. An earlier version followed the camera from depth and walls alone; on the
real clip of a bedroom it was 90 cm off, and it was removed (docs/decisions/0003).
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from floorplan.io.intake import VIDEO_SUFFIXES, videos_in


def find_video(capture: Path) -> Path:
    """The walkthrough clip of a capture: the file itself, or the largest clip in the folder."""
    capture = Path(capture)
    if capture.is_file():
        return capture
    videos = videos_in(capture)
    if not videos:
        raise FileNotFoundError(f"no video clip ({', '.join(VIDEO_SUFFIXES)}) found in {capture}")
    return max(videos, key=lambda p: p.stat().st_size)


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
