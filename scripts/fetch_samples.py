"""Download the real iPhone sample files listed in configs/samples.json into .cache/samples/.

These are files written by real iPhones and published by others. They let the readers be
tested against what an iPhone writes when no iPhone is to hand. Each file is pinned by its
SHA-256. They are not benchmark data: none of them comes with measurements of a room.

    python scripts/fetch_samples.py                # every set
    python scripts/fetch_samples.py iphone15pro
"""

from __future__ import annotations

import json
import shutil
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch import download  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    manifest = json.loads((ROOT / "configs" / "samples.json").read_text())
    wanted = sys.argv[1:] or list(manifest)
    unknown = [name for name in wanted if name not in manifest]
    if unknown:
        print(f"unknown sample set(s) {unknown}; available: {sorted(manifest)}")
        return 2
    for name in wanted:
        entry = manifest[name]
        folder = ROOT / ".cache" / "samples" / entry["dir"]
        for file_name, item in entry["files"].items():
            download(item["url"], folder / file_name, sha256=item["sha256"], connections=4)
        unpack = entry.get("unpack")
        if unpack and not (folder / unpack["to"]).is_dir():
            with zipfile.ZipFile(folder / unpack["archive"]) as bundle:
                bundle.extractall(folder / unpack["to"])
            for source, target in unpack.get("also", {}).items():
                shutil.copyfile(folder / source, folder / unpack["to"] / target)
            print(f"{name}: unpacked to {folder / unpack['to']}")
        print(f"{name}: {entry['licence']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
