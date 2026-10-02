"""Metric depth from a single image, with a cache.

The photo and video tiers have no depth sensor, so depth comes from a learned model:
MoGe-2 (Microsoft, MIT licence), which predicts a metric point map, surface normals and the
camera's field of view from one RGB image. The weights are fetched by
`scripts/fetch_weights.py`; nothing is downloaded at run time.

Two things here matter for accuracy and for reproducibility:

* the field of view is taken from the photo's EXIF data when it is there (the "35 mm
  equivalent" focal length an iPhone writes), instead of being guessed by the model. A
  wrong field of view stretches or squeezes the room;
* every prediction is cached under a key made of the image bytes and the model settings, so
  a second run on the same files replays the same numbers exactly. A graphics card does not
  always produce bit-identical results twice; the cache is what makes reruns identical.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import cv2
import numpy as np

from floorplan.frontend.views import View

ROOT = Path(__file__).resolve().parents[3]
VARIANTS = {"vitl": "moge-2-vitl-normal.pt", "vitb": "moge-2-vitb-normal.pt"}
FULL_FRAME_DIAGONAL = 43.2666  # millimetres, the reference for "35 mm equivalent"


def load_image(path: Path) -> tuple[np.ndarray, float | None]:
    """An upright RGB image and its horizontal field of view in degrees, if EXIF gives it."""
    from PIL import Image, ImageOps

    if path.suffix.lower() in (".heic", ".heif"):
        import pillow_heif

        pillow_heif.register_heif_opener()
    with Image.open(path) as handle:
        focal_35 = None
        try:
            focal_35 = handle.getexif().get_ifd(0x8769).get(0xA405)
        except Exception:  # EXIF is optional; a missing or broken block is not an error
            focal_35 = None
        image = np.asarray(ImageOps.exif_transpose(handle).convert("RGB"))
    fov_x = None
    if focal_35:
        height, width = image.shape[:2]
        focal_pixels = float(focal_35) / FULL_FRAME_DIAGONAL * float(np.hypot(width, height))
        fov_x = float(np.degrees(2 * np.arctan(width / (2 * focal_pixels))))
    return image, fov_x


class DepthModel:
    """Loads MoGe-2 once and turns images into `View`s."""

    def __init__(
        self,
        variant: str | None = None,
        device: str | None = None,
        weights_dir: Path | None = None,
        cache_dir: Path | None = None,
        infer_long_side: int = 1024,
        view_long_side: int = 512,
    ) -> None:
        self.weights_dir = Path(weights_dir or ROOT / "weights")
        self.cache_dir = Path(cache_dir or ROOT / ".cache" / "depth")
        self.infer_long_side = infer_long_side
        self.view_long_side = view_long_side
        self.device = device or os.environ.get("FLOORPLAN_DEVICE")
        self.variant = variant or os.environ.get("FLOORPLAN_DEPTH_MODEL")
        self._model = None

    # ---------------------------------------------------------------- model

    def _load(self):
        if self._model is not None:
            return self._model
        import torch
        from moge.model.v2 import MoGeModel

        if self.device is None:
            usable = torch.cuda.is_available() and torch.cuda.mem_get_info()[0] > 2.5 * 2**30
            self.device = "cuda" if usable else "cpu"
        if self.variant is None:
            # the large model on a GPU; the small one on a CPU, where the large one is slow
            self.variant = "vitl" if self.device == "cuda" else "vitb"
        weights = self.weights_dir / VARIANTS[self.variant]
        if not weights.is_file():
            raise FileNotFoundError(
                f"{weights} is missing. Run: python scripts/fetch_weights.py "
                f"{VARIANTS[self.variant].removesuffix('.pt')}"
            )
        self._model = MoGeModel.from_pretrained(str(weights)).to(self.device).eval()
        return self._model

    def describe(self) -> dict:
        return {
            "model": "MoGe-2",
            "variant": self.variant,
            "device": self.device,
            "infer_long_side": self.infer_long_side,
        }

    # ---------------------------------------------------------------- inference

    def _key(self, image: np.ndarray, fov_x: float | None) -> str:
        digest = hashlib.sha256()
        digest.update(np.ascontiguousarray(image).tobytes())
        digest.update(
            repr(
                (
                    image.shape,
                    None if fov_x is None else round(fov_x, 3),
                    self.variant or "auto",
                    self.infer_long_side,
                    self.view_long_side,
                )
            ).encode()
        )
        return digest.hexdigest()[:32]

    def predict(
        self,
        image: np.ndarray,
        fov_x: float | None = None,
        name: str = "image",
        source: Path | None = None,
    ) -> View:
        """A `View` (metric depth, intrinsics, normals) for an upright RGB image."""
        if self.variant is None and self._model is None:
            self._choose_without_loading()
        cached = self.cache_dir / f"{self._key(image, fov_x)}.npz"
        if cached.is_file():
            data = np.load(cached)
            return View(
                name=name,
                depth=data["depth"],
                K=data["K"],
                image=data["image"],
                normal=data["normal"].astype(np.float32),
                source=source,
            )

        import torch

        model = self._load()
        height, width = image.shape[:2]
        scale = self.infer_long_side / max(height, width)
        small = (
            cv2.resize(
                image, (round(width * scale), round(height * scale)), interpolation=cv2.INTER_AREA
            )
            if scale < 1
            else image
        )
        tensor = torch.tensor(small / 255.0, dtype=torch.float32, device=self.device)
        with torch.inference_mode():
            output = model.infer(
                tensor.permute(2, 0, 1), fov_x=fov_x, use_fp16=self.device == "cuda"
            )
        depth = output["depth"].float().cpu().numpy()
        mask = output["mask"].cpu().numpy().astype(bool)
        normal = (
            output["normal"].float().cpu().numpy() if output.get("normal") is not None else None
        )
        intrinsics = output["intrinsics"].float().cpu().numpy()  # normalised by image size
        depth = np.where(mask & np.isfinite(depth) & (depth > 0) & (depth < 30), depth, 0.0)

        # hand a smaller map to the geometry code; nearest-neighbour keeps depth edges sharp
        h, w = depth.shape
        factor = self.view_long_side / max(h, w)
        out_w, out_h = round(w * factor), round(h * factor)
        depth_small = cv2.resize(depth, (out_w, out_h), interpolation=cv2.INTER_NEAREST)
        image_small = cv2.resize(small, (out_w, out_h), interpolation=cv2.INTER_AREA)
        if normal is not None:
            normal_small = cv2.resize(normal, (out_w, out_h), interpolation=cv2.INTER_NEAREST)
        else:
            normal_small = np.zeros((out_h, out_w, 3), np.float32)
        K = np.array(
            [
                [intrinsics[0, 0] * out_w, 0.0, intrinsics[0, 2] * out_w - 0.5],
                [0.0, intrinsics[1, 1] * out_h, intrinsics[1, 2] * out_h - 0.5],
                [0.0, 0.0, 1.0],
            ]
        )
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            cached,
            depth=depth_small.astype(np.float32),
            K=K,
            image=image_small,
            normal=normal_small.astype(np.float16),
        )
        return View(
            name=name,
            depth=depth_small.astype(np.float32),
            K=K,
            image=image_small,
            normal=normal_small.astype(np.float32),
            source=source,
        )

    def _choose_without_loading(self) -> None:
        """Fix the variant before computing a cache key, without loading weights."""
        import torch

        if self.device is None:
            usable = torch.cuda.is_available() and torch.cuda.mem_get_info()[0] > 2.5 * 2**30
            self.device = "cuda" if usable else "cpu"
        self.variant = "vitl" if self.device == "cuda" else "vitb"

    def view(self, path: Path) -> View:
        """A `View` for an image file (HEIC, JPEG or PNG)."""
        path = Path(path)
        image, fov_x = load_image(path)
        return self.predict(image, fov_x, name=path.stem, source=path)
