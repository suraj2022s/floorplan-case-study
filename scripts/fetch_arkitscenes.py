"""Download the public-data benchmark: one bedroom of Apple's ARKitScenes, three LiDAR scans.

    python scripts/fetch_arkitscenes.py           # the three captures (155 MB)
    python scripts/fetch_arkitscenes.py --laser   # + the laser scan the truth came from (1.9 GB)
    python scripts/fetch_arkitscenes.py --video   # + the original video of scan 47333462 (530 MB)

ARKitScenes is published by Apple under its own licence (see
https://github.com/apple/ARKitScenes); nothing from it is redistributed in this repository
except the room dimensions read off the laser scan.
"""

from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch import download  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://docs-assets.developer.apple.com/ml-research/datasets/arkitscenes/v1"
CAPTURES = {  # video id -> SHA-256 of its 3dod zip
    "47333462": "74d53fb42cc3b0fb11eac5e59dc9fd86a0f912c14f4f02e4dcd07355bee0e8f6",
    "47333463": "768041da1bbb7f0159cfa6a4319897ce29b23f32a6902ee3c81236eee33017e9",
    "47333468": "acc3d0b569337ef75fbd5cf48dcebd6abe5464e3c72e8301ad2af22f4602560e",
}
VISIT = "467138"
LASER_SCAN = "190170"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--laser", action="store_true")
    parser.add_argument("--video", action="store_true")
    arguments = parser.parse_args()
    folder = ROOT / ".cache" / "arkitscenes"
    for video_id, sha256 in CAPTURES.items():
        archive = download(
            f"{BASE}/threedod/Training/{video_id}.zip", folder / f"{video_id}.zip", sha256=sha256
        )
        if not (folder / video_id).is_dir():
            with zipfile.ZipFile(archive) as bundle:
                bundle.extractall(folder)
    if arguments.laser:
        laser = folder / "laser" / VISIT
        for suffix in ("_pose.txt", ".ply"):
            download(
                f"{BASE}/raw/laser_scanner_point_clouds/{VISIT}/{LASER_SCAN}{suffix}",
                laser / f"{LASER_SCAN}{suffix}",
            )
    if arguments.video:
        download(f"{BASE}/raw/Training/47333462/47333462.mov", folder / "raw" / "47333462.mov")
    print(f"ready in {folder}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
