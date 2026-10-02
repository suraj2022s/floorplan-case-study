"""Camera poses and metric depth for a set of images, in one pass.

The photo and video tiers have images but no poses. MapAnything (Meta; the Apache-2.0
checkpoint is used) takes a set of images of one scene and returns, for each, a metric depth
map, the camera intrinsics and the camera pose, all in one shared frame. Recovering poses
from walls alone was tried first and did not survive a real cluttered room; a model trained
on a great many scenes handles furniture, close-ups and bare walls where that could not.

What the model does not give: which way is up (its frame is the first camera's), and any
guarantee about metric scale beyond its own prediction. Up is recovered from the surfaces
afterwards (`level_views`), and the scale uncertainty is carried into every interval.

Weights are fetched by `scripts/fetch_weights.py`. Results are cached by the hash of the
whole image set, so a rerun replays the same numbers.
"""

from __future__ import annotations

import hashlib
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from floorplan.frontend.views import View, estimate_up
from floorplan.geometry.cloud import _normals, backproject

ROOT = Path(__file__).resolve().parents[3]
WEIGHTS = "map-anything-apache"


@dataclass
class PosedView:
    view: View
    T_world_cam: np.ndarray  # 4x4, camera (x right, y down, z forward) to the set's frame
    confidence: np.ndarray | None = None


class MultiViewModel:
    def __init__(self, device: str | None = None, weights_dir: Path | None = None,
                 cache_dir: Path | None = None, long_side: int = 1024) -> None:
        self.folder = Path(weights_dir or ROOT / "weights") / WEIGHTS
        self.cache_dir = Path(cache_dir or ROOT / ".cache" / "multiview")
        self.device = device or os.environ.get("FLOORPLAN_MULTIVIEW_DEVICE")
        self.long_side = long_side
        self._model = None

    @property
    def available(self) -> bool:
        return (self.folder / "model.safetensors").is_file()

    def describe(self) -> dict:
        return {"model": "MapAnything (Apache-2.0 checkpoint)", "device": self.device}

    def _load(self):
        if self._model is None:
            import torch
            from mapanything.models import MapAnything

            if not self.available:
                raise FileNotFoundError(
                    f"{self.folder} is missing. Run: python scripts/fetch_weights.py {WEIGHTS}"
                )
            if self.device is None:
                # the checkpoint is 4.9 GB in single precision: it needs a GPU with clearly
                # more memory than that, otherwise it runs on the CPU
                roomy = torch.cuda.is_available() and torch.cuda.mem_get_info()[1] > 10 * 2**30
                self.device = "cuda" if roomy else "cpu"
            self._model = MapAnything.from_pretrained(str(self.folder)).to(self.device).eval()
        return self._model

    def release(self) -> None:
        if self._model is not None:
            import torch

            self._model = None
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

    def reconstruct(self, images: list[np.ndarray], names: list[str],
                    sources: list[Path | None] | None = None) -> list[PosedView]:
        """Posed metric depth views for RGB images of one scene."""
        sources = sources or [None] * len(images)
        digest = hashlib.sha256()
        for image in images:
            digest.update(np.ascontiguousarray(image).tobytes())
            digest.update(repr(image.shape).encode())
        digest.update(repr((WEIGHTS, self.long_side)).encode())
        cached = self.cache_dir / f"{digest.hexdigest()[:32]}.npz"
        if cached.is_file():
            data = np.load(cached)
            return [
                PosedView(
                    View(name=names[k], depth=data[f"depth_{k}"], K=data[f"K_{k}"],
                         image=data[f"image_{k}"], source=sources[k],
                         detail=data[f"detail_{k}"]),
                    data[f"pose_{k}"],
                    data[f"confidence_{k}"],
                )
                for k in range(len(images))
            ]

        import torch
        from mapanything.utils.image import load_images

        model = self._load()
        with tempfile.TemporaryDirectory() as folder:
            paths = []
            for k, image in enumerate(images):
                height, width = image.shape[:2]
                scale = min(1.0, self.long_side / max(height, width))
                if scale < 1.0:
                    image = cv2.resize(image, (round(width * scale), round(height * scale)),
                                       interpolation=cv2.INTER_AREA)
                path = Path(folder) / f"{k:04d}.png"
                cv2.imwrite(str(path), cv2.cvtColor(image, cv2.COLOR_RGB2BGR))
                paths.append(str(path))
            views = load_images(paths)
        with torch.inference_mode():
            predictions = model.infer(
                views, memory_efficient_inference=True, minibatch_size=1,
                use_amp=self.device == "cuda", amp_dtype="bf16", apply_mask=True,
                mask_edges=True,
            )

        results, store = [], {}
        for k, prediction in enumerate(predictions):
            depth = prediction["depth_z"][0].float().cpu().numpy().squeeze()
            mask = prediction["mask"][0].cpu().numpy().squeeze().astype(bool)
            K = prediction["intrinsics"][0].float().cpu().numpy()
            pose = prediction["camera_poses"][0].float().cpu().numpy().astype(np.float64)
            confidence = prediction["conf"][0].float().cpu().numpy().squeeze()
            picture = (prediction["img_no_norm"][0].float().cpu().numpy() * 255).clip(0, 255)
            picture = picture.astype(np.uint8)
            depth = np.where(mask & np.isfinite(depth) & (depth > 0) & (depth < 30), depth, 0.0)
            _, detail = cv2.imencode(".jpg", cv2.cvtColor(picture, cv2.COLOR_RGB2BGR),
                                     [cv2.IMWRITE_JPEG_QUALITY, 90])
            view = View(name=names[k], depth=depth.astype(np.float32), K=K.astype(np.float64),
                        image=picture, source=sources[k], detail=detail)
            results.append(PosedView(view, pose, confidence))
            store.update({f"depth_{k}": view.depth, f"K_{k}": view.K, f"image_{k}": picture,
                          f"pose_{k}": pose, f"confidence_{k}": confidence,
                          f"detail_{k}": detail})
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(cached, **store)
        return results


