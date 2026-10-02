"""Find the floor, the ceiling and the wall faces in a point cloud.

The world frame is gravity-aligned, so floors and ceilings are (nearly) horizontal and walls
are vertical. That turns plane finding into two easy one-dimensional searches:

* floor and ceiling are peaks in the histogram of point heights;
* a wall face is a peak in the histogram of signed distances along the direction the wall
  faces, after grouping wall points by facing direction.

Every plane found this way is then refitted by least squares on its own points, so the
histogram only decides *which* points belong together and never sets a dimension. A plane fit
uses thousands of points; that averaging is where millimetre-level plane positions come
from even though single depth readings are noisier.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from floorplan.geometry.cloud import Cloud


@dataclass(frozen=True)
class PlaneConfig:
    level_bin: float = 0.02  # metres, height histogram bin
    level_band: float = 0.06  # points within this of a height peak are fitted
    level_min_share: float = 0.2  # a floor/ceiling peak must hold this share of the largest
    wall_max_nz: float = 0.3  # |vertical component| of a wall normal
    wall_min_height: float = 0.10  # ignore wall points this close to the floor (skirting)
    angle_tolerance_deg: float = 20.0  # normal-to-direction angle for a point to vote
    direction_min_share: float = 0.03  # facing directions below this share are ignored
    offset_bin: float = 0.01
    inlier_band: float = 0.03  # metres either side of a wall face
    min_points: int = 250  # about 0.16 m2 of wall at 2.5 cm voxels
    min_extent: float = 0.35  # metres of the wall's length that must be supported
    max_rms: float = 0.015  # metres; a line fitted worse than this is not one clean wall
    copy_offset: float = 0.08  # lines closer than this, facing the same way, are one wall
    copy_angle_deg: float = 3.0
    max_weight: float = 40.0  # cap so a spot stared at for long does not dominate a fit


SUPPORT_BIN = 0.05  # metres along a wall
SUPPORT_HEIGHT_BIN = 0.20  # metres up a wall
RELAXED_MIN_TOP = 1.50  # metres above the floor, used when upper walls were not captured


def wall_min_top(ceiling_height: float | None) -> float:
    """How high a surface must reach to count as wall rather than furniture or a door leaf.

    Walls run up to the ceiling. Door leaves stop near 2.0-2.1 m and most wardrobes and
    cabinets stop below the ceiling too, so a surface must reach within 45 cm of the
    ceiling, and never lower than 2.15 m.
    """
    if ceiling_height is None:
        return RELAXED_MIN_TOP
    return max(2.15, ceiling_height - 0.45)


@dataclass
class Level:
    """A near-horizontal plane z = a*x + b*y + c (floor or ceiling)."""

    coefficients: np.ndarray  # (a, b, c)
    rms: float
    count: int

    def z_at(self, xy: np.ndarray) -> np.ndarray:
        xy = np.atleast_2d(xy)
        a, b, c = self.coefficients
        return a * xy[:, 0] + b * xy[:, 1] + c

    @property
    def tilt_deg(self) -> float:
        a, b, _ = self.coefficients
        return float(np.degrees(np.arctan(np.hypot(a, b))))


@dataclass
class WallLine:
    """A vertical wall face seen from above: the line `normal . p = offset`.

    `normal` points away from the wall surface into the space it was seen from. `t` is the
    coordinate along the wall, measured along `direction`.
    """

    normal: np.ndarray  # (2,) unit
    offset: float
    rms: float
    sigma_offset: float  # 1-sigma of the fitted offset from point scatter alone
    sigma_angle: float  # radians
    points_xy: np.ndarray = field(repr=False)  # (N, 2) inlier positions
    points_z: np.ndarray = field(repr=False)  # (N,) inlier heights above the floor
    points_w: np.ndarray = field(repr=False)  # (N,) inlier weights
    min_top: float = RELAXED_MIN_TOP  # see `wall_min_top`
    _supported: np.ndarray | None = field(default=None, repr=False)

    @property
    def direction(self) -> np.ndarray:
        return np.array([-self.normal[1], self.normal[0]])

    @property
    def count(self) -> int:
        return len(self.points_xy)

    @property
    def points_t(self) -> np.ndarray:
        return self.points_xy @ self.direction

    def distance(self, xy: np.ndarray) -> np.ndarray:
        """Signed distance from the wall face; positive on the side the wall was seen from."""
        return np.atleast_2d(xy) @ self.normal - self.offset

    def along(self, xy: np.ndarray) -> np.ndarray:
        return np.atleast_2d(xy) @ self.direction

    def point(self, t: float) -> np.ndarray:
        return self.offset * self.normal + t * self.direction

    @property
    def supported_bins(self) -> np.ndarray:
        """Indices of the 5 cm stretches along the line where a real wall was seen.

        A stretch counts when its points reach `min_top` above the floor and occupy two or
        more 20 cm height bands. That keeps the wall above a door (its header) and a wall
        seen only above furniture, and rejects beds, tables, door leaves and stray points.
        """
        if self._supported is None:
            along = np.floor(self.points_t / SUPPORT_BIN).astype(np.int64)
            band = np.floor(self.points_z / SUPPORT_HEIGHT_BIN).astype(np.int64)
            stretches, inverse = np.unique(along, return_inverse=True)
            top = np.full(len(stretches), -np.inf)
            np.maximum.at(top, inverse, self.points_z)
            pairs = np.unique(np.stack([inverse, band], axis=1), axis=0)
            bands = np.bincount(pairs[:, 0], minlength=len(stretches))
            self._supported = stretches[(top >= self.min_top) & (bands >= 2)]
        return self._supported

    @property
    def supported_length(self) -> float:
        return len(self.supported_bins) * SUPPORT_BIN

    def coverage(self, t0: float, t1: float) -> float:
        """Share of the stretch [t0, t1] of this line where a real wall was seen."""
        lo, hi = min(t0, t1), max(t0, t1)
        first = int(np.floor(lo / SUPPORT_BIN + 0.5))
        last = int(np.floor(hi / SUPPORT_BIN - 0.5))
        if last < first:
            first = last = int(np.floor((lo + hi) / 2 / SUPPORT_BIN))
        wanted = np.arange(first, last + 1)
        return float(np.isin(wanted, self.supported_bins).mean())


def fit_level(xyz: np.ndarray, weight: np.ndarray, iterations: int = 5) -> Level:
    """Robust least-squares fit of z = a*x + b*y + c (Huber-style reweighting)."""
    centre = xyz[:, :2].mean(axis=0)
    A = np.column_stack([xyz[:, 0] - centre[0], xyz[:, 1] - centre[1], np.ones(len(xyz))])
    w = weight.astype(float).copy()
    coefficients = np.zeros(3)
    residual = np.zeros(len(xyz))
    for _ in range(iterations):
        sw = np.sqrt(w)
        coefficients, *_ = np.linalg.lstsq(A * sw[:, None], xyz[:, 2] * sw, rcond=None)
        residual = xyz[:, 2] - A @ coefficients
        scale = 1.4826 * np.median(np.abs(residual)) + 1e-6
        w = weight * np.minimum(1.0, (2.0 * scale) / np.maximum(np.abs(residual), 1e-12))
    a, b, c = coefficients
    rms = float(np.sqrt(np.average(residual**2, weights=w)))
    return Level(np.array([a, b, c - a * centre[0] - b * centre[1]]), rms, len(xyz))


def _height_peak(z: np.ndarray, config: PlaneConfig, pick: str) -> float | None:
    """Height of a peak in the histogram of `z`: the "lowest" or "highest" peak holding at
    least `level_min_share` of the largest, or the "strongest" peak."""
    if len(z) < 50:
        return None
    lo, hi = z.min(), z.max()
    bins = max(1, int(np.ceil((hi - lo) / config.level_bin)))
    histogram, edges = np.histogram(z, bins=bins, range=(lo, lo + bins * config.level_bin))
    smooth = np.convolve(histogram, np.ones(3), mode="same")
    strong = np.flatnonzero(smooth >= config.level_min_share * smooth.max())
    index = {"lowest": strong[0], "highest": strong[-1], "strongest": int(np.argmax(smooth))}[pick]
    # walk uphill to the local maximum next to the chosen bin
    while 0 < index < bins - 1:
        if smooth[index + 1] > smooth[index]:
            index += 1
        elif smooth[index - 1] > smooth[index]:
            index -= 1
        else:
            break
    return float((edges[index] + edges[index + 1]) / 2)


def find_level(
    cloud: Cloud, facing_up: bool, config: PlaneConfig | None = None, pick: str | None = None
) -> Level | None:
    """A floor (`facing_up=True`) or ceiling plane.

    By default the floor is the lowest strong peak of upward-facing points (beds and tables
    sit above it) and the ceiling is the highest strong peak of downward-facing points
    (table undersides and door heads sit below it).
    """
    config = config or PlaneConfig()
    nz = cloud.normal[:, 2]
    mask = nz > 0.9 if facing_up else nz < -0.9
    pick = pick or ("lowest" if facing_up else "highest")
    height = _height_peak(cloud.xyz[mask, 2], config, pick)
    if height is None:
        return None
    near = mask & (np.abs(cloud.xyz[:, 2] - height) < config.level_band)
    if near.sum() < 50:
        return None
    return fit_level(cloud.xyz[near], np.minimum(cloud.weight[near], config.max_weight))


def _facing_directions(theta: np.ndarray, config: PlaneConfig) -> list[float]:
    """Dominant directions wall faces look toward, in radians."""
    bins = 360
    histogram = np.bincount(
        (np.floor(np.degrees(theta) % 360)).astype(int) % bins, minlength=bins
    ).astype(float)
    kernel = np.exp(-0.5 * (np.arange(-6, 7) / 2.0) ** 2)
    smooth = np.convolve(
        np.concatenate([histogram[-6:], histogram, histogram[:6]]), kernel, mode="same"
    )[6:-6]
    total = histogram.sum()
    directions = []
    remaining = smooth.copy()
    while True:
        peak = int(np.argmax(remaining))
        refined = np.radians(peak + 0.5)
        near = np.zeros(len(theta), dtype=bool)
        for _ in range(3):
            # circular mean over a wide window, repeated so the window centres itself: the
            # mean of thousands of noisy normals is accurate to a small fraction of a degree
            near = np.abs((theta - refined + np.pi) % (2 * np.pi) - np.pi) < np.radians(15.0)
            if not near.any():
                break
            refined = np.arctan2(np.sin(theta[near]).mean(), np.cos(theta[near]).mean())
        if near.sum() < config.direction_min_share * total or near.sum() < config.min_points:
            break
        directions.append(float(refined))
        suppress = (np.arange(bins) - peak + 180) % 360 - 180
        remaining[np.abs(suppress) <= config.angle_tolerance_deg] = 0.0
        if remaining.max() <= 0:
            break
    return directions


def fit_line(xy: np.ndarray, weight: np.ndarray, toward: np.ndarray) -> tuple:
    """Total-least-squares line through 2D points; `toward` fixes the sign of the normal."""
    mean = np.average(xy, axis=0, weights=weight)
    centred = xy - mean
    covariance = (centred * weight[:, None]).T @ centred / weight.sum()
    values, vectors = np.linalg.eigh(covariance)
    normal = vectors[:, 0]
    if normal @ toward < 0:
        normal = -normal
    return normal, float(normal @ mean), float(np.sqrt(max(values[0], 0.0))), float(values[1])


def find_wall_lines(
    cloud: Cloud,
    floor: Level,
    ceiling: Level | None,
    config: PlaneConfig | None = None,
    min_top: float | None = None,
) -> list[WallLine]:
    """Every vertical wall face in the cloud, as a fitted 2D line with its inlier points.

    `min_top` is how high a surface must reach to count as wall; by default it is derived
    from the ceiling height (see `wall_min_top`).
    """
    config = config or PlaneConfig()
    if min_top is None:
        centre = cloud.xyz[:, :2].mean(axis=0)
        gap = None if ceiling is None else float(ceiling.z_at(centre)[0] - floor.z_at(centre)[0])
        min_top = wall_min_top(gap)
    height = cloud.xyz[:, 2] - floor.z_at(cloud.xyz[:, :2])
    mask = (np.abs(cloud.normal[:, 2]) < config.wall_max_nz) & (height > config.wall_min_height)
    if ceiling is not None:
        mask &= cloud.xyz[:, 2] < ceiling.z_at(cloud.xyz[:, :2]) + 0.05
    xy = cloud.xyz[mask, :2]
    z = height[mask]
    weight = np.minimum(cloud.weight[mask], config.max_weight)
    theta = np.arctan2(cloud.normal[mask, 1], cloud.normal[mask, 0])
    if len(xy) < config.min_points:
        return []

    tolerance = np.radians(config.angle_tolerance_deg)
    lines: list[WallLine] = []
    for direction_angle in _facing_directions(theta, config):
        facing = np.array([np.cos(direction_angle), np.sin(direction_angle)])
        delta = np.abs((theta - direction_angle + np.pi) % (2 * np.pi) - np.pi)
        available = delta < tolerance
        rho = xy @ facing
        refined = False
        while available.sum() >= config.min_points:
            values = rho[available]
            lo = values.min()
            bins = int(np.ceil((values.max() - lo) / config.offset_bin)) + 1
            histogram = np.bincount(((values - lo) / config.offset_bin).astype(int), minlength=bins)
            smooth = np.convolve(histogram, np.ones(3), mode="same")
            peak = int(np.argmax(smooth))
            if smooth[peak] < config.min_points / 3:
                break
            centre = lo + (peak + 0.5) * config.offset_bin
            members = available & (np.abs(rho - centre) < config.inlier_band)
            if members.sum() < config.min_points:
                available &= np.abs(rho - centre) >= config.inlier_band
                continue
            # free-angle fit, then reselect inliers against the fitted line and refit
            normal, offset, rms, _ = fit_line(xy[members], weight[members], facing)
            if not refined:
                # The strongest wall gives a far better direction than point normals do.
                # Distances along a direction that is one degree off smear by 7 cm over a
                # 4 m wall, so restart this direction with the fitted one.
                refined = True
                facing = normal
                rho = xy @ facing
                continue
            members = (delta < tolerance) & (np.abs(xy @ normal - offset) < config.inlier_band)
            normal, offset, rms, variance_t = fit_line(xy[members], weight[members], facing)
            available &= ~members
            available &= np.abs(rho - centre) >= config.inlier_band

            count = int(members.sum())
            if count < config.min_points or rms > config.max_rms:
                continue  # too few points, or a fit through a mixture of surfaces
            line = WallLine(
                normal=normal,
                offset=offset,
                rms=rms,
                sigma_offset=rms / np.sqrt(count),
                sigma_angle=rms / np.sqrt(count * max(variance_t, 1e-9)),
                points_xy=xy[members],
                points_z=z[members],
                points_w=weight[members],
                min_top=min_top,
            )
            if line.supported_length >= config.min_extent:
                lines.append(line)
    # A wall whose points are spread over more than the inlier band (residual drift, a
    # tiled lower half, a slightly bowed wall) comes out as two or three lines a few
    # centimetres apart. They are one wall: merge them.
    return merge_wall_copies(lines, config.copy_offset, config.copy_angle_deg)[0]


def merge_wall_copies(
    lines: list[WallLine], max_offset: float, max_angle_deg: float = 4.0, min_overlap: float = 0.5
) -> tuple[list[WallLine], int]:
    """Merge wall lines that are one wall seen at slightly different positions.

    Two lines are copies of one wall when they face the same way, lie within a few
    centimetres of each other, and overlap along their length. Lines that are side by side
    instead of on top of each other are a real step in the wall and are left alone.
    """
    lines = sorted(lines, key=lambda line: -line.count)
    merged = 0
    cos_limit = np.cos(np.radians(max_angle_deg))
    changed = True
    while changed:
        changed = False
        kept: list[WallLine] = []
        absorbed = [False] * len(lines)
        for i, base in enumerate(lines):
            if absorbed[i]:
                continue
            along_base = np.unique(np.floor(base.points_xy @ base.direction / 0.05))
            group = [base]
            for j in range(i + 1, len(lines)):
                other = lines[j]
                if absorbed[j] or base.normal @ other.normal < cos_limit:
                    continue
                if abs(float(np.mean(base.distance(other.points_xy)))) > max_offset:
                    continue
                along_other = np.unique(np.floor(other.points_xy @ base.direction / 0.05))
                shared = len(np.intersect1d(along_base, along_other))
                if shared < min_overlap * min(len(along_base), len(along_other)):
                    continue
                group.append(other)
                absorbed[j] = True
            if len(group) == 1:
                kept.append(base)
                continue
            xy = np.concatenate([line.points_xy for line in group])
            weight = np.concatenate([line.points_w for line in group])
            normal, offset, rms, variance_t = fit_line(xy, weight, base.normal)
            kept.append(
                WallLine(
                    normal=normal,
                    offset=offset,
                    rms=rms,
                    sigma_offset=rms / np.sqrt(len(xy)),
                    sigma_angle=rms / np.sqrt(len(xy) * max(variance_t, 1e-9)),
                    points_xy=xy,
                    points_z=np.concatenate([line.points_z for line in group]),
                    points_w=weight,
                    min_top=base.min_top,
                )
            )
            merged += len(group) - 1
            changed = True
        lines = sorted(kept, key=lambda line: -line.count)
    return lines, merged


def refit_stretch(
    line: WallLine,
    t0: float,
    t1: float,
    min_points: int = 150,
    min_extent: float = 1.0,
    margin: float = 0.05,
) -> WallLine:
    """Refit a wall face using only its points between `t0` and `t1` along the line.

    One detected line can run through several rooms (two walls that happen to be in line).
    Each room's wall is refitted on its own stretch so that a small step between them is not
    averaged away. Short or thinly seen stretches keep the direction of the whole line and
    only re-estimate their position, because a short stretch cannot pin down an angle.
    """
    t = line.points_t
    lo, hi = min(t0, t1) + margin, max(t0, t1) - margin
    members = (t >= lo) & (t <= hi)
    count = int(members.sum())
    if count < min_points // 3:
        return line
    xy, weight = line.points_xy[members], line.points_w[members]
    span = float(np.percentile(t[members], 97.5) - np.percentile(t[members], 2.5))
    if count >= min_points and span >= min_extent:
        normal, offset, rms, variance_t = fit_line(xy, weight, line.normal)
        sigma_angle = rms / np.sqrt(count * max(variance_t, 1e-9))
    else:
        normal = line.normal
        offset = float(np.average(xy @ normal, weights=weight))
        rms = float(np.sqrt(np.average((xy @ normal - offset) ** 2, weights=weight)))
        sigma_angle = line.sigma_angle
    return WallLine(
        normal=normal,
        offset=offset,
        rms=rms,
        sigma_offset=rms / np.sqrt(count),
        sigma_angle=sigma_angle,
        points_xy=xy,
        points_z=line.points_z[members],
        points_w=weight,
        min_top=line.min_top,
    )
