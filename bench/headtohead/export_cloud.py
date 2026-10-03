"""Write a capture's raw point cloud as a LAS file, for a floor-plan tool that takes uploads.

    python bench/headtohead/export_cloud.py <capture> <out.las> [--voxel 0.01]

The brief's head-to-head runs a consumer scanning app on the same rooms. Those apps scan live
on a phone; with no phone available, the closest fair stand-in is a tool that accepts a point
cloud and draws the floor plan automatically, given the same raw data our pipeline starts
from. So this writes the capture's depth on the device's own recorded poses: no drift
correction, no depth correction, nothing of our pipeline beyond turning depth pixels into
points (`geometry/cloud.py`) and thinning them to one per voxel.

LAS 1.2, point format 0 (x, y, z), written directly: the format is a 227-byte header and 20
bytes per point, so no extra dependency is needed.
"""

from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from floorplan.geometry.cloud import CloudConfig, accumulate  # noqa: E402
from floorplan.io.arkitscenes import is_arkitscenes, read_arkitscenes  # noqa: E402
from floorplan.io.intake import find_capture  # noqa: E402
from floorplan.io.stray import read_stray  # noqa: E402

SCALE = 0.0001  # metres per stored integer unit: 0.1 mm


def write_las(path: Path, xyz: np.ndarray) -> None:
    """LAS 1.2, point data format 0, coordinates in metres."""
    low, high = xyz.min(axis=0), xyz.max(axis=0)
    offset = np.floor(low)
    stored = np.round((xyz - offset) / SCALE).astype("<i4")
    count = len(xyz)
    header = struct.pack(
        "<4sHHIHH8sBB32s32sHHHIIBHI5IddddddddddddH",
        b"LASF",
        0,  # file source id
        0,  # global encoding
        0,
        0,
        0,
        b"\0" * 8,  # project id (GUID)
        1,
        2,  # version 1.2
        b"floorplan".ljust(32, b"\0"),
        b"bench/headtohead/export_cloud.py".ljust(32, b"\0"),
        1,
        2026,  # creation day of year, year
        227,  # header size
        227,  # offset to point data
        0,  # number of variable-length records
        0,  # point data format 0
        20,  # point record length
        count,
        count,
        0,
        0,
        0,
        0,  # points by return
        SCALE,
        SCALE,
        SCALE,
        *offset,
        high[0],
        low[0],
        high[1],
        low[1],
        high[2],
        low[2],
        0,  # padding to 227 bytes
    )[:227]
    record = np.zeros(
        count,
        dtype=[
            ("x", "<i4"),
            ("y", "<i4"),
            ("z", "<i4"),
            ("intensity", "<u2"),
            ("flags", "u1"),
            ("classification", "u1"),
            ("angle", "i1"),
            ("user", "u1"),
            ("source", "<u2"),
        ],
    )
    record["x"], record["y"], record["z"] = stored[:, 0], stored[:, 1], stored[:, 2]
    record["flags"] = 0b00001001  # return 1 of 1
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(header)
        handle.write(record.tobytes())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("capture", type=Path)
    parser.add_argument("out", type=Path)
    parser.add_argument("--voxel", type=float, default=0.01)
    arguments = parser.parse_args()
    source = find_capture(arguments.capture).path
    capture = (read_arkitscenes if is_arkitscenes(source) else read_stray)(source)
    cloud = accumulate(capture, CloudConfig(voxel=arguments.voxel))
    write_las(arguments.out, cloud.xyz)
    print(
        f"wrote {arguments.out}: {len(cloud.xyz):,} points, {arguments.voxel * 100:.0f} cm voxels"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
