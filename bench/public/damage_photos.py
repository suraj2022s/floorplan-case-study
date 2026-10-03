"""The damage detector on real photographs of damage (configs/samples.json, "damage-photos").

    python scripts/fetch_samples.py damage-photos
    python bench/public/damage_photos.py

For each photo: the classes the detector reports at the configured thresholds, before and
after keeping one class per patch, against the class the photo shows. A check of the
detector, not a benchmark: seven web photos, framed as close-ups.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

from floorplan.models.detect import Detector
from floorplan.semantics.damage import load_semantics_config, one_class_per_patch

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    entry = json.loads((ROOT / "configs" / "samples.json").read_text())["damage-photos"]
    folder = ROOT / ".cache" / "samples" / entry["dir"]
    classes = load_semantics_config()["damage"]
    owner = {phrase: name for name, spec in classes.items() for phrase in spec["phrases"]}
    detector = Detector()
    hits_before = hits_after = wrong_before = wrong_after = 0
    print("| Photo | Shows | Reported | Reported, one class per patch |")
    print("|---|---|---|---|")
    for name, item in entry["files"].items():
        shows = set(item["shows"].split("|"))
        image = np.asarray(ImageOps.exif_transpose(Image.open(folder / name)).convert("RGB"))
        found = [
            d
            for d in detector.detect(image, list(owner), 0.05)
            if d.score >= classes[owner[d.label]]["threshold"]
        ]
        before = {owner[d.label] for d in found}
        after = {owner[d.label] for d in one_class_per_patch(found, owner)}
        hits_before += bool(before & shows)
        hits_after += bool(after & shows)
        wrong_before += len(before - shows)
        wrong_after += len(after - shows)
        print(
            f"| {name} | {', '.join(sorted(shows))} | {', '.join(sorted(before)) or '-'} "
            f"| {', '.join(sorted(after)) or '-'} |"
        )
    count = len(entry["files"])
    print(
        f"\nright class reported: {hits_before}/{count} before, {hits_after}/{count} after; "
        f"wrong classes reported: {wrong_before} before, {wrong_after} after"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
