"""Download the model weights listed in configs/weights.json into weights/.

Every file is pinned to an exact revision and checked against its SHA-256. A file that is
already present and matches is not downloaded again.

    python scripts/fetch_weights.py                # every model
    python scripts/fetch_weights.py moge-2-vitb-normal
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch import download  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    manifest = json.loads((ROOT / "configs" / "weights.json").read_text())
    wanted = sys.argv[1:] or list(manifest)
    unknown = [name for name in wanted if name not in manifest]
    if unknown:
        print(f"unknown model(s) {unknown}; available: {sorted(manifest)}")
        return 2
    for name in wanted:
        entry = manifest[name]
        if "files" in entry:  # a model made of several files, kept together in a folder
            folder = ROOT / "weights" / entry["dir"]
            for file_name, item in entry["files"].items():
                download(item["url"], folder / file_name, sha256=item["sha256"])
        else:
            download(entry["url"], ROOT / "weights" / entry["file"], sha256=entry["sha256"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
