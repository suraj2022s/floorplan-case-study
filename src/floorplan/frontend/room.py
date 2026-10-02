"""Fit several levelled views to one rectangular room.

Each view already knows which way is up and has its walls lined up with the axes. What is
still unknown per view is where the camera stood, which of the four ways the view is turned,
and how far off its metric scale is. A room with four walls is described by two numbers,
its width and depth. Every wall a view sees gives one equation that is linear in all of
these:

    scale * (wall's distance in the view) + (wall normal . camera position) = wall's place

so the room and all views are solved together by weighted least squares.

Two facts make this work with very few photos:

* a view that sees both side walls measures the distance between them by itself. Where the
  camera stood does not enter into it;
* the distance to the wall behind the camera is never seen, so it has to be assumed. The
  capture protocol has the person stand with their back against a wall; the camera is then
  about 0.35 m in front of that wall. That assumption carries its own uncertainty and it
  is why depth-direction intervals are wider than side-to-side ones.

The turn of each view comes from the capture protocol (walk round the room clockwise,
photographing the opposite wall from the middle of each wall). If the views do not fit that
order, every combination of turns is tried and the best-fitting one is used, and the result
says so.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import product

import numpy as np

from floorplan.capture import Capture, Frame
from floorplan.frontend.views import LevelView, image_loader

STANDOFF = 0.35  # metres from the wall behind the person to the camera
STANDOFF_SIGMA = 0.15
SCALE_SIGMA = 0.06  # how far one view's scale may sit from the model's average (measured: 6%)
WALL_SIGMA = 0.03  # metres, plus 2% of the wall's distance
MISFIT = 0.25  # metres rms; above this the protocol order is not believed
OUTLIER = 0.30  # metres; a wall this far from the fitted room belongs to another room

# Room walls as (inward normal, which unknown its position is): S and W sit at zero.
_ROOM_WALLS = [
    (np.array([0.0, 1.0]), None),  # S wall, y = 0
    (np.array([0.0, -1.0]), "depth"),  # N wall, y = depth
    (np.array([1.0, 0.0]), None),  # W wall, x = 0
    (np.array([-1.0, 0.0]), "width"),  # E wall, x = width
]
# Protocol: photo k is taken walking clockwise; it looks north, east, south, west in turn.
_PROTOCOL_FORWARD = {2: [1, 3], 3: [1, 0, 3]}
_PROTOCOL_FORWARD_FULL = [1, 0, 3, 2]  # as multiples of 90 degrees from +x


@dataclass
class RoomFit:
    width: float
    depth: float
    quarters: list[int]  # turn of each view, local -> room, in multiples of 90 degrees
    positions: np.ndarray  # (N, 2) camera position of each view in the room frame
    scales: np.ndarray  # (N,)
    rms: float  # metres, how well the walls seen agree with one rectangle
    equations: int
    notes: list[str] = field(default_factory=list)


def _turn(quarter: int) -> np.ndarray:
    c, s = [(1, 0), (0, 1), (-1, 0), (0, -1)][quarter % 4]
    return np.array([[c, -s], [s, c]], dtype=float)


def _solve(views: list[LevelView], quarters: list[int], standoff: list[bool]) -> RoomFit | None:
    count = len(views)
    size = 2 + 3 * count  # width, depth, then (x, y, scale) per view
    rows, values, weights, is_wall = [], [], [], []

    def add(row: np.ndarray, value: float, sigma: float, wall: bool) -> None:
        rows.append(row)
        values.append(value)
        weights.append(1.0 / sigma)
        is_wall.append(wall)

    for k, view in enumerate(views):
        base = 2 + 3 * k
        R = _turn(quarters[k])
        for wall in view.walls:
            normal = R @ wall.normal
            match = max(range(4), key=lambda i: float(_ROOM_WALLS[i][0] @ normal))
            room_normal, unknown = _ROOM_WALLS[match]
            if room_normal @ normal < np.cos(np.radians(25.0)):
                continue  # a wall that is not square to the room: left out of the fit
            row = np.zeros(size)
            row[base : base + 2] = room_normal
            row[base + 2] = wall.offset
            if unknown == "width":
                row[0] = 1.0
            elif unknown == "depth":
                row[1] = 1.0
            add(row, 0.0, WALL_SIGMA + 0.02 * abs(wall.offset), True)

        row = np.zeros(size)
        row[base + 2] = 1.0
        add(row, 1.0, SCALE_SIGMA, False)

        forward = np.round(R @ view.forward).astype(int)  # the room direction the view faces
        if standoff[k]:
            behind = max(range(4), key=lambda i: float(_ROOM_WALLS[i][0] @ forward))
            room_normal, unknown = _ROOM_WALLS[behind]
            row = np.zeros(size)
            row[base : base + 2] = room_normal
            if unknown == "width":
                row[0] = 1.0
            elif unknown == "depth":
                row[1] = 1.0
            add(row, STANDOFF, STANDOFF_SIGMA, False)
        # a loose pull toward the middle of the room keeps an under-seen view from wandering
        for axis, unknown_index in ((0, 0), (1, 1)):
            row = np.zeros(size)
            row[base + axis] = 1.0
            row[unknown_index] = -0.5
            add(row, 0.0, 1.5, False)

    if sum(is_wall) < 2:
        return None
    rows_array, value_array = np.array(rows), np.array(values)
    weight_array, wall_rows = np.array(weights), np.array(is_wall)
    active = np.ones(len(rows), dtype=bool)
    dropped = 0
    while True:
        A = rows_array[active] * weight_array[active, None]
        solution, *_ = np.linalg.lstsq(A, value_array[active] * weight_array[active], rcond=None)
        residual = rows_array @ solution - value_array
        # A photo also shows walls of the next room through an open door. Such a wall
        # cannot be made to agree with the other views of this room, so the wall equation
        # that fits worst is dropped and the room is solved again, while it is clearly off.
        candidates = np.flatnonzero(active & wall_rows)
        worst = candidates[np.argmax(np.abs(residual[candidates]))]
        if abs(residual[worst]) <= OUTLIER or len(candidates) <= 3 or dropped >= 6:
            break
        active[worst] = False
        dropped += 1
    kept = residual[active & wall_rows]
    fit = RoomFit(
        width=float(solution[0]),
        depth=float(solution[1]),
        quarters=list(quarters),
        positions=solution[2:].reshape(count, 3)[:, :2],
        scales=solution[2:].reshape(count, 3)[:, 2],
        rms=float(np.sqrt(np.mean(kept**2))),
        equations=int(len(kept)),
    )
    fit.dropped = dropped  # type: ignore[attr-defined]
    return fit


def _plausible(fit: RoomFit | None) -> bool:
    return (
        fit is not None
        and 0.8 < fit.width < 20
        and 0.8 < fit.depth < 20
        and np.all(fit.scales > 0.7)
        and np.all(fit.scales < 1.4)
    )


def fit_room(views: list[LevelView]) -> RoomFit:
    """Width, depth and every view's pose and scale for one room."""
    usable = [k for k, view in enumerate(views) if view.walls]
    if not usable:
        raise ValueError("no wall is visible in any photo of this room")
    notes = [
        f"{views[k].view.name}: no wall visible, not used"
        for k in range(len(views))
        if k not in usable
    ]
    chosen = [views[k] for k in usable]
    count = len(chosen)

    forward = _PROTOCOL_FORWARD.get(count, _PROTOCOL_FORWARD_FULL[:count])
    protocol = [
        (forward[k] - chosen[k].facing_axis) % 4 if k < len(forward) else None for k in range(count)
    ]
    fixed = [q for q in protocol if q is not None]
    fit = _solve(chosen[: len(fixed)], fixed, [True] * len(fixed))

    if not _plausible(fit) or fit.rms > MISFIT:
        # The photos do not fit the protocol order. Try every combination of turns; the
        # first view defines the room's axes, so it keeps its turn.
        best = None
        first = (1 - chosen[0].facing_axis) % 4
        for rest in product(range(4), repeat=min(count, 6) - 1):
            candidate = _solve(chosen[: len(rest) + 1], [first, *rest], [True] * (len(rest) + 1))
            if _plausible(candidate) and (best is None or candidate.rms < best.rms):
                best = candidate
        if best is None:
            best = fit if fit is not None else _solve(chosen[:1], [first], [True])
        if best is None:
            raise ValueError("the photos of this room do not show enough wall to fit a room")
        fit = best
        notes.append(
            "the photos did not match the protocol order; the layout was chosen by best fit "
            "and opposite walls may be swapped"
        )
        fixed = fit.quarters

    # extra photos beyond the walk-round (close-ups): place each where it fits best, without
    # letting it change the room
    quarters = list(fixed)
    for k in range(len(fixed), count):
        options = []
        for quarter in range(4):
            trial = _solve(
                chosen[: len(fixed)] + [chosen[k]], fixed + [quarter], [True] * len(fixed) + [False]
            )
            if trial is not None:
                options.append((trial.rms, quarter))
        quarters.append(min(options)[1] if options else 0)
    final = _solve(chosen, quarters, [True] * len(fixed) + [False] * (count - len(fixed)))
    if final is None or not _plausible(final):
        final = fit
        chosen = chosen[: len(fit.quarters)]
    final.notes = notes
    final.used = usable[: len(final.quarters)]  # type: ignore[attr-defined]
    return final