def level_views(posed: list[PosedView]) -> tuple[list[np.ndarray], float]:
    """Turn the set's frame so that z is up and the floor is at z = 0.

    Returns the levelled camera-to-world pose of every view and the floor height that was
    subtracted (None-safe: 0 when no floor is visible, in which case the lowest camera is
    assumed to be 1.4 m above it).
    """
    normals, ups = [], []
    for item in posed:
        depth = item.view.depth.astype(np.float64)
        points = backproject(depth, item.view.K)
        computed, ok = _normals(points, depth > 0, 3)
        R = item.T_world_cam[:3, :3]
        picked = computed[ok][:: max(1, int(ok.sum()) // 15000)]
        normals.append(picked @ R.T)
        ups.append(-R[:, 1])  # the top of each picture, in the set's frame
    up = estimate_up(np.concatenate(normals), initial=np.mean(ups, axis=0))

    # any horizontal direction will do for x; take the first camera's viewing direction
    forward = posed[0].T_world_cam[:3, 2] - (posed[0].T_world_cam[:3, 2] @ up) * up
    forward /= np.linalg.norm(forward)
    R_level = np.stack([forward, np.cross(up, forward), up])
    levelled = []
    for item in posed:
        T = np.eye(4)
        T[:3, :3] = R_level @ item.T_world_cam[:3, :3]
        T[:3, 3] = R_level @ item.T_world_cam[:3, 3]
        levelled.append(T)

    # floor: the lowest strong layer of upward-facing points
    heights = []
    for item, T in zip(posed, levelled, strict=True):
        depth = item.view.depth.astype(np.float64)
        points = backproject(depth, item.view.K)
        computed, ok = _normals(points, depth > 0, 3)
        world_normals = computed[ok] @ T[:3, :3].T
        world_points = points[ok] @ T[:3, :3].T + T[:3, 3]
        heights.append(world_points[world_normals[:, 2] > 0.9, 2])
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
