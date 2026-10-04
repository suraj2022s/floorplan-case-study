"""Head-to-head stand-in: our LiDAR tier against Pointorama's automatic room, on public bedrooms.

    python bench/headtohead/pointorama.py

Consumer scanning apps scan live on a phone, and no phone was available. The stand-in: the raw
point cloud of an ARKitScenes scan (bench/headtohead/export_cloud.py: the iPad's depth on its
own poses) was given to Pointorama, a web floor-plan tool, which found the floor and the room
with its automatic tools; its DXF exports are in bench/headtohead/pointorama/. Both sides are
scored against Apple's laser truth (bench/ground_truth/).

Dimensions compared, measured the same way on both outlines: the room's width and length (the
smallest rectangle around the outline), its floor area and its ceiling height, where the laser
truth has them; the second bedroom's truth is its ceiling only, so its other dimensions are
shown but not scored. Pointorama reported no doors or windows, so openings are not compared
(only shared dimensions count). "Ours, raw" switches off the iPad's depth factor (fix-loop
round 3): the same input the tool had.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import yaml
from shapely.geometry import Polygon

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

import floorplan.io.arkitscenes as arkitscenes  # noqa: E402
from floorplan.pipeline import config_for, run  # noqa: E402

HERE = ROOT / "bench" / "headtohead" / "pointorama"
ROOMS = [  # capture given to the tool, its DXF, its "Room height" as its room panel shows it
    {"name": "bedroom 467138", "capture": "47333462", "visit": "467138", "tool_ceiling": 2.59},
    {"name": "bedroom 423441", "capture": "42897672", "visit": "423441", "tool_ceiling": None},
]
TIE = 0.005  # metres: errors this close are a tie (the resolution an app reports to)
KEYS = ("width", "length", "floor area", "ceiling height")


def dxf_outline(path: Path) -> np.ndarray:
    """Corners of the first closed POLYLINE in an ASCII DXF (group 10/20 pairs of its VERTEXes)."""
    lines = path.read_text(errors="replace").splitlines()
    pairs = [(lines[i].strip(), lines[i + 1].strip()) for i in range(0, len(lines) - 1, 2)]
    corners, inside, in_vertex, x = [], False, False, None
    for code, value in pairs:
        if code == "0":
            if value == "SEQEND" and inside:
                break
            inside = inside or value == "POLYLINE"
            in_vertex = value == "VERTEX"
            continue
        if inside and in_vertex and code == "10":
            x = float(value)
        elif inside and in_vertex and code == "20":
            corners.append((x, float(value)))
    return np.array(corners)


def size(outline: np.ndarray) -> tuple[float, float]:
    """Width and length of the smallest rectangle around an outline, shorter first."""
    box = np.array(Polygon(outline).minimum_rotated_rectangle.exterior.coords)[:4]
    sides = sorted(float(np.linalg.norm(box[i + 1] - box[i])) for i in range(2))
    return sides[0], sides[1]


def laser(visit: str) -> dict:
    room = yaml.safe_load(
        (ROOT / "bench" / "ground_truth" / f"arkitscenes-{visit}.yaml").read_text()
    )
    room = room["rooms"][0]
    truth = {"ceiling height": room["ceiling_height"]["middle"]}
    walls = [w["length"] for w in room["walls"]]  # W1..W4 clockwise, when read off
    if len(walls) == 4:
        truth |= {"width": (walls[0] + walls[2]) / 2, "length": (walls[1] + walls[3]) / 2}
    if room.get("floor_area"):
        truth["floor area"] = room["floor_area"]
    return truth


def ours(capture: str, depth_scale: float) -> dict:
    arkitscenes.DEPTH_SCALE = depth_scale
    plan = run(
        arkitscenes.read_arkitscenes(ROOT / ".cache" / "arkitscenes" / capture), config_for("lidar")
    )
    room = max(plan.rooms, key=lambda r: r.floor_area.value)
    width, length = size(room.polygon)
    return {
        "width": width,
        "length": length,
        "floor area": room.floor_area.value,
        "ceiling height": room.ceiling_height.value,
    }


def main() -> int:
    beat, scored = {"Ours": 0, "Ours, raw": 0}, 0
    print("| Room | Dimension | Laser | Pointorama | Ours | Ours, raw |")
    print("|---|---|---|---|---|---|")
    for spec in ROOMS:
        dxf = HERE / f"bedroom_{spec['visit']}.dxf"
        if not dxf.is_file() or spec["tool_ceiling"] is None:
            continue
        outline = dxf_outline(dxf)
        width, length = size(outline)
        tool = {
            "width": width,
            "length": length,
            "floor area": Polygon(outline).area,
            "ceiling height": spec["tool_ceiling"],
        }
        truth = laser(spec["visit"])
        sides = {"Ours": ours(spec["capture"], 1.00945), "Ours, raw": ours(spec["capture"], 1.0)}
        for key in KEYS:
            unit = "m2" if key == "floor area" else "m"
            if key not in truth:  # no laser value: shown side by side, not scored
                values = [f"{tool[key]:.3f}"] + [f"{sides[n][key]:.3f}" for n in sides]
                row = [spec["name"], f"{key} ({unit})", "not read off", *values]
                print("| " + " | ".join(row) + " |")
                continue
            scored += 1
            tool_error = tool[key] - truth[key]
            cells = []
            for name, side in sides.items():
                error = side[key] - truth[key]
                won = abs(error) <= abs(tool_error) + TIE
                beat[name] += won
                cells.append(f"{error:+.3f}{'' if won else ' x'}")
            row = [spec["name"], f"{key} ({unit})", f"{truth[key]:.3f}", f"{tool_error:+.3f}"]
            print("| " + " | ".join(row + cells) + " |")
    print(
        f"\nerrors are measured minus laser; x = the tool's error is smaller. Beaten or tied: "
        f"ours {beat['Ours']}/{scored}, ours raw {beat['Ours, raw']}/{scored}; the bar is 70%"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
