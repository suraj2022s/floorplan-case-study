"""Ground truth for one room from a stationary laser scan (ARKitScenes' Faro point clouds).

    python bench/public/laser_truth.py <scan.ply> --site <name> --out <truth.yaml>
        [--preview <top-view.png>]

Used for the public-data benchmark: Apple published, for some rooms of its ARKitScenes
dataset, both iPad LiDAR captures and Faro Focus S70 laser scans of the same room. A
stationary scanner standing in a room sees every wall, the floor and the ceiling of that room
at millimetre accuracy, so the room's dimensions can be read off it without any registration
to the iPad captures. This is not a tape measurement by us: the instrument is Apple's laser,
and the reading-off is this script, which is deliberately independent of the pipeline's code.

What is read off, and how:

* ceiling: the dense top layer, fitted as a plane;
* floor: the lowest dense layer below the ceiling (a rug or a mat is a layer above it, and
  the room's height is measured to the floor, not to the rug);
* walls: straight lines fitted to the band just under the ceiling, where furniture, curtains
  and door heads do not reach, keeping in each direction the line nearest the scanner;
* openings: rays from the scanner that cross a wall line and hit something behind it pass
  through an opening; where they cross the wall line gives the opening's extent.

Coordinates in the scan are metres. Walls are listed clockwise (seen from above) starting
from the wall with the entrance, as the tape protocol does (bench/GT_PROTOCOL.md).
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import yaml

STRIDE = 10  # keep every 10th point: about 4 million of a 43 million point scan


def read_scan(path: Path, stride: int = STRIDE) -> np.ndarray:
    """xyz of a binary PLY written by the dataset (doubles, colour, quality, radius)."""
    with open(path, "rb") as handle:
        header = b""
        while not header.endswith(b"end_header\n"):
            line = handle.readline()
            if not line:
                raise ValueError(f"{path}: no end_header")
            header += line
    lines = header.decode("ascii", "replace").splitlines()
    count = int(next(line for line in lines if line.startswith("element vertex")).split()[-1])
    types = {"double": "<f8", "float": "<f4", "uchar": "u1", "int": "<i4", "uint": "<u4"}
    fields = []
    in_vertex = False
    for line in lines:
        if line.startswith("element"):
            in_vertex = line.startswith("element vertex")
        elif in_vertex and line.startswith("property"):
            _, kind, name = line.split()
            fields.append((name, types[kind]))
    data = np.memmap(path, dtype=np.dtype(fields), mode="r", offset=len(header), shape=(count,))
    sample = np.asarray(data[::stride])
    xyz = np.stack([sample["x"], sample["y"], sample["z"]], axis=1).astype(np.float64)
    return xyz[np.isfinite(xyz).all(axis=1)]


@dataclass
class Line:
    normal: np.ndarray  # unit, pointing towards the scanner (into the room)
    distance: float  # from the scanner to the line
    points: int
    rms: float
    extent: tuple[float, float]  # along the line, from the foot of the scanner


def fit_plane_z(points: np.ndarray) -> np.ndarray:
    """z = a x + b y + c, refit three times without outliers."""
    for _ in range(3):
        A = np.c_[points[:, :2], np.ones(len(points))]
        coef, *_ = np.linalg.lstsq(A, points[:, 2], rcond=None)
        residual = points[:, 2] - A @ coef
        points = points[np.abs(residual) < 3 * max(residual.std(), 1e-4)]
    return coef


def levels(xyz: np.ndarray) -> tuple[np.ndarray, np.ndarray, list]:
    """Ceiling plane, floor plane (lowest dense layer) and the floor layers found."""
    near = np.hypot(xyz[:, 0], xyz[:, 1]) < 1.5
    z = xyz[:, 2]
    hist, edges = np.histogram(z[near], bins=np.arange(z.min(), z.max() + 0.01, 0.01))
    top = edges[np.flatnonzero(hist > 0.2 * hist.max())[-1]]
    ceiling = fit_plane_z(xyz[near & (np.abs(z - top) < 0.03)])
    below = (ceiling[0] * xyz[:, 0] + ceiling[1] * xyz[:, 1] + ceiling[2]) - z
    tall = below[near & (below > 1.8)]
    fine, fine_edges = np.histogram(tall, bins=np.arange(1.8, tall.max() + 0.004, 0.002))
    dense = np.flatnonzero(fine > 0.15 * fine.max())
    layers = []
    for index in dense:  # group neighbouring dense bins into layers
        if layers and index - layers[-1][-1] <= 2:
            layers[-1].append(index)
        else:
            layers.append([index])
    found = [
        (float(fine_edges[group[0]]), float(fine_edges[group[-1] + 1]), int(fine[group].sum()))
        for group in layers
    ]
    lowest = found[-1]  # largest distance below the ceiling
    floor_points = xyz[near & (below >= lowest[0] - 0.002) & (below <= lowest[1] + 0.002)]
    return ceiling, fit_plane_z(floor_points), found


def lines_in(points: np.ndarray, tolerance: float = 0.006, minimum: int = 4000) -> list[Line]:
    """Straight lines in a 2D point set, strongest first (sequential RANSAC + refit)."""
    rng = np.random.default_rng(0)
    remaining, found = points, []
    while len(remaining) > minimum:
        best_count, best = 0, None
        for _ in range(500):
            p, q = remaining[rng.choice(len(remaining), 2, replace=False)]
            direction = q - p
            if np.linalg.norm(direction) < 0.3:
                continue
            normal = np.array([-direction[1], direction[0]]) / np.linalg.norm(direction)
            count = int((np.abs((remaining - p) @ normal) < tolerance).sum())
            if count > best_count:
                best_count, best = count, (normal, p)
        if best is None or best_count < minimum:
            break
        normal, p = best
        inliers = remaining[np.abs((remaining - p) @ normal) < tolerance]
        centre = inliers.mean(axis=0)
        direction = np.linalg.svd(inliers - centre, full_matrices=False)[2][0]
        normal = np.array([-direction[1], direction[0]])
        if normal @ centre > 0:
            normal = -normal
        on_line = np.abs((remaining - centre) @ normal) < 2 * tolerance
        along = (remaining[on_line] - centre) @ direction
        foot = -(normal @ centre) * normal
        offset = float((centre - foot) @ direction)
        found.append(
            Line(
                normal=normal,
                distance=float(-(normal @ centre)),
                points=int(on_line.sum()),
                rms=float(np.sqrt(np.mean(((remaining[on_line] - centre) @ normal) ** 2))),
                extent=(float(along.min() + offset), float(along.max() + offset)),
            )
        )
        remaining = remaining[~on_line]
    return found


def room_walls(lines: list[Line], max_rms: float = 0.002) -> list[Line]:
    """The four walls of the room the scanner stands in: per direction, the nearest line."""
    good = [line for line in lines if line.rms <= max_rms]
    strongest = max(good, key=lambda line: line.points)
    walls = []
    for turn in range(4):
        angle = np.arctan2(strongest.normal[1], strongest.normal[0]) + turn * np.pi / 2
        wanted = np.array([np.cos(angle), np.sin(angle)])
        candidates = [line for line in good if line.normal @ wanted > np.cos(np.radians(3))]
        if not candidates:
            raise ValueError(f"no wall found facing {np.degrees(angle):.0f} degrees")
        walls.append(min(candidates, key=lambda line: line.distance))
    return walls


def corner(a: Line, b: Line) -> np.ndarray:
    """Intersection of two wall lines (each: normal . x = -distance)."""
    return np.linalg.solve(np.stack([a.normal, b.normal]), -np.array([a.distance, b.distance]))


def opening_extent(xyz, height, wall: Line, low: float, high: float):
    """Where rays through an opening in `wall` cross it, as positions along the wall.

    A point more than 10 cm behind the wall, at a height inside [low, high], was reached by
    a ray that passed through the wall's plane, so through an opening. The crossing points
    of those rays mark out the opening.
    """
    behind = (xyz[:, :2] @ wall.normal + wall.distance) < -0.10
    chosen = xyz[behind & (height > low) & (height < high)]
    if len(chosen) < 200:
        return None
    reach = wall.distance / -(chosen[:, :2] @ wall.normal)  # fraction of the ray at the wall
    crossing = chosen[:, :2] * reach[:, None]
    crossing_height = chosen[:, 2] * reach  # not used beyond the height filter
    del crossing_height
    direction = np.array([wall.normal[1], -wall.normal[0]])
    along = crossing @ direction
    lo, hi = np.percentile(along, [0.5, 99.5])
    return float(lo), float(hi)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("scan", type=Path)
    parser.add_argument("--site", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--preview", type=Path)
    parser.add_argument("--source", default="")
    arguments = parser.parse_args()

    xyz = read_scan(arguments.scan)
    ceiling, floor, layers = levels(xyz)
    room_height = float(ceiling[2] - floor[2])  # at the scanner, which stands in the room
    height = xyz[:, 2] - (floor[0] * xyz[:, 0] + floor[1] * xyz[:, 1] + floor[2])
    band = xyz[(height > room_height - 0.40) & (height < room_height - 0.08)][:, :2]
    lines = lines_in(band)
    walls = room_walls(lines)

    # corners, then walls clockwise seen from above (z up): order by angle, descending
    centre = np.mean([corner(walls[i], walls[(i + 1) % 4]) for i in range(4)], axis=0)
    by_angle = sorted(
        walls,
        key=lambda wall: -np.arctan2(*(-wall.distance * wall.normal - centre)[::-1]),
    )
    corners = [corner(by_angle[i - 1], by_angle[i]) for i in range(4)]  # start of each wall

    # openings: door height band for passages, window band for windows
    openings = []
    for index, wall in enumerate(by_angle):
        start, end = corners[index], corners[(index + 1) % 4]
        direction = (end - start) / np.linalg.norm(end - start)
        foot = -wall.distance * wall.normal
        for kind, low, high in (("passage", 0.10, 1.80), ("window", 1.00, 1.60)):
            extent = opening_extent(xyz, height, wall, low, high)
            if extent is None:
                continue
            # positions along the wall from its start corner
            sign = 1.0 if direction @ np.array([wall.normal[1], -wall.normal[0]]) > 0 else -1.0
            positions = sorted(
                float((foot + sign * e * direction * sign - start) @ direction) for e in extent
            )
            del positions
            a = float(
                (foot + extent[0] * np.array([wall.normal[1], -wall.normal[0]]) - start) @ direction
            )
            b = float(
                (foot + extent[1] * np.array([wall.normal[1], -wall.normal[0]]) - start) @ direction
            )
            lo_, hi_ = sorted((a, b))
            openings.append(
                {"wall_index": index, "kind": kind, "from_left_corner": lo_, "width": hi_ - lo_}
            )

    print(
        f"ceiling height {room_height:.4f} m; floor layers below the ceiling: "
        + ", ".join(f"{a:.3f}-{b:.3f} m ({n} pts)" for a, b, n in layers)
    )
    for line in lines:
        print(
            f"  line: facing {np.degrees(np.arctan2(line.normal[1], line.normal[0])):7.2f} deg, "
            f"{line.distance:.4f} m from the scanner, {line.points} points, rms "
            f"{line.rms * 1000:.1f} mm, extent {line.extent[0]:.2f}..{line.extent[1]:.2f}"
        )
    for index, wall in enumerate(by_angle):
        start, end = corners[index], corners[(index + 1) % 4]
        print(
            f"  wall {index + 1}: length {np.linalg.norm(end - start):.4f} m, facing "
            f"{np.degrees(np.arctan2(wall.normal[1], wall.normal[0])):.2f} deg"
        )
    for item in openings:
        print(
            f"  opening candidate on wall {item['wall_index'] + 1}: {item['kind']} from "
            f"{item['from_left_corner']:.3f} m, width {item['width']:.3f} m"
        )

    if arguments.preview:
        _preview(xyz, height, room_height, by_angle, corners, arguments.preview)

    truth = {
        "site": arguments.site,
        "source": arguments.source,
        "instrument": {
            "type": "laser",
            "model": "Faro Focus S70 (scan published by Apple)",
            "stated_accuracy_mm": 2,
        },
        "read_off_by": "bench/public/laser_truth.py",
        "rooms": [
            {
                "id": "room",
                "walls": [
                    {
                        "id": f"W{i + 1}",
                        "length": round(
                            float(np.linalg.norm(corners[(i + 1) % 4] - corners[i])), 4
                        ),
                    }
                    for i in range(4)
                ],
                "ceiling_height": {"middle": round(room_height, 4)},
                "openings": [],
            }
        ],
        "adjacency": [],
    }
    arguments.out.parent.mkdir(parents=True, exist_ok=True)
    arguments.out.write_text(yaml.safe_dump(truth, sort_keys=False))
    print(f"wrote {arguments.out} (openings are listed above; add the ones that are real by hand)")
    return 0


def _preview(xyz, height, room_height, walls, corners, path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    band = xyz[(height > 0.9) & (height < room_height - 0.08)]
    keep = np.hypot(band[:, 0], band[:, 1]) < 6
    figure, axis = plt.subplots(figsize=(7, 7))
    axis.scatter(band[keep, 0][::5], band[keep, 1][::5], s=0.05, color="#52514e")
    polygon = np.array(corners + [corners[0]])
    axis.plot(polygon[:, 0], polygon[:, 1], color="#2a78d6", linewidth=1.2)
    for i, point in enumerate(corners):
        nxt = corners[(i + 1) % 4]
        middle = (point + nxt) / 2
        axis.text(
            middle[0],
            middle[1],
            f"W{i + 1}\n{np.linalg.norm(nxt - point):.3f}",
            color="#0b0b0b",
            fontsize=8,
            ha="center",
            va="center",
        )
    axis.plot([0], [0], marker="+", color="#eb6834")
    axis.set_aspect("equal")
    axis.set_title("Laser scan, 0.9 m to the ceiling, with the walls read off", fontsize=9)
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(figure)


if __name__ == "__main__":
    raise SystemExit(main())
