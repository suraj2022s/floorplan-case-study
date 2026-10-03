"""Video tier: camera poses from structure from motion, metric depth from a depth model.

    clip -> frames, 4 a second, 960 px wide
         -> COLMAP (SIFT features, sequential matching, incremental mapping): camera poses
            and focal length, up to an unknown scale
         -> MoGe-2 depth for the registered frames, given COLMAP's focal length
         -> scale: each frame's depth against the COLMAP points it sees; the median over
            frames sets metres per COLMAP unit, and each frame's depth is rescaled to agree
         -> level the frame (z up, floor at z = 0) -> Capture -> the shared back-end

Why this split, measured on the real clip of a bedroom (ARKitScenes 47333462): where COLMAP
held the track, its camera positions were within 1 cm of ARKit's (median) and its relative
rotations within 0.7 degrees. A learned multi-view model was 40 to 70 cm off on the same
frames, and following the camera from depth and walls alone was 90 cm off. COLMAP knows
neither metric scale nor which way is up: the depth model supplies the scale, the surfaces
supply up. The scale is the tier's dominant uncertainty and goes into every interval.

COLMAP's random choices are seeded and its result is cached by the frames' content, so a
rerun on the same clip replays the same poses.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import cv2
import numpy as np

from floorplan.capture import Capture, Frame
from floorplan.frontend.views import View, estimate_up, image_loader
from floorplan.geometry.cloud import _normals, backproject

ROOT = Path(__file__).resolve().parents[3]
RATE = 4.0  # frames a second taken from the clip
LONG_SIDE = 960  # pixels; COLMAP and the depth model work on frames this size
MAX_FRAMES = 360
DEPTH_EVERY = 2  # depth is predicted for every second registered frame
MIN_REGISTERED = 12
LOOP_FRAMES = 80  # frames matched all against all, for loop closure
# changes whenever the way poses are computed changes, so the cache never replays old ones
METHOD = "colmap-incremental/loop80/inliers15/joined/v3"
VIDEO_SCALE_SIGMA = 0.05  # relative 1-sigma of the depth model's metric scale (measured)


def sample_clip(
    path: Path, rate: float = RATE, long_side: int = LONG_SIDE, max_frames: int = MAX_FRAMES
) -> tuple[list[np.ndarray], list[float]]:
    """RGB frames at `rate` per second, shrunk to `long_side`, with their times."""
    reader = cv2.VideoCapture(str(path))
    if not reader.isOpened():
        raise OSError(f"could not open video {path}")
    try:
        fps = reader.get(cv2.CAP_PROP_FPS) or 30.0
        total = int(reader.get(cv2.CAP_PROP_FRAME_COUNT))
        stride = max(1, round(fps / rate))
        if total > 0 and total / stride > max_frames:
            stride = int(np.ceil(total / max_frames))
        frames, times, index = [], [], 0
        while reader.grab():
            if index % stride == 0:
                ok, frame = reader.retrieve()
                if not ok:
                    break
                height, width = frame.shape[:2]
                scale = min(1.0, long_side / max(height, width))
                if scale < 1.0:
                    frame = cv2.resize(
                        frame,
                        (round(width * scale), round(height * scale)),
                        interpolation=cv2.INTER_AREA,
                    )
                frames.append(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                times.append(index / fps)
            index += 1
    finally:
        reader.release()
    if len(frames) < 3:
        raise ValueError(f"{path} has fewer than three readable frames")
    return frames, times


def structure_from_motion(frames: list[np.ndarray], cache_dir: Path | None = None) -> dict:
    """COLMAP on the frames: per registered frame its pose (camera from world) and the
    COLMAP points it sees; plus the focal length. Cached by the frames' content."""
    import pycolmap

    digest = hashlib.sha256(METHOD.encode())
    for frame in frames:
        digest.update(frame.tobytes())
    key = digest.hexdigest()[:24]
    cache_dir = Path(cache_dir or ROOT / ".cache" / "sfm")
    cached = cache_dir / f"{key}.npz"
    if cached.is_file():
        data = np.load(cached, allow_pickle=False)
        return json.loads(str(data["result"]))

    work = cache_dir / key
    if work.exists():
        shutil.rmtree(work)
    (work / "images").mkdir(parents=True)
    names = [f"{k:05d}.jpg" for k in range(len(frames))]
    for name, frame in zip(names, frames, strict=True):
        cv2.imwrite(
            str(work / "images" / name),
            cv2.cvtColor(frame, cv2.COLOR_RGB2BGR),
            [cv2.IMWRITE_JPEG_QUALITY, 95],
        )
    database = work / "database.db"
    reader = pycolmap.ImageReaderOptions()
    reader.camera_model = "SIMPLE_RADIAL"
    extraction = pycolmap.FeatureExtractionOptions()
    extraction.sift.max_num_features = 4096
    pycolmap.extract_features(
        database,
        work / "images",
        camera_mode=pycolmap.CameraMode.SINGLE,
        reader_options=reader,
        extraction_options=extraction,
    )
    pairing = pycolmap.SequentialPairingOptions()
    pairing.overlap = 10
    pairing.quadratic_overlap = True
    pycolmap.match_sequential(database, pairing_options=pairing)
    # loop closure: a walk comes back past what it saw before. Matching every few frames
    # against every other lets a stretch the track lost (a fast turn, a bare wall) be
    # joined back through the furniture seen before and after it
    step = max(1, len(names) // LOOP_FRAMES)
    keys = names[::step]
    pairs = [
        f"{a} {b}"
        for i, a in enumerate(keys)
        for b in keys[i + 1 :]
        if names.index(b) - names.index(a) > pairing.overlap
    ]
    if pairs:
        (work / "loop_pairs.txt").write_text("\n".join(pairs) + "\n")
        imported = pycolmap.ImportedPairingOptions()
        imported.match_list_path = str(work / "loop_pairs.txt")
        pycolmap.match_image_pairs(database, pairing_options=imported)
    options = pycolmap.IncrementalPipelineOptions()
    options.min_model_size = 5
    options.random_seed = 0
    # register a frame on fewer matches than the default: measured on a real walkthrough,
    # this keeps 2 cm accuracy against ARKit and places 40% more frames in one piece
    options.mapper.abs_pose_min_num_inliers = 15
    options.mapper.abs_pose_min_inlier_ratio = 0.15
    models = pycolmap.incremental_mapping(database, work / "images", work / "sparse", options)
    if not models:
        raise RuntimeError("could not follow the camera through the clip (no reconstruction)")
    pieces = sorted(models.values(), key=lambda model: -model.num_reg_images())
    camera = next(iter(pieces[0].cameras.values()))
    registered, joined = _join_pieces([_piece(model, names) for model in pieces])
    result = {
        "focal": float(camera.params[0]),
        "width": int(camera.width),
        "height": int(camera.height),
        "registered": {str(k): v for k, v in registered.items()},
        "models": [int(model.num_reg_images()) for model in pieces],
        "joined": joined,
    }
    cache_dir.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(cached, result=np.array(json.dumps(result)))
    shutil.rmtree(work, ignore_errors=True)
    return result


def _piece(model, names: list[str]) -> dict[int, dict]:
    """Per registered frame of one COLMAP model: its pose and the model points it sees."""
    entries = {}
    for image in model.images.values():
        if not image.has_pose:
            continue
        pose = image.cam_from_world() if callable(image.cam_from_world) else image.cam_from_world
        observed = [(p.xy, p.point3D_id) for p in image.points2D if p.has_point3D()]
        entries[names.index(image.name)] = {
            "R": pose.rotation.matrix(),
            "t": np.asarray(pose.translation, dtype=float),
            "uv": np.array([xy for xy, _ in observed], dtype=float).reshape(-1, 2),
            "xyz": np.array(
                [model.points3D[index].xyz for _, index in observed], dtype=float
            ).reshape(-1, 3),
        }
    return entries


def _similarity(source: np.ndarray, target: np.ndarray) -> tuple[float, np.ndarray, np.ndarray]:
    """Scale, rotation and shift taking `source` points onto `target` (Umeyama)."""
    mu_s, mu_t = source.mean(axis=0), target.mean(axis=0)
    a, b = source - mu_s, target - mu_t
    u, s, vt = np.linalg.svd(b.T @ a)
    d = np.diag([1.0, 1.0, np.sign(np.linalg.det(u @ vt))])
    R = u @ d @ vt
    scale = float(np.trace(np.diag(s) @ d) / max((a**2).sum(), 1e-12))
    return scale, R, mu_t - scale * R @ mu_s


def _join_pieces(pieces: list[dict[int, dict]]) -> tuple[dict[int, dict], int]:
    """Join COLMAP's separate models through the frames they share.

    When the incremental mapper loses the track it starts a new model, and it lets a new
    model re-use up to 20 frames of earlier ones. Those shared frames have a pose in both,
    which fixes the scale, rotation and shift between the two. A model sharing fewer than
    three frames, or whose shared frames do not agree to 5% of the model's size, is left out.
    Returns the joined frames (as JSON-ready lists) and how many models went in.
    """
    joined = dict(pieces[0])
    pending = list(pieces[1:])
    count = 1
    while pending:
        for piece in pending:
            shared = sorted(set(joined) & set(piece))
            if len(shared) < 3:
                continue
            centre = lambda e: -e["R"].T @ e["t"]  # noqa: E731
            source = np.array([centre(piece[k]) for k in shared])
            target = np.array([centre(joined[k]) for k in shared])
            scale, R, shift = _similarity(source, target)
            residual = np.linalg.norm(scale * source @ R.T + shift - target, axis=1)
            extent = float(np.ptp(np.array([centre(e) for e in joined.values()]), axis=0).max())
            if residual.max() > 0.05 * max(extent, 1e-6):
                continue
            for k, entry in piece.items():
                if k in joined:
                    continue
                R_wc = R @ entry["R"].T
                c = scale * R @ centre(entry) + shift
                joined[k] = {
                    "R": R_wc.T,
                    "t": -R_wc.T @ c,
                    "uv": entry["uv"],
                    "xyz": scale * entry["xyz"] @ R.T + shift,
                }
            pending.remove(piece)
            count += 1
            break
        else:
            break
    ready = {
        k: {key: np.asarray(value).tolist() for key, value in entry.items()}
        for k, entry in joined.items()
    }
    return ready, count


def _level(views: list[View], poses: list[np.ndarray]) -> tuple[list[np.ndarray], float]:
    """Turn the frame so that z is up and the floor is at z = 0."""
    normals, ups = [], []
    for view, T in zip(views, poses, strict=True):
        depth = view.depth.astype(np.float64)
        points = backproject(depth, view.K)
        computed, ok = _normals(points, depth > 0, 3)
        picked = computed[ok][:: max(1, int(ok.sum()) // 15000)]
        normals.append(picked @ T[:3, :3].T)
        ups.append(-T[:3, 1])  # the top of each picture, in COLMAP's frame
    up = estimate_up(np.concatenate(normals), initial=np.mean(ups, axis=0))
    forward = poses[0][:3, 2] - (poses[0][:3, 2] @ up) * up
    forward /= np.linalg.norm(forward)
    turn = np.stack([forward, np.cross(up, forward), up])
    levelled = []
    for T in poses:
        L = np.eye(4)
        L[:3, :3] = turn @ T[:3, :3]
        L[:3, 3] = turn @ T[:3, 3]
        levelled.append(L)
    heights = []
    for view, T in zip(views, levelled, strict=True):
        depth = view.depth.astype(np.float64)
        points = backproject(depth, view.K)
        computed, ok = _normals(points, depth > 0, 3)
        up_facing = (computed[ok] @ T[:3, :3].T)[:, 2] > 0.9
        heights.append((points[ok] @ T[:3, :3].T + T[:3, 3])[up_facing, 2])
    heights = np.concatenate(heights)
    if len(heights) > 500:
        histogram, edges = np.histogram(heights, bins=max(10, int(np.ptp(heights) / 0.03)))
        strong = np.flatnonzero(histogram >= 0.25 * histogram.max())
        floor = float((edges[strong[0]] + edges[strong[0] + 1]) / 2)
    else:
        floor = float(min(T[2, 3] for T in levelled)) - 1.40
    for T in levelled:
        T[2, 3] -= floor
    return levelled, floor


def video_capture(path: Path, model, rate: float = RATE) -> Capture:
    """A capture of posed metric depth frames for a walkthrough clip.

    `model` is a `DepthModel`. Raises RuntimeError when the camera cannot be followed.
    """
    from floorplan.frontend.video import find_video

    path = find_video(path)
    frames, times = sample_clip(path, rate)
    sfm = structure_from_motion(frames)
    registered = {int(k): v for k, v in sfm["registered"].items()}
    if len(registered) < MIN_REGISTERED:
        raise RuntimeError(
            f"could not follow the camera through the clip: only {len(registered)} of "
            f"{len(frames)} frames could be placed. Walk more slowly and keep walls, furniture "
            "and the floor in view."
        )
    order = sorted(registered)
    chosen = order[::DEPTH_EVERY]
    fov_x = float(np.degrees(2 * np.arctan(sfm["width"] / (2 * sfm["focal"]))))

    views, poses, ratios = [], [], []
    for k in chosen:
        entry = registered[k]
        view = model.predict(frames[k], fov_x, name=f"{path.stem}_{k:05d}", source=path)
        R, t = np.array(entry["R"]), np.array(entry["t"])
        T = np.eye(4)
        T[:3, :3] = R.T
        T[:3, 3] = -R.T @ t
        # depth model against COLMAP: depth of COLMAP's points in this frame
        uv, xyz = np.array(entry["uv"]).reshape(-1, 2), np.array(entry["xyz"]).reshape(-1, 3)
        ratio = np.nan
        if len(uv) >= 20:
            z = (xyz @ R.T + t)[:, 2]
            scale = view.depth.shape[1] / sfm["width"]
            cols = np.clip(np.round(uv[:, 0] * scale).astype(int), 0, view.depth.shape[1] - 1)
            rows = np.clip(np.round(uv[:, 1] * scale).astype(int), 0, view.depth.shape[0] - 1)
            predicted = view.depth[rows, cols]
            good = (predicted > 0) & (z > 0)
            if good.sum() >= 20:
                ratio = float(np.median(predicted[good] / z[good]))
        views.append(view)
        poses.append(T)
        ratios.append(ratio)
    ratios = np.array(ratios)
    usable = np.isfinite(ratios)
    if usable.sum() < 5:
        raise RuntimeError("too few frames see enough of the reconstruction to set its scale")
    metres_per_unit = float(np.median(ratios[usable]))
    spread = float(np.median(np.abs(ratios[usable] / metres_per_unit - 1.0)) * 1.4826)

    # every frame in metres, its depth rescaled to agree with the reconstruction
    depths = []
    for view, T, ratio in zip(views, poses, ratios, strict=True):
        T[:3, 3] *= metres_per_unit
        factor = (
            1.0 if not np.isfinite(ratio) else float(np.clip(metres_per_unit / ratio, 0.8, 1.25))
        )
        depths.append((view.depth * factor).astype(np.float32))
        view.depth = depths[-1]
    levelled, _ = _level(views, poses)

    names = [view.name for view in views]
    frame_list = [
        Frame(index=i, timestamp=float(times[k]), K=view.K, T_world_cam=levelled[i], name=names[i])
        for i, (k, view) in enumerate(zip(chosen, views, strict=True))
    ]
    # the scale of the whole clip: the depth model's own bias dominates; the frame-to-frame
    # spread, averaged over the frames, adds a little
    scale_sigma = float(np.hypot(VIDEO_SCALE_SIGMA, spread / np.sqrt(usable.sum())))
    capture = Capture(
        tier="video",
        source=path,
        frames=frame_list,
        depth_loader=lambda i: depths[i],
        depth_sigma_a=0.01,
        depth_sigma_b=0.01,
        scale_sigma=scale_sigma,
        notes={
            "frames_sampled": len(frames),
            "frames_placed": len(registered),
            "reconstructions": sfm["models"],
            "frames_with_depth": len(views),
            "clip_seconds": round(times[-1], 1),
            "metres_per_unit": round(metres_per_unit, 5),
            "frame_scale_spread": round(spread, 4),
            "field_of_view_deg": round(fov_x, 2),
        },
        images={view.name: image_loader(view, depths[i]) for i, view in enumerate(views)},
    )
    return capture
