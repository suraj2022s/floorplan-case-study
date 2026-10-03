"""The shared back-end: a `Capture` in, a measured floor plan out.

This is the one code path every tier runs. It never looks at which tier the capture came
from, except to pick up the uncertainties the front-end declared.

Stages, in order:

1. keyframes       drop near-duplicate frames;
2. fragments       turn short runs of frames into small point clouds;
3. drift           correct accumulated pose error (optional stage, on by default);
4. cloud           merge the fragments into one voxel-averaged point cloud;
5. planes          floor, ceiling and wall faces;
6. layout          wall lines -> cells -> rooms;
7. refine          refit each wall on its own points, rebuild the corners;
8. levels          floor and ceiling of each room, ceiling height;
9. openings        doors, windows and passages, with widths;
10. measure        attach an interval to every number.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np
import shapely

from floorplan.capture import Capture, Frame, select_keyframes
from floorplan.geometry.cloud import Cloud, CloudConfig, fragment_clouds, merge_clouds
from floorplan.geometry.drift import DriftConfig, correct_drift
from floorplan.geometry.layout import (
    LayoutConfig,
    Room,
    fallback_room,
    find_rooms,
    refine_room,
)
from floorplan.geometry.openings import Opening, OpeningConfig, find_openings
from floorplan.geometry.planes import (
    RELAXED_MIN_TOP,
    Level,
    PlaneConfig,
    WallLine,
    find_level,
    find_wall_lines,
)
from floorplan.uncertainty.budget import (
    BUDGETS,
    OBSERVED_SHARE,
    Calibration,
    Measurement,
    load_calibration,
    quadrature,
)


@dataclass(frozen=True)
class PipelineConfig:
    cloud: CloudConfig = field(default_factory=CloudConfig)
    planes: PlaneConfig = field(default_factory=PlaneConfig)
    drift: DriftConfig = field(default_factory=DriftConfig)
    layout: LayoutConfig = field(default_factory=LayoutConfig)
    openings: OpeningConfig = field(default_factory=OpeningConfig)
    correct_drift: bool = True
    room_inset: float = 0.10  # metres kept clear of the walls when fitting a room's levels


def config_for(tier: str, correct_drift: bool = True) -> PipelineConfig:
    """Settings for a tier.

    The stages are the same for every tier. What differs is how tight the tolerances can be:
    LiDAR depth is good to millimetres, depth predicted from an image is good to
    centimetres and bows flat walls slightly, so the bands inside which points count as
    "on the wall" are wider. Still images have no order in time either, so drift correction
    treats each photo as its own fragment with no smoothness between neighbours.
    """
    if tier == "lidar":
        return PipelineConfig(correct_drift=correct_drift)
    cloud = CloudConfig(
        voxel=0.03,
        min_confidence=0,
        min_depth=0.3,
        max_depth=9.0,
        edge_abs=0.05,
        edge_rel=0.05,
        normal_step=3,
        batch_frames=1 if tier == "photo" else 8,
        pixel_stride=1 if tier == "photo" else 2,
    )
    planes = PlaneConfig(
        level_band=0.10,
        inlier_band=0.07,
        min_points=200,
        max_rms=0.06,
        copy_offset=0.20,
        copy_angle_deg=6.0,
    )
    openings = OpeningConfig(
        cell=0.03,
        wall_band=0.08,
        beyond=0.20,
        max_range=9.0,
        # a room has only a few photos, so every pixel's ray is cast: seen at a slant (a
        # corridor's side doors from its end), every second pixel leaves the doorway striped
        pixel_stride=1 if tier == "photo" else 2,
        min_width=0.50,
        jamb_search=0.15,
        max_thickness=0.50,
        face_sigma=0.02,
        grid_sigma=0.03,
    )
    drift = DriftConfig(
        assign_distance=(0.35, 0.25, 0.18, 0.12),
        merge_offset=0.35,
        merge_angle_deg=8.0,
        thin=1 if tier == "photo" else 4,
        point_sigma=0.03,
        max_wall_rms=0.15,
        step_sigma_shift=10.0 if tier == "photo" else 0.03,
        step_sigma_turn_deg=90.0 if tier == "photo" else 0.3,
    )
    return PipelineConfig(
        cloud=cloud, planes=planes, drift=drift, openings=openings, correct_drift=correct_drift
    )


@dataclass
class WallResult:
    id: str
    start: np.ndarray
    end: np.ndarray
    length: Measurement
    observed_share: float


@dataclass
class RoomResult:
    id: str
    polygon: np.ndarray  # (N, 2) corners, counter-clockwise
    walls: list[WallResult]
    floor_area: Measurement
    ceiling_height: Measurement
    ceiling_height_range: tuple[float, float]
    entered: bool
    notes: list[str]
    floor_z: float = 0.0  # height of the floor in the plan's frame, at the room's middle


@dataclass
class OpeningResult:
    id: str
    kind: str
    room: str
    wall: str
    other_room: str | None
    width: Measurement
    height: Measurement
    sill: float
    position_along_wall: float
    wall_thickness: float | None
    centre: np.ndarray
    method: str
    evidence: str
    depth_beyond: float | None = None  # metres the space seen through it reaches behind it


@dataclass
class Plan:
    tier: str
    rooms: list[RoomResult]
    openings: list[OpeningResult]
    footprint_area: Measurement
    adjacency: list[tuple[str, str, str]]  # room, room, opening id
    warnings: list[str]
    timings: dict[str, float]
    stats: dict
    calibration: Calibration
    damage: list = field(default_factory=list)  # semantics.damage.DamageRegion
    flags: list = field(default_factory=list)  # semantics.rules.Flag
    scope: list = field(default_factory=list)  # semantics.scope.ScopeItem
    # the posed frames the plan was built from, for looking at the images afterwards
    frames: list[Frame] = field(default_factory=list, repr=False)
    images: dict = field(default_factory=dict, repr=False)  # frame name -> image loader


def _room_levels(
    room: Room,
    cloud: Cloud,
    global_floor: Level,
    global_ceiling: Level | None,
    config: PipelineConfig,
) -> tuple[Level, Level | None, list[str]]:
    """Floor and ceiling fitted on the points inside one room."""
    notes: list[str] = []
    inner = room.polygon.buffer(-config.room_inset)
    if inner.is_empty:
        inner = room.polygon
    inside = shapely.contains_xy(inner, cloud.xyz[:, 0], cloud.xyz[:, 1])
    local = cloud.select(inside)
    floor = find_level(local, facing_up=True, config=config.planes) if len(local) else None
    if floor is None:
        floor = global_floor
        notes.append("floor not seen in this room; the level of the whole capture is used")
    ceiling = (
        find_level(local, facing_up=False, config=config.planes, pick="strongest")
        if len(local)
        else None
    )
    if ceiling is None:
        ceiling = global_ceiling
        if ceiling is not None:  # with no ceiling anywhere, the room says so when measured
            notes.append("ceiling not seen in this room; the level of the whole capture is used")
    return floor, ceiling, notes


HIDDEN_SIGMA = 0.06  # metres, for a wall seen over only part of its length (see below)


def _position_sigma(edge, plane_sigma: float, inferred_sigma: float) -> tuple[float, bool]:
    """1-sigma on where a wall face sits, and whether the wall was actually observed.

    Three terms beyond the fit itself, each found on real scans against a laser:
    - the surface's own scatter (`rms`). A wall's points scatter by 7-9 mm; a curtain hung
      in front of a wall by 20-50 mm, and which of its folds is "the wall" is not known. The
      scatter is a bound on how far off the face can be, so it enters whole, not divided by
      the number of points;
    - the share of the wall that was hidden. Where furniture or a curtain stands in front of
      a wall, the face found may be theirs; on the benchmark scans such walls were up to
      12 cm in front of the laser's. A wall seen over its whole length carries none of this;
    - the tier's plane term, as before.
    """
    if edge.line is None or edge.coverage < OBSERVED_SHARE:
        return inferred_sigma, False
    hidden = HIDDEN_SIGMA * (1.0 - min(1.0, edge.coverage))
    return quadrature(edge.line.sigma_offset, edge.line.rms, plane_sigma, hidden), True


def _measure_room(
    room: Room,
    floor: Level,
    ceiling: Level | None,
    notes: list[str],
    capture: Capture,
    calibration: Calibration,
) -> RoomResult:
    budget = BUDGETS[capture.tier]
    scale = capture.scale_sigma
    count = len(room.edges)
    positions = [_position_sigma(e, budget.plane_sigma, budget.inferred_sigma) for e in room.edges]

    walls = []
    for k, edge in enumerate(room.edges):
        ends = []
        observed = True
        for j in ((k - 1) % count, (k + 1) % count):
            sigma, seen = positions[j]
            # a neighbour that meets this wall at a shallow angle moves the corner further
            a, b = edge.direction, room.edges[j].direction
            sine = abs(float(a[0] * b[1] - a[1] * b[0]))
            ends.append(sigma / max(sine, 0.2))
            observed &= seen
        sigma = quadrature(*ends, scale * edge.length, budget.definition_sigma)
        walls.append(
            WallResult(
                id=f"{room.name}-W{k + 1}",
                start=edge.p0,
                end=edge.p1,
                length=Measurement(
                    edge.length,
                    sigma * calibration.factor("wall_length"),
                    "observed" if observed else "inferred",
                ),
                observed_share=float(edge.coverage),
            )
        )

    area = room.area
    area_sigma = quadrature(
        *[edge.length * positions[k][0] for k, edge in enumerate(room.edges)], 2 * scale * area
    )
    all_seen = all(seen for _, seen in positions)

    centre = np.array(room.polygon.centroid.coords[0])
    if ceiling is None:
        height_value, height_range, height_sigma, height_basis = (
            float("nan"),
            (0.0, 0.0),
            0.0,
            "inferred",
        )
        notes = notes + ["no ceiling was captured anywhere; ceiling height is not reported"]
    else:
        corners = np.asarray(room.polygon.exterior.coords)[:-1]
        gaps = ceiling.z_at(corners) - floor.z_at(corners)
        height_value = float(ceiling.z_at(centre)[0] - floor.z_at(centre)[0])
        height_range = (float(gaps.min()), float(gaps.max()))
        fit = quadrature(floor.rms / np.sqrt(floor.count), ceiling.rms / np.sqrt(ceiling.count))
        seen_here = not any("not seen" in note for note in notes)
        height_sigma = quadrature(
            fit,
            budget.plane_sigma * np.sqrt(2),
            scale * height_value,
            budget.definition_sigma,
            0.0 if seen_here else budget.inferred_sigma,
        )
        height_basis = "observed" if seen_here else "inferred"

    return RoomResult(
        id=room.name,
        polygon=np.asarray(room.polygon.exterior.coords)[:-1],
        walls=walls,
        floor_area=Measurement(
            area,
            area_sigma * calibration.factor("floor_area"),
            "observed" if all_seen else "inferred",
            unit="m2",
        ),
        ceiling_height=Measurement(
            height_value, height_sigma * calibration.factor("ceiling_height"), height_basis
        ),
        ceiling_height_range=height_range,
        entered=room.entered,
        notes=notes + ([] if room.entered else ["seen through an opening but not walked into"]),
        floor_z=float(floor.z_at(centre)[0]),
    )


def _measure_opening(
    opening: Opening, room: RoomResult, capture: Capture, calibration: Calibration
) -> OpeningResult:
    budget = BUDGETS[capture.tier]
    scale = capture.scale_sigma
    width_sigma = quadrature(opening.width_sigma, scale * opening.width, budget.definition_sigma)
    height_sigma = quadrature(
        budget.plane_sigma * np.sqrt(2), 0.01, scale * opening.height, budget.definition_sigma
    )
    return OpeningResult(
        id=opening.id,
        kind=opening.kind,
        room=opening.room,
        wall=room.walls[opening.edge].id,
        other_room=opening.other_room,
        width=Measurement(opening.width, width_sigma * calibration.factor("opening_width")),
        height=(
            Measurement(opening.height, height_sigma * calibration.factor("opening_height"))
            if opening.top_seen
            else Measurement(float("nan"), float("nan"), "inferred")  # its top was never seen
        ),
        sill=opening.sill,
        position_along_wall=opening.u0,
        wall_thickness=opening.wall_thickness,
        centre=opening.centre,
        method=opening.method,
        evidence=opening.evidence,
        depth_beyond=opening.depth_beyond,
    )


def run(capture: Capture, config: PipelineConfig | None = None) -> Plan:
    """Run the whole back-end on a capture."""
    config = config or PipelineConfig()
    timings: dict[str, float] = {}
    warnings: list[str] = []
    stats: dict = {"frames_in": len(capture), "scale_sigma": capture.scale_sigma}

    def stage(name: str, started: float) -> None:
        timings[name] = round(time.perf_counter() - started, 3)

    started = time.perf_counter()
    keyframes = capture.subset(select_keyframes(capture.frames))
    stats["keyframes"] = len(keyframes)
    stage("keyframes", started)

    started = time.perf_counter()
    fragments, ranges = fragment_clouds(keyframes, config.cloud)
    stage("fragments", started)

    if config.correct_drift:
        started = time.perf_counter()
        keyframes, fragments, stats["drift"] = correct_drift(
            keyframes, fragments, ranges, config.drift, config.planes
        )
        if not stats["drift"]["applied"]:
            warnings.append(
                "drift correction could not run (" + stats["drift"]["reason"] + "); poses are "
                "used as recorded"
            )
        stage("drift", started)
    else:
        stats["drift"] = {"applied": False, "reason": "switched off"}
        warnings.append("drift correction was switched off; poses are used as recorded")

    started = time.perf_counter()
    cloud = merge_clouds(fragments, config.cloud.voxel)
    stats["cloud_points"] = len(cloud)
    stage("cloud", started)

    started = time.perf_counter()
    floor = find_level(cloud, facing_up=True, config=config.planes)
    if floor is None:
        raise RuntimeError("no floor found: the capture does not show enough of the floor")
    ceiling = find_level(cloud, facing_up=False, config=config.planes)
    if ceiling is None:
        warnings.append("no ceiling found: tilt the phone up so the ceiling is captured")
    lines = find_wall_lines(cloud, floor, ceiling, config.planes)
    stage("planes", started)

    started = time.perf_counter()
    camera_xy = np.array([frame.position[:2] for frame in keyframes.frames])
    rooms = find_rooms(cloud, lines, floor, camera_xy, config.layout)
    if not rooms:
        # upper walls were not captured, so nothing reached the height a wall must reach;
        # accept lower surfaces as walls and say so
        lines = find_wall_lines(cloud, floor, ceiling, config.planes, min_top=RELAXED_MIN_TOP)
        rooms = find_rooms(cloud, lines, floor, camera_xy, config.layout)
        if rooms:
            warnings.append(
                "the tops of the walls were not captured; furniture may have been taken for "
                "walls. Recapture with the phone tilted up along each wall."
            )
    if not rooms:
        # Not every wall was captured, so nothing closes. Report the rectangle around what
        # was seen, with the unseen sides marked, instead of reporting nothing.
        if not lines and ceiling is None:
            # a level surface and nothing else: a table top or a floor close-up, not a room
            raise RuntimeError(
                "no wall and no ceiling were captured, so there is no room to measure. "
                "Walk the room with the phone upright so that the walls are in view."
            )
        rescue = fallback_room(cloud, lines, floor, camera_xy, config.layout)
        if rescue is None:
            raise RuntimeError("no room found: the capture shows too little floor and wall")
        rooms = [rescue]
        stats["closure"] = "fallback"
        warnings.append(
            "the captured walls do not close a room; the plan is the rectangle around what "
            "was seen and its unseen sides are inferred. Capture every wall to measure it."
        )
    stats["wall_lines"] = len(lines)
    stage("layout", started)

    started = time.perf_counter()
    rooms = [refine_room(room) for room in rooms]
    stage("refine", started)

    started = time.perf_counter()
    floors: dict[str, Level] = {}
    ceilings: dict[str, Level | None] = {}
    level_notes: dict[str, list[str]] = {}
    heights: dict[str, float] = {}
    for room in rooms:
        room_floor, room_ceiling, notes = _room_levels(room, cloud, floor, ceiling, config)
        floors[room.name], ceilings[room.name], level_notes[room.name] = (
            room_floor,
            room_ceiling,
            notes,
        )
        centre = np.array(room.polygon.centroid.coords[0])
        heights[room.name] = (
            float(room_ceiling.z_at(centre)[0] - room_floor.z_at(centre)[0])
            if room_ceiling is not None
            else 2.4
        )
    stage("levels", started)

    started = time.perf_counter()
    openings = find_openings(
        rooms, floors, heights, cloud, keyframes, config.openings, config.cloud
    )
    stage("openings", started)

    started = time.perf_counter()
    calibration = load_calibration(capture.tier)
    if not calibration.calibrated:
        warnings.append(
            f"intervals for the {capture.tier} tier are not yet calibrated against a benchmark"
        )
    room_results = [
        _measure_room(
            room,
            floors[room.name],
            ceilings[room.name],
            level_notes[room.name],
            capture,
            calibration,
        )
        for room in rooms
    ]
    by_id = {room.id: room for room in room_results}
    opening_results = [_measure_opening(o, by_id[o.room], capture, calibration) for o in openings]

    footprint = sum(room.floor_area.value for room in room_results)
    # room areas share the capture's scale error, so that part adds linearly, not in quadrature
    independent = quadrature(
        *[
            np.sqrt(
                max(
                    room.floor_area.sigma**2
                    - (2 * capture.scale_sigma * room.floor_area.value) ** 2
                    * calibration.factor("floor_area") ** 2,
                    0.0,
                )
            )
            for room in room_results
        ]
    )
    footprint_sigma = quadrature(
        independent, 2 * capture.scale_sigma * footprint * calibration.factor("floor_area")
    )
    adjacency = sorted(
        (min(o.room, o.other_room), max(o.room, o.other_room), o.id)
        for o in opening_results
        if o.other_room is not None
    )
    stage("measure", started)

    return Plan(
        tier=capture.tier,
        rooms=room_results,
        openings=opening_results,
        footprint_area=Measurement(footprint, footprint_sigma, unit="m2"),
        adjacency=adjacency,
        warnings=warnings,
        timings=timings,
        stats=stats,
        calibration=calibration,
        frames=list(keyframes.frames),
        images=dict(capture.images),
    )


__all__ = ["Plan", "PipelineConfig", "WallLine", "run"]