def room_capture(
    views: list[LevelView], fit: RoomFit, room: str, tier: str = "photo", scale_sigma: float = 0.05
) -> Capture:
    """The room's views as one capture of posed depth frames in the room's frame."""
    used: list[int] = fit.used  # type: ignore[attr-defined]
    frames, depths = [], []
    for slot, index in enumerate(used):
        view = views[index]
        T = np.eye(4)
        turn = np.eye(3)
        turn[:2, :2] = _turn(fit.quarters[slot])
        T[:3, :3] = turn @ view.R_local_cam
        T[:2, 3] = fit.positions[slot]
        T[2, 3] = view.camera_height * fit.scales[slot]
        frames.append(
            Frame(
                index=slot,
                timestamp=float(slot),
                K=view.view.K,
                T_world_cam=T,
                name=f"{room}/{view.view.name}",
            )
        )
        depths.append((view.view.depth * fit.scales[slot]).astype(np.float32))
    return Capture(
        tier=tier,
        source=views[used[0]].view.source or views[used[0]].view.name,
        frames=frames,
        depth_loader=lambda i: depths[i],
        depth_sigma_a=0.01,
        depth_sigma_b=0.01,
        scale_sigma=scale_sigma,
        room_of_frame=[room] * len(frames),
        images={
            frame.name: image_loader(views[index].view, depths[slot])
            for slot, (frame, index) in enumerate(zip(frames, used, strict=True))
        },
        notes={"views": [views[i].view.name for i in used], "room_fit_rms_m": round(fit.rms, 4)},
    )
