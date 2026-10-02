"""Error budget: how sure each reported number is.

Every measurement is reported as a value with a 90% interval. The interval is built from
named, independent error sources added in quadrature:

    sigma^2 = sigma_fit^2 + sigma_plane^2 + (scale_sigma * length)^2 + sigma_definition^2

* fit         scatter of the points behind the estimate; shrinks with more points;
* plane       systematic error in where a fitted surface sits (sensor range bias, residual
              pose error); does not shrink with more points;
* scale       error in the metric scale of the whole capture, proportional to length. This
              is small for LiDAR and large for photos, and it is the reason intervals widen
              as the sensor data thins;
* definition  ambiguity in what is being measured (where exactly a wall face or a jamb is).

A wall that was never seen has no fit at all; its position is carried with a wide prior.

The raw sigma is then multiplied by a per-tier factor learned from benchmark captures
(`configs/calibration/<tier>.json`) so that 90% intervals really contain the truth 90% of
the time. Until a tier has been calibrated the factor is 1.0 and the output says so.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

Z90 = 1.6449  # two-sided 90% for a normal distribution
OBSERVED_SHARE = 0.30  # a wall seen over less of its length than this is treated as inferred


@dataclass(frozen=True)
class TierBudget:
    plane_sigma: float  # metres, systematic 1-sigma on one fitted surface
    inferred_sigma: float  # metres, 1-sigma on the position of a wall that was not seen
    definition_sigma: float  # metres


# Starting values. The LiDAR numbers are replaced by measured ones once a device has been
# characterised against a laser; photo and video numbers come from the benchmark.
BUDGETS = {
    "lidar": TierBudget(plane_sigma=0.004, inferred_sigma=0.15, definition_sigma=0.002),
    "video": TierBudget(plane_sigma=0.012, inferred_sigma=0.25, definition_sigma=0.003),
    "photo": TierBudget(plane_sigma=0.025, inferred_sigma=0.40, definition_sigma=0.005),
}


@dataclass(frozen=True)
class Measurement:
    value: float
    sigma: float  # calibrated 1-sigma
    basis: str = "observed"  # "observed" | "inferred"
    unit: str = "m"
    coverage: float = 0.90

    @property
    def lo(self) -> float:
        return self.value - Z90 * self.sigma

    @property
    def hi(self) -> float:
        return self.value + Z90 * self.sigma

    @property
    def available(self) -> bool:
        return bool(np.isfinite(self.value))

    def to_dict(self, digits: int = 4) -> dict:
        if not self.available:  # e.g. ceiling height when no ceiling was captured
            return {
                "value": None,
                "lo": None,
                "hi": None,
                "coverage": self.coverage,
                "sigma": None,
                "unit": self.unit,
                "basis": "not_measured",
            }
        return {
            "value": round(self.value, digits),
            "lo": round(self.lo, digits),
            "hi": round(self.hi, digits),
            "coverage": self.coverage,
            "sigma": round(self.sigma, digits + 1),
            "unit": self.unit,
            "basis": self.basis,
        }


@dataclass(frozen=True)
class Calibration:
    """Per-measurement-type factors that turn raw sigmas into calibrated ones."""

    factors: dict[str, float]
    calibrated: bool
    source: str

    def factor(self, kind: str) -> float:
        return float(self.factors.get(kind, self.factors.get("pooled", 1.0)))


def load_calibration(tier: str, directory: Path | None = None) -> Calibration:
    directory = directory or Path(__file__).resolve().parents[3] / "configs" / "calibration"
    file = directory / f"{tier}.json"
    if file.is_file():
        data = json.loads(file.read_text())
        return Calibration(data["factors"], True, str(file.name))
    return Calibration({}, False, "none: factors default to 1.0")


def quadrature(*sigmas: float) -> float:
    return float(np.sqrt(sum(s * s for s in sigmas)))
