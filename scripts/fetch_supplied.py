"""Download the sample data supplied with the assessment into captures/supplied/.

    python scripts/fetch_supplied.py

Three Stray Scanner recordings made on a LiDAR iPhone, shared by the assessors in the
assessment's "Sample Data" Google Drive folder ("Assignment - YC Startup"):

    single_room.zip               -> c00a170fe1   1,715 frames,  37 s, 14 m walk
    single_scan_floor_only.zip    -> 1a8384c3f6   5,251 frames, 115 s, 54 m walk
    single_scan_with_ceiling.zip  -> c7d28f72c6   9,745 frames, 215 s, 100 m walk

Each file is checked against its SHA-256 and unpacked next to the zip. They come without
tape measurements, so they test whether the pipeline holds up on real iPhone recordings,
not how accurate it is. `floorplan run` also takes the zips as they are.
"""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch import download  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
FOLDER = "https://drive.google.com/drive/folders/1QIzPgDXL27EzL3RB_H-Cf75NABtD68SE"
FILES = {  # name -> (Drive file id, SHA-256)
    "single_room.zip": (
        "1-0ZxGbWHWgbh5FwUGR5U4FJrCHp_mKCk",
        "0805f742d378e4bda480fef6e5839304364807bb7b77bb459983003727e9699c",
    ),
    "single_scan_floor_only.zip": (
        "1Dio9breIRM3N5Yl1UTji7G8UfksRaOJo",
        "f822287268297d2adab49deff8e0ee5f50f05304b450d8d47d0b5eb476aa74d4",
    ),
    "single_scan_with_ceiling.zip": (
        "1WyFSoB-hYktaXb50v00i6ZCn5hl3CCkF",
        "4bfbeb11ee21b114c46ad43cf0c9602d8ada827397f4e8b3c70dd827d0191379",
    ),
}


def main() -> int:
    target = ROOT / "captures" / "supplied"
    for name, (file_id, sha256) in FILES.items():
        url = f"https://drive.usercontent.google.com/download?id={file_id}&export=download&confirm=t"
        archive = download(url, target / name, sha256=sha256, connections=8)
        with zipfile.ZipFile(archive) as bundle:
            inner = {Path(m).parts[0] for m in bundle.namelist() if not m.startswith("__MACOSX")}
            if not all((target / part).exists() for part in inner):
                bundle.extractall(target)
    print(f"ready in {target} (source: {FOLDER})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
