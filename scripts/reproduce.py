"""Regenerate every reported number from raw inputs, in one command.

    uv run python scripts/reproduce.py            # fetch what is missing, test, run benchmarks
    uv run python scripts/reproduce.py --laser    # also re-read the ground truth off the laser scan

Steps, each skipped when its input is already present and verified:

1. model weights (scripts/fetch_weights.py) and real sample files (scripts/fetch_samples.py);
2. the public-data benchmark's captures and the bedroom's video (scripts/fetch_arkitscenes.py);
3. the test suite;
4. both benchmarks, each capture run through the public command in its own process
   (reports/bench/synthetic, reports/bench/arkitscenes);
5. with --laser: the 1.9 GB laser scan, and the bedroom's ground truth read off it again,
   compared with the committed file;
6. the calibration report on the real benchmark (nothing written).

Depth-model and COLMAP results are cached by input content and method, so a second run
replays them; deleting .cache/ runs everything live.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def step(title: str, command: list[str]) -> None:
    print(f"\n== {title}\n   {' '.join(command)}", flush=True)
    completed = subprocess.run(command, cwd=ROOT)
    if completed.returncode != 0:
        raise SystemExit(f"step failed: {title}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--laser", action="store_true")
    arguments = parser.parse_args()
    python = sys.executable
    step(
        "model weights",
        [python, "scripts/fetch_weights.py", "moge-2-vitl-normal", "owlv2-base-patch16-ensemble"],
    )
    step("real sample files", [python, "scripts/fetch_samples.py"])
    step(
        "public-data benchmark captures",
        [python, "scripts/fetch_arkitscenes.py", "--video"]
        + (["--laser"] if arguments.laser else []),
    )
    step("tests", [python, "-m", "pytest", "tests", "-q"])
    step("synthetic benchmark", [python, "bench/run_bench.py", "bench/benchmarks/synthetic.yaml"])
    step(
        "public-data benchmark", [python, "bench/run_bench.py", "bench/benchmarks/arkitscenes.yaml"]
    )
    if arguments.laser:
        step(
            "ground truth from the laser scan",
            [
                python,
                "bench/public/laser_truth.py",
                ".cache/arkitscenes/laser/467138/190170.ply",
                "--site",
                "arkitscenes-467138",
                "--out",
                ".cache/bench/arkitscenes/truth_regenerated.yaml",
            ],
        )
        print("   compare with bench/ground_truth/arkitscenes-467138.yaml (walls, ceiling)")
    step(
        "calibration report", [python, "bench/calibrate.py", "reports/bench/arkitscenes/gates.json"]
    )
    print("\nReports: reports/bench/synthetic/gates.md, reports/bench/arkitscenes/gates.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
