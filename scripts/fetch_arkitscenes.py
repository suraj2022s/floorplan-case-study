"""Download the public-data benchmark: four rooms of Apple's ARKitScenes, three LiDAR scans each.

    python scripts/fetch_arkitscenes.py           # the twelve captures (about 1.1 GB)
    python scripts/fetch_arkitscenes.py --laser   # + the laser scans of the truth (4 x 1.9 GB)
    python scripts/fetch_arkitscenes.py --video   # + the original video of scan 47333462 (530 MB)

The bedroom 467138 is the first room; 423441, 438802 and 482863 were added for the held-out
ceiling check of fix-loop round 3 (bench/benchmarks/arkitscenes.yaml says how they were chosen).

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
MORE_CAPTURES = {  # video id -> (fold, SHA-256 of its 3dod zip)
    "42897672": ("Validation", "252f230368542caebd9f66bd09e0f0d3ab292c3c8eeb625c715285f7c90fd5c1"),
    "42897678": ("Validation", "bdd2ac995d70689afd7abf0051455a9d7241b75dd4c90e3abcf0b51b80ccf585"),
    "42897688": ("Validation", "bae9ab3c8997b696b28a015997e8a6f20aecb0ebf0a3927bebb43bb172954f36"),
    "44358256": ("Training", "f1553e4f435d7b7391e855964576c1de3a3ffc0b5ea196aad11c258cc40c9631"),
    "44358257": ("Training", "8c48e66b71c89435cb1c357a3a46a1fbd8856890dd37d24ec331a906705c4387"),
    "44358258": ("Training", "3c334fed3f8559e4edf7af3d4fbcad5a1a696b701f8a77bbda2aa984fec27b8c"),
    "48017890": ("Training", "9eb8da3d9384968e3598e6fc9ea1e177703f9b3fff043c10a372a0edd9fd8684"),
    "48017892": ("Training", "1034bd4f6480a183a08d2d91307bd676be664f572bbdeabf9dd405275d657532"),
    "48017893": ("Training", "731a860c78d66c5f0c4eb087184fe91f409db6d5f675c333e7ce61411dca91da"),
}
MORE_LASERS = {  # visit -> (laser scan id, SHA-256 of its pose file, of its point cloud)
    "423441": (
        "179157",
        "5c3991222b48f7739e39b0088a2e660ed91c86657ceac9e0aabe8fd2221f06fc",
        "1921833edcc3cac0bb22ef1c4c0dcedc236d6f63109f2f09385ddb14aa8cb257",
    ),
    "438802": (
        "176283",
        "c1978d5e1f731cccc2a69a54ea45de470fcbfdc17541032e99db644ed66f919d",
        "e927581a5f1164f07562883dd1e6c22019e46222d4ae50cbd589cbb1d3b5c7c6",
    ),
    "482863": (
        "191800",
        "618f2be17d4dfd4eb7f65f17ccc82d4a19d5666f7f0b285e374fbcf8eeb0663a",
        "17b8bacc9204e682c703519f4a62a3056266c97c0dab9aa236518d2c409eefe0",
    ),
}


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
    for video_id, (fold, sha256) in MORE_CAPTURES.items():
        archive = download(
            f"{BASE}/threedod/{fold}/{video_id}.zip", folder / f"{video_id}.zip", sha256=sha256
        )
        if not (folder / video_id).is_dir():
            with zipfile.ZipFile(archive) as bundle:
                bundle.extractall(folder)
    if arguments.laser:
        for visit, (scan, pose_sha, cloud_sha) in MORE_LASERS.items():
            for suffix, sha256 in (("_pose.txt", pose_sha), (".ply", cloud_sha)):
                download(
                    f"{BASE}/raw/laser_scanner_point_clouds/{visit}/{scan}{suffix}",
                    folder / "laser" / visit / f"{scan}{suffix}",
                    sha256=sha256,
                )
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
