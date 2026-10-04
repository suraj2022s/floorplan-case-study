"""Head-to-head stand-in: our LiDAR tier against Pointorama's automatic room, on a public bedroom.

    python bench/headtohead/pointorama.py

Consumer scanning apps scan live on a phone, and no phone was available. The stand-in: the raw
point cloud of ARKitScenes scan 47333462 (bench/headtohead/export_cloud.py: the iPad's depth on
its own poses) was given to Pointorama, a web floor-plan tool, which found the floor and the
room with its automatic tools; its DXF export is in bench/headtohead/pointorama/. Both sides
are scored against Apple's laser truth (bench/ground_truth/arkitscenes-467138.yaml).

Dimensions compared, measured the same way on both outlines: the room's width and length (the
smallest rectangle around the outline), its floor area and its ceiling height. Pointorama
reported no doors or windows, so openings are not compared (only shared dimensions count).
"Ours, raw" switches off the iPad's depth factor (fix-loop round 3): the same input the tool had.
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

CAPTURE = ROOT / ".cache" / "arkitscenes" / "47333462"
DXF = ROOT / "bench" / "headtohead" / "pointorama" / "bedroom_467138.dxf"
TRUTH = ROOT / "bench" / "ground_truth" / "arkitscenes-467138.yaml"
TOOL_CEILING = 2.59  # Pointorama's "Room height", as its room panel shows it
TIE = 0.005  # metres: errors this close are a tie (the resolution an app reports to)


def dxf_outline(path: Path) -> np.ndarray:
    """Corners of the first closed POLYLINE in an ASCII DXF (group 10/20 pairs of its VERTEXes)."""
    lines = path.read_text(errors="replace").splitlines()
    pairs = [(lines[i].strip(), lines[i + 1].strip()) for i in range(0, len(lines) - 1, 2)]
    corners, inside, x = [], False, None
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


def ours(depth_scale: float) -> dict:
    arkitscenes.DEPTH_SCALE = depth_scale
    plan = run(arkitscenes.read_arkitscenes(CAPTURE), config_for("lidar"))
    room = max(plan.rooms, key=lambda r: r.floor_area.value)
    width, length = size(room.polygon)
    return {
        "width": width,
        "length": length,
        "floor area": room.floor_area.value,
        "ceiling height": room.ceiling_height.value,
    }


def main() -> int:
    truth_room = yaml.safe_load(TRUTH.read_text())["rooms"][0]
    walls = [w["length"] for w in truth_room["walls"]]  # W1..W4, clockwise
    truth = {
        "width": (walls[0] + walls[2]) / 2,
        "length": (walls[1] + walls[3]) / 2,
        "floor area": truth_room["floor_area"],
        "ceiling height": truth_room["ceiling_height"]["middle"],
    }
    outline = dxf_outline(DXF)
    width, length = size(outline)
    tool = {
        "width": width,
        "length": length,
        "floor area": Polygon(outline).area,
        "ceiling height": TOOL_CEILING,
    }
    shipped, raw = ours(1.00945), ours(1.0)
    print(f"Pointorama outline: {len(outline)} corners, area {tool['floor area']:.2f} m2\n")
    print("| Dimension | Laser | Pointorama | Ours | Ours, raw |")
    print("|---|---|---|---|---|")
    beat = {"Ours": 0, "Ours, raw": 0}
    for key in truth:
        unit = "m2" if key == "floor area" else "m"
        error = {
            name: side[key] - truth[key]
            for name, side in (("tool", tool), ("Ours", shipped), ("Ours, raw", raw))
        }
        cells = []
        for name in ("Ours", "Ours, raw"):
            won = abs(error[name]) <= abs(error["tool"]) + TIE
            beat[name] += won
            cells.append(f"{error[name]:+.3f}{'' if won else ' x'}")
        row = [f"{key} ({unit})", f"{truth[key]:.3f}", f"{error['tool']:+.3f}", *cells]
        print("| " + " | ".join(row) + " |")
    count = len(truth)
    print(
        f"\nbeaten or tied (x = the tool's error is smaller): ours {beat['Ours']}/{count}, "
        f"ours raw {beat['Ours, raw']}/{count}; the brief's bar is 70%"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
