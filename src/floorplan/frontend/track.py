"""Camera path for a video, from depth frames and the walls they see.

A video has no poses. Each sampled frame is levelled and its walls are lined up with the
axes (`views.py`), so what remains unknown per frame is where the camera was, which quarter
turn the frame is in, and how far off its depth scale is. Three sources of information fix
them, and all are combined in one least-squares problem.

* **Frame to frame.** Two consecutive frames show mostly the same surfaces. With gravity
  and the wall directions already known, the only thing that differs between them is a
  shift, which is found by sliding one frame's points onto the other's (an alignment that
  solves for translation only). This works on anything in view: floor, furniture, door
  frames. It carries the camera through a doorway, where for a moment no wall is shared
  between what is behind and what is ahead.
* **Walls.** A wall does not move. Every wall a frame sees gives one equation

      scale * (wall's distance in the frame) + (wall normal . camera position) = wall's place

  in which the wall's place is shared by every frame that sees that wall. Frame-to-frame
  shifts accumulate error; walls do not, and coming back to a wall seen earlier ties the
  end of the walk to its start, so loop closure needs no separate step.
* **Scale.** A depth model's scale wobbles by a few percent from frame to frame. Frames
  that see the same two walls must agree on the distance between them, which ties their
  scales together; the average stays at the model's own scale.

The quarter turn of a frame is the one under which it lines up best with the frame before.

Limits: it needs square-built interiors (walls at right angles), and the whole path
inherits the depth model's average scale error, which nothing in the video can reveal.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy.spatial import cKDTree

from floorplan.capture import Capture, Frame
from floorplan.frontend.views import LevelView, image_loader

SCALE_SIGMA = 0.06  # how far one frame's scale may sit from the model's average (measured: 6%)
STEP_SIGMA = 1.0  # metres; a loose "the camera does not teleport" between sampled frames
SHIFT_SIGMA = 0.04  # metres, a frame-to-frame shift along a well-constrained direction
WALL_SIGMA = 0.03  # metres, plus 2% of the wall's distance
SAME_WALL = 0.25  # metres: a wall predicted this close to a known wall is that wall
SEARCH = 0.40  # metres around the predicted position in which known walls are looked for
OUTLIER = 0.25  # metres: an observation this far from its wall after the solve is dropped
PAIR_REACH = 0.30  # metres: points farther apart than this are not paired when aligning
MIN_FITNESS = 0.35  # share of points that must land within 10 cm for an alignment to count
MAX_MOVE = 1.0  # metres the camera can move between two sampled frames
MERGE = 0.15  # metres: solved walls this close, facing the same way, are one wall
TRUSTED_SHARE = 60.0  # points' worth of evidence a direction needs for its shift to be used
FULL_EVIDENCE = 600.0  # points' worth at which a shift gets its full weight
AMBIGUOUS = 0.10  # difference in cos(angle) below which two quarter turns are a toss-up
_AXES = [np.array([1.0, 0.0]), np.array([0.0, 1.0]), np.array([-1.0, 0.0]), np.array([0.0, -1.0])]


def _turn(quarter: int) -> np.ndarray:
    c, s = [(1, 0), (0, 1), (-1, 0), (0, -1)][quarter % 4]
    return np.array([[c, -s], [s, c]], dtype=float)


def _turn3(points: np.ndarray, quarter: int) -> np.ndarray:
    out = points.astype(np.float64).copy()
    out[:, :2] = points[:, :2] @ _turn(quarter).T
    return out


@dataclass
class Track:
    quarters: list[int]
    positions: np.ndarray  # (N, 2)
    scales: np.ndarray  # (N,)
    used: list[int]  # indices of the views that were placed
    walls: int
    rms: float
    notes: list[str] = field(default_factory=list)


@dataclass
class _Sighting:
    frame: int  # position in the list of placed frames
    wall: int  # index of the shared wall
    normal: np.ndarray
    offset: float  # the wall's signed distance term in the frame's own coordinates


@dataclass
class _Shift:
    frame: int  # the shift is from this frame to the next
    move: np.ndarray  # (2,) how far the camera moved
    share: np.ndarray  # (2,) evidence along each axis, in points' worth
    fitness: float


def align_shift(
    previous: tuple[np.ndarray, np.ndarray], current: np.ndarray, guess: np.ndarray
) -> _Shift | None:
    """How far the camera moved between two frames whose axes already agree.

    `previous` is (points, normals) of the earlier frame, `current` the later frame's
    points, each in its own camera-centred frame. A point seen in both frames satisfies
    p_previous = p_current + move, so `move` is found by point-to-plane alignment with
    translation as the only unknown.
    """
    points, normals = previous
    if len(points) < 200 or len(current) < 200:
        return None
    tree = cKDTree(points)
    move = np.array([guess[0], guess[1], 0.0])
    information = np.zeros((3, 3))
    paired = 0
    for _ in range(10):
        distance, index = tree.query(current + move, distance_upper_bound=PAIR_REACH)
        ok = np.isfinite(distance)
        paired = int(ok.sum())
        if paired < 200:
            return None
        n = normals[index[ok]]
        residual = np.einsum("ij,ij->i", current[ok] + move - points[index[ok]], n)
        weight = 1.0 / (1.0 + (residual / 0.05) ** 2)
        information = (n * weight[:, None]).T @ n
        step = -np.linalg.solve(
            information + 1e-3 * np.eye(3) * weight.sum(), (n * weight[:, None]).T @ residual
        )
        move += step
        if np.linalg.norm(step) < 1e-3:
            break
    distance, _ = tree.query(current + move, distance_upper_bound=0.10)
    # how many points' worth of evidence pins the shift along x and along y. A bare wall
    # seen square-on gives thousands across it and none along it.
    share = np.diag(information)[:2].copy()
    return _Shift(-1, move[:2].copy(), share, float(np.isfinite(distance).mean()))


def _solve(count: int, walls: int, sightings: list[_Sighting], shifts: list[_Shift]) -> tuple:
    """Least squares over camera positions, scales and wall places."""
    size = 3 * count + walls
    rows, values, weights = [], [], []
    for item in sightings:
        row = np.zeros(size)
        row[3 * item.frame : 3 * item.frame + 2] = item.normal
        row[3 * item.frame + 2] = item.offset
        row[3 * count + item.wall] = -1.0
        rows.append(row)
        values.append(0.0)
        weights.append(1.0 / (WALL_SIGMA + 0.02 * abs(item.offset)))
    for shift in shifts:
        for axis in range(2):
            if shift.share[axis] < TRUSTED_SHARE:
                continue  # nothing in view constrains this direction
            row = np.zeros(size)
            row[3 * (shift.frame + 1) + axis] = 1.0
            row[3 * shift.frame + axis] = -1.0
            rows.append(row)
            values.append(float(shift.move[axis]))
            weights.append(
                np.sqrt(min(shift.share[axis], FULL_EVIDENCE) / FULL_EVIDENCE) / SHIFT_SIGMA
            )
    for k in range(count):
        row = np.zeros(size)
        row[3 * k + 2] = 1.0
        rows.append(row)
        values.append(1.0)
        weights.append(1.0 / SCALE_SIGMA)
    for k in range(count - 1):
        for axis in range(2):
            row = np.zeros(size)
            row[3 * (k + 1) + axis] = 1.0
            row[3 * k + axis] = -1.0
            rows.append(row)
            values.append(0.0)
            weights.append(1.0 / STEP_SIGMA)
    for axis in range(2):  # the first frame is the origin
        row = np.zeros(size)
        row[axis] = 1.0
        rows.append(row)
        values.append(0.0)
        weights.append(1e4)
    A, b, w = np.array(rows), np.array(values), np.array(weights)
    solution, *_ = np.linalg.lstsq(A * w[:, None], b * w, rcond=None)
    residual = (A @ solution - b)[: len(sightings)]
    return solution, residual


def track_views(views: list[LevelView]) -> Track:
    """Quarter turn, position and scale of every view that sees a wall."""
    used = [k for k, view in enumerate(views) if view.walls]
    if len(used) < 2:
        raise ValueError("fewer than two frames show a wall; the camera path cannot be found")
    notes = []
    if len(used) < len(views):
        notes.append(f"{len(views) - len(used)} frame(s) show no wall and were left out")

    wall_axis: list[int] = []  # which of the four directions each shared wall faces
    wall_place: list[float] = []  # running estimate of normal . point on the wall
    wall_count: list[int] = []
    sightings: list[_Sighting] = []
    shifts: list[_Shift] = []
    position = np.zeros(2)
    velocity = np.zeros(2)
    heading = None
    previous = None  # (points, normals) of the last placed frame, in the shared axes
    quarters: list[int] = []
    unaligned = 0

    def seen_walls(view: LevelView, quarter: int) -> list[tuple[int, float]]:
        """The walls a view sees, as (direction faced, signed distance term)."""
        R = _turn(quarter)
        seen = []
        for wall in view.walls:
            normal = R @ wall.normal
            axis = max(range(4), key=lambda i: float(_AXES[i] @ normal))
            if _AXES[axis] @ normal > np.cos(np.radians(20.0)):
                seen.append((axis, float(wall.offset)))
        return seen

    for slot, index in enumerate(used):
        view = views[index]
        # 1. quarter turn and shift since the last frame: the turn under which this frame
        #    lines up best with the previous one. Only the two turns closest to "carry on
        #    looking the same way" are tried.
        shift = None
        if heading is None:
            quarter = 0
        else:
            # The camera turns far less than 45 degrees between two sampled frames, so the
            # quarter turn that keeps the viewing direction closest to the last frame's is
            # the right one. Only when the two best candidates are nearly as close (the
            # camera turned about 45 degrees) is the alignment asked to decide.
            closeness = {q: float(_turn(q) @ view.forward @ heading) for q in range(4)}
            ranked = sorted(range(4), key=lambda q: -closeness[q])
            quarter = ranked[0]
            shift = align_shift(previous, _turn3(view.points, quarter), velocity)
            if closeness[ranked[0]] - closeness[ranked[1]] < AMBIGUOUS:
                other = align_shift(previous, _turn3(view.points, ranked[1]), velocity)
                mine = shift.fitness if shift is not None else 0.0
                if other is not None and other.fitness > mine + 0.25:
                    quarter, shift = ranked[1], other
            # an alignment that pairs too few points, or asks for an impossible move, is
            # not evidence of anything
            if shift is not None and (
                shift.fitness < MIN_FITNESS or np.linalg.norm(shift.move) > MAX_MOVE
            ):
                shift = None
            if shift is None:
                unaligned += 1
        quarters.append(quarter)
        heading = _turn(quarter) @ view.forward
        # Along a direction nothing in view constrains (sliding along a single bare wall),
        # the alignment returns noise. There the camera is assumed to carry on as before.
        trusted = np.zeros(2, dtype=bool) if shift is None else shift.share >= TRUSTED_SHARE
        predicted = position + np.where(trusted, shift.move if shift is not None else 0.0, velocity)

        # 2. which known wall is each wall seen now? Along each coordinate, every pairing of
        #    a wall seen with a known wall facing the same way proposes a position; the one
        #    most sightings agree on, nearest the prediction, wins.
        seen = seen_walls(view, quarter)
        here = predicted.copy()
        for coordinate in range(2):
            proposals = []
            for axis, offset in seen:
                sign = _AXES[axis][coordinate]
                if abs(sign) < 0.5:
                    continue
                for j in range(len(wall_axis)):
                    if wall_axis[j] == axis:
                        move = (wall_place[j] - offset) * sign - predicted[coordinate]
                        if abs(move) <= SEARCH:
                            proposals.append(move)
            if proposals:
                moves = np.array(proposals)
                votes = [(np.abs(moves - m) < 0.12).sum() for m in moves]
                best = max(range(len(moves)), key=lambda i: (votes[i], -abs(moves[i])))
                here[coordinate] += float(np.mean(moves[np.abs(moves - moves[best]) < 0.12]))
                trusted[coordinate] = True
        for axis, offset in seen:
            place = offset + _AXES[axis] @ here
            close = [
                j
                for j in range(len(wall_axis))
                if wall_axis[j] == axis and abs(wall_place[j] - place) < SAME_WALL
            ]
            if close:
                j = min(close, key=lambda j: abs(wall_place[j] - place))
                wall_place[j] = (wall_place[j] * wall_count[j] + place) / (wall_count[j] + 1)
                wall_count[j] += 1
            else:
                wall_axis.append(axis)
                wall_place.append(float(place))
                wall_count.append(1)
                j = len(wall_axis) - 1
            sightings.append(_Sighting(slot, j, _AXES[axis], offset))

        if shift is not None:
            shift.frame = slot - 1
            shifts.append(shift)
        # carry half of the last measured motion forward; a direction that was not measured
        # this time decays toward standing still
        velocity = (
            np.where(trusted, 0.5 * (here - position), 0.5 * velocity) if slot else np.zeros(2)
        )
        position = here
        previous = (_turn3(view.points, quarter), _turn3(view.normals, quarter))

    if unaligned:
        notes.append(f"{unaligned} frame(s) could not be lined up with the frame before")

    # 3. solve everything together. While walking, a wall met again after a detour can be
    #    taken for a new wall because the running position had drifted by then. Solved
    #    together the two come out in nearly the same place; they are then made one wall
    #    and the problem is solved again, which is what closes the loop.
    count = len(used)
    solution, residual = _solve(count, len(wall_axis), sightings, shifts)
    merged_walls = 0
    for _ in range(4):
        places = solution[3 * count :]
        target = list(range(len(wall_axis)))
        order = sorted(range(len(wall_axis)), key=lambda j: -wall_count[j])
        for position_in_order, j in enumerate(order):
            for k in order[:position_in_order]:
                if (
                    target[k] == k
                    and wall_axis[k] == wall_axis[j]
                    and abs(places[k] - places[j]) < MERGE
                ):
                    target[j] = k
                    wall_count[k] += wall_count[j]
                    break
        if all(target[j] == j for j in range(len(target))):
            break
        kept = [j for j in range(len(target)) if target[j] == j]
        renumber = {j: i for i, j in enumerate(kept)}
        merged_walls += len(target) - len(kept)
        for sighting in sightings:
            sighting.wall = renumber[target[sighting.wall]]
        wall_axis = [wall_axis[j] for j in kept]
        wall_count = [wall_count[j] for j in kept]
        solution, residual = _solve(count, len(wall_axis), sightings, shifts)
    if merged_walls:
        notes.append(f"{merged_walls} wall(s) met again later in the walk were recognised")
    keep = np.abs(residual) < OUTLIER
    if keep.sum() >= max(4, 0.5 * len(sightings)) and not keep.all():
        sightings = [s for s, good in zip(sightings, keep, strict=True) if good]
        notes.append(
            f"{int((~keep).sum())} wall sighting(s) disagreed with the rest and were dropped"
        )
        solution, residual = _solve(count, len(wall_axis), sightings, shifts)
    frames = solution[: 3 * count].reshape(count, 3)
    return Track(
        quarters=quarters,
        positions=frames[:, :2],
        scales=frames[:, 2],
        used=used,
        walls=len(wall_axis),
        rms=float(np.sqrt(np.mean(residual**2))),
        notes=notes,
    )


def track_capture(
    views: list[LevelView], track: Track, source, timestamps: list[float], scale_sigma: float = 0.04
) -> Capture:
    """The tracked frames as one capture of posed depth frames."""
    # camera height changes slowly; a frame that cannot see the floor borrows its neighbours'
    heights = np.array(
        [views[i].camera_height if views[i].floor is not None else np.nan for i in track.used]
    )
    if np.isnan(heights).all():
        heights[:] = 1.40
    else:
        known = np.flatnonzero(~np.isnan(heights))
        heights = np.interp(np.arange(len(heights)), known, heights[known])

    frames, depths = [], []
    for slot, index in enumerate(track.used):
        view = views[index]
        turn = np.eye(3)
        turn[:2, :2] = _turn(track.quarters[slot])
        T = np.eye(4)
        T[:3, :3] = turn @ view.R_local_cam
        T[:2, 3] = track.positions[slot]
        T[2, 3] = heights[slot] * track.scales[slot]
        frames.append(
            Frame(
                index=index,
                timestamp=float(timestamps[index]),
                K=view.view.K,
                T_world_cam=T,
                name=view.view.name,
            )
        )
        depths.append((view.view.depth * track.scales[slot]).astype(np.float32))
    return Capture(
        tier="video",
        source=source,
        frames=frames,
        depth_loader=lambda i: depths[i],
        depth_sigma_a=0.01,
        depth_sigma_b=0.01,
        scale_sigma=scale_sigma,
        images={
            frame.name: image_loader(views[index].view, depths[slot])
            for slot, (frame, index) in enumerate(zip(frames, track.used, strict=True))
        },
        notes={
            "frames_tracked": len(frames),
            "walls_tracked": track.walls,
            "track_rms_m": round(track.rms, 4),
        },
    )
