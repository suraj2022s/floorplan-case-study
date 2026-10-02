"""Find things in an image from a short text description of each.

The detector is OWLv2 (Google, Apache-2.0), an open-vocabulary object detector: it is given
phrases such as "water stain" or "mirror" and returns boxes in the image with a score. No
training was done for this project. It is used for two jobs:

* damage: stains, cracks, mould, peeling paint, holes;
* things that confuse geometry: mirrors and televisions (which look like openings to a
  depth sensor), and doors and windows that geometry alone cannot see (a closed door, a
  window whose glass sits flush with the wall).

Weights are fetched by `scripts/fetch_weights.py`. Results are cached by image hash, so a
rerun replays the same detections.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
WEIGHTS = "owlv2-base-patch16-ensemble"


@dataclass(frozen=True)
class Detection:
    label: str  # the phrase that matched
    score: float
    box: tuple[float, float, float, float]  # x0, y0, x1, y1 in pixels of the image given


class Detector:
    def __init__(
        self,
        device: str | None = None,
        weights_dir: Path | None = None,
        cache_dir: Path | None = None,
    ) -> None:
        self.folder = Path(weights_dir or ROOT / "weights") / WEIGHTS
        self.cache_dir = Path(cache_dir or ROOT / ".cache" / "detect")
        self.device = device or os.environ.get("FLOORPLAN_DEVICE")
        self._model = None
        self._processor = None

    @property
    def available(self) -> bool:
        return (self.folder / "model.safetensors").is_file()

    def describe(self) -> dict:
        return {"model": "OWLv2 base patch16 ensemble", "device": self.device}

    def _load(self):
        if self._model is None:
            import torch
            from transformers import Owlv2ForObjectDetection, Owlv2Processor

            if not self.available:
                raise FileNotFoundError(
                    f"{self.folder} is missing. Run: python scripts/fetch_weights.py {WEIGHTS}"
                )
            if self.device is None:
                usable = torch.cuda.is_available() and torch.cuda.mem_get_info()[0] > 1.5 * 2**30
                self.device = "cuda" if usable else "cpu"
            self._processor = Owlv2Processor.from_pretrained(str(self.folder))
            self._model = Owlv2ForObjectDetection.from_pretrained(str(self.folder))
            self._model = self._model.to(self.device).eval()
        return self._model, self._processor

    def release(self) -> None:
        """Free the model (the laptop GPU cannot hold this and the depth model at once)."""
        if self._model is not None:
            import torch

            self._model = self._processor = None
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

    def detect(
        self, image: np.ndarray, phrases: list[str], threshold: float = 0.15
    ) -> list[Detection]:
        """Boxes for every phrase found in an RGB image, best first."""
        digest = hashlib.sha256()
        digest.update(np.ascontiguousarray(image).tobytes())
        digest.update(repr((image.shape, phrases, threshold)).encode())
        cached = self.cache_dir / f"{digest.hexdigest()[:32]}.json"
        if cached.is_file():
            return [
                Detection(d["label"], d["score"], tuple(d["box"]))
                for d in json.loads(cached.read_text())
            ]

        import torch

        model, processor = self._load()
        image = np.array(image)  # a writable copy; images loaded from files can be read-only
        height, width = image.shape[:2]
        inputs = processor(text=[phrases], images=image, return_tensors="pt").to(self.device)
        with torch.inference_mode():
            outputs = model(**inputs)
        # the processor pads the image to a square before resizing, so boxes come back in
        # the padded square's coordinates
        side = max(height, width)
        results = processor.post_process_grounded_object_detection(
            outputs, threshold=threshold, target_sizes=[(side, side)]
        )[0]
        found = []
        for score, label, box in zip(
            results["scores"].tolist(),
            results["labels"].tolist(),
            results["boxes"].tolist(),
            strict=True,
        ):
            x0, y0, x1, y1 = box
            x0, x1 = max(0.0, x0), min(float(width), x1)
            y0, y1 = max(0.0, y0), min(float(height), y1)
            if x1 - x0 < 2 or y1 - y0 < 2:
                continue
            found.append(Detection(phrases[int(label)], float(score), (x0, y0, x1, y1)))
        found.sort(key=lambda d: -d.score)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        cached.write_text(json.dumps([d.__dict__ for d in found]))
        return found
