"""Turn a `Plan` into the JSON document a run writes.

`plan.json` holds only what was measured. It contains no clock times and no machine paths,
so two runs on the same capture produce byte-identical files; that is what makes "same room
in, same plan out" checkable with a file comparison. Timings and environment details go in
`run_log.json`, which is expected to differ from run to run.
"""

from __future__ import annotations

import hashlib
import json
import platform
from pathlib import Path

import numpy as np

from floorplan import __version__
from floorplan.pipeline import Plan

SCHEMA_VERSION = "draft-1"  # replaced by the published Round 1 schema once it is in spec/


def _point(xy: np.ndarray) -> list[float]:
    return [round(float(xy[0]), 4), round(float(xy[1]), 4)]


def plan_to_dict(plan: Plan, capture_name: str) -> dict:
    rooms = []
    for room in plan.rooms:
        rooms.append(
            {
                "id": room.id,
                "polygon": [_point(p) for p in room.polygon],
                "floor_area": room.floor_area.to_dict(),
                "ceiling_height": room.ceiling_height.to_dict(),
                "ceiling_height_range": [round(v, 4) for v in room.ceiling_height_range],
                "walls": [
                    {
                        "id": wall.id,
                        "start": _point(wall.start),
                        "end": _point(wall.end),
                        "length": wall.length.to_dict(),
                        "observed_share": round(wall.observed_share, 3),
                    }
                    for wall in room.walls
                ],
                "openings": [o.id for o in plan.openings if room.id in (o.room, o.other_room)],
                "entered": room.entered,
                "notes": room.notes,
            }
        )
    openings = []
    for opening in plan.openings:
        openings.append(
            {
                "id": opening.id,
                "kind": opening.kind,
                "room": opening.room,
                "wall": opening.wall,
                "connects_to": opening.other_room,
                "width": opening.width.to_dict(),
                "height": opening.height.to_dict(),
                "sill_height": round(opening.sill, 4),
                "position_along_wall": round(opening.position_along_wall, 4),
                "wall_thickness": (
                    None if opening.wall_thickness is None else round(opening.wall_thickness, 4)
                ),
                "centre": _point(opening.centre),
                "width_method": opening.method,
                "evidence": opening.evidence,
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "capture": {"name": capture_name, "tier": plan.tier},
        "units": {"length": "m", "area": "m2"},
        "frame": "metric, gravity-aligned, z up; x and y are arbitrary but shared by all rooms",
        "rooms": rooms,
        "openings": openings,
        "adjacency": [{"rooms": [a, b], "via": opening} for a, b, opening in plan.adjacency],
        "footprint_area": plan.footprint_area.to_dict(),
        "damage_regions": [region.to_dict() for region in plan.damage],
        "concealed_damage_flags": [flag.to_dict() for flag in plan.flags],
        "scope_items": [item.to_dict() for item in plan.scope],
        "intervals": {
            "coverage": 0.90,
            "calibrated": plan.calibration.calibrated,
            "calibration_source": plan.calibration.source,
        },
        "warnings": plan.warnings,
    }


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=False) + "\n", newline="\n")


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def run_log(plan: Plan, capture_dir: Path, plan_file: Path, arguments: dict) -> dict:
    """Everything about a run that is not a measurement: timings, inputs, environment."""
    inputs = {}
    for name in ("odometry.csv", "camera_matrix.csv"):
        file = capture_dir / name
        if file.is_file():
            inputs[name] = file_digest(file)
    return {
        "floorplan_version": __version__,
        "arguments": arguments,
        "tier": plan.tier,
        "stats": plan.stats,
        "timings_s": plan.timings,
        "total_s": round(sum(plan.timings.values()), 3),
        "inputs_sha256": inputs,
        "plan_sha256": file_digest(plan_file),
        "python": platform.python_version(),
        "platform": platform.platform(),
    }
