"""Fit the depth-scale factor of a LiDAR device from benchmark ceilings, and check it out of sample.

    python bench/fit_depth_scale.py reports/bench/arkitscenes/gates.json

A depth sensor that reads every distance a fixed fraction short makes every ceiling that same
fraction low: a ceiling height is the sum of two depth readings (up to the ceiling, down to
the floor) taken from the same camera. So the factor is the mean of truth / measured over the
ceilings of the benchmark's LiDAR captures. Fitting and checking on the same rooms only proves
the arithmetic, so each room (each site) is left out in turn: the factor is fitted on the
other rooms and applied to the room left out. That held-out count is what a report quotes.

The result is the factor still missing from the measurements as they stand: multiply it into
the device's factor in its reader (`io/arkitscenes.py` for the iPad Pro of ARKitScenes). Run
again after that, it should print a factor near 1.000.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

GATE = 0.015  # metres, the brief's ceiling gate


def main() -> int:
    data = json.loads(Path(sys.argv[1]).read_text())
    rows = [
        (capture["site"], row["capture"], row["truth"], row["value"])
        for capture in data["captures"]
        if capture["tier"] == "lidar"
        for row in capture["rows"]
        if row["kind"] == "ceiling_height" and row["value"] is not None
    ]
    sites = sorted({site for site, *_ in rows})
    ratio = {capture: truth / value for _, capture, truth, value in rows}
    factor = sum(ratio.values()) / len(ratio)
    print(f"{len(rows)} ceilings in {len(sites)} rooms; factor fitted on all: {factor:.5f}\n")
    print("| Room | Capture | Truth (m) | Now (cm) | Factor of the other rooms | Then (cm) |")
    print("|---|---|---|---|---|---|")
    held_out_pass = 0
    for site in sites:
        others = [ratio[c] for s, c, _, _ in rows if s != site]
        held = sum(others) / len(others)
        for s, capture, truth, value in rows:
            if s != site:
                continue
            after = value * held - truth
            held_out_pass += abs(after) <= GATE
            print(
                f"| {site} | {capture} | {truth:.4f} | {(value - truth) * 100:+.1f} "
                f"| {held:.5f} | {after * 100:+.1f} |"
            )
    in_sample = sum(abs(value * factor - truth) <= GATE for _, _, truth, value in rows)
    print(
        f"\nwithin 1.5 cm: now {sum(abs(v - t) <= GATE for _, _, t, v in rows)}/{len(rows)}; "
        f"each room with the factor of the others {held_out_pass}/{len(rows)}; "
        f"all with the factor of all {in_sample}/{len(rows)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
