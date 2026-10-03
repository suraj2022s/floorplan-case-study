"""Fit interval calibration factors from benchmark results, and check them on held-out rooms.

    python bench/calibrate.py reports/bench/<name>/gates.json [...]          # report only
    python bench/calibrate.py reports/bench/<name>/gates.json --write        # also save them

A 90% interval is calibrated when it contains the truth 90% of the time. For each tier and
measurement type this finds the factor f that makes it so on the benchmark: with each
interval's 1-sigma s = (hi - lo) / (2 * 1.6449), it is the 90th percentile of |error| / s,
divided by 1.6449. f > 1 widens the intervals, f < 1 narrows them.

Fitting and checking on the same rooms only proves the arithmetic. So each room (each site,
or each group of repeat captures) is left out in turn: the factor is fitted on the others and
the coverage counted on the room left out. That held-out coverage is what the report quotes.

Factors are never allowed below 0.75 (too few points to narrow intervals with confidence),
and a type with fewer than 4 points keeps its factor of 1.0. `--write` saves the factors
fitted on all rooms to configs/calibration/<tier>.json, with where they came from; the
pipeline multiplies every sigma of that type by them from then on.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import date
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
Z90 = 1.6449
MIN_POINTS = 4
MIN_FACTOR = 0.75


def load_rows(paths: list[Path], include_synthetic: bool = False) -> list[dict]:
    rows = []
    for path in paths:
        data = json.loads(Path(path).read_text())
        if "synthetic" in data["benchmark"] and not include_synthetic:
            # synthetic scenes have exact depth and no clutter: their errors say nothing
            # about a real sensor, and fitting on them would narrow real intervals
            print(f"skipped {path}: synthetic results do not calibrate a real sensor")
            continue
        for capture in data["captures"]:
            room = capture.get("group") or capture.get("site") or capture["capture"]
            for row in capture["rows"]:
                if row.get("value") is None or row.get("lo") is None:
                    continue
                sigma = (row["hi"] - row["lo"]) / (2 * Z90)
                if sigma <= 0:
                    continue
                rows.append({**row, "room": f"{data['benchmark']}:{room}", "sigma": sigma})
    return rows


def factor(rows: list[dict]) -> float:
    if len(rows) < MIN_POINTS:
        return 1.0
    z = np.array([abs(row["value"] - row["truth"]) / row["sigma"] for row in rows])
    return max(MIN_FACTOR, float(np.percentile(z, 90)) / Z90)


def covered(rows: list[dict], f: float) -> list[bool]:
    return [abs(row["value"] - row["truth"]) <= Z90 * f * row["sigma"] for row in rows]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("reports", nargs="+", type=Path)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--include-synthetic", action="store_true")
    arguments = parser.parse_args()
    rows = load_rows(arguments.reports, arguments.include_synthetic)
    by_type: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in rows:
        by_type[(row["tier"], row["kind"])].append(row)

    fitted: dict[str, dict[str, float]] = defaultdict(dict)
    print(
        "| Tier | Measurement | Points | Rooms | Coverage now | Factor (all rooms) "
        "| Coverage, room left out |"
    )
    print("|---|---|---|---|---|---|---|")
    for (tier, kind), items in sorted(by_type.items()):
        rooms = sorted({row["room"] for row in items})
        now = sum(covered(items, 1.0)) / len(items)
        f_all = factor(items)
        held = []
        for room in rooms:
            train = [row for row in items if row["room"] != room]
            test = [row for row in items if row["room"] == room]
            held += covered(test, factor(train)) if len(rooms) > 1 else []
        held_text = f"{sum(held)}/{len(held)}" if held else "one room only: not checkable"
        print(
            f"| {tier} | {kind} | {len(items)} | {len(rooms)} | {now:.0%} | {f_all:.2f} "
            f"| {held_text} |"
        )
        fitted[tier][kind] = round(f_all, 3)

    if arguments.write:
        directory = ROOT / "configs" / "calibration"
        directory.mkdir(parents=True, exist_ok=True)
        for tier, factors in fitted.items():
            path = directory / f"{tier}.json"
            path.write_text(
                json.dumps(
                    {
                        "factors": factors,
                        "fitted_on": [str(p) for p in arguments.reports],
                        "date": date.today().isoformat(),
                        "rule": "90th percentile of |error| / sigma, divided by 1.6449; "
                        f"floor 0.75; types with fewer than {MIN_POINTS} points keep 1.0",
                    },
                    indent=2,
                )
                + "\n"
            )
            print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
