"""Head-to-head: our LiDAR tier against a consumer scanning app, dimension by dimension.

    python bench/headtohead.py bench/headtohead/<site>.yaml reports/bench/<name>/gates.json \
        --capture <benchmark capture id> [--out reports/headtohead/<site>.md]

The app's numbers are copied by hand from its export into the YAML file (the export itself is
kept next to it as evidence: apps export PDF floor plans, and a hand transcription that can be
checked against the PDF is more reliable than parsing it). Our numbers and the ground truth
come from the benchmark run of the same rooms. A dimension counts when both sides measured
it. "Beat or tie" means our error is no larger than the app's plus 5 mm, the resolution an app
reports to; the brief's bar is 70% of shared dimensions.

    app: Polycam
    version: "3.6.1"
    mode: "LiDAR room mode, free tier"
    exports: [polycam/living.pdf, polycam/bedroom.pdf]
    rooms:
      living:                       # room ids as in the ground truth
        walls: {W1: 4.215, W2: 3.360, W3: 4.205, W4: 3.355}
        ceiling_height: 2.71        # leave out what the app does not report
        openings: {D1: 0.81, WIN1: 1.19}
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

TIE = 0.005  # metres


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("app", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument("--capture", required=True)
    parser.add_argument("--out", type=Path)
    arguments = parser.parse_args()

    app = yaml.safe_load(arguments.app.read_text())
    report = json.loads(arguments.report.read_text())
    capture = next((c for c in report["captures"] if c["capture"] == arguments.capture), None)
    if capture is None:
        raise SystemExit(f"capture {arguments.capture!r} not in {arguments.report}")
    ours = {row["id"]: row for row in capture["rows"]}

    lines = [
        f"# Head-to-head: our LiDAR tier against {app['app']} {app['version']}",
        "",
        f"App mode: {app.get('mode', '')}. App exports: "
        + ", ".join(f"`{e}`" for e in app.get("exports", [])),
        f"Our run: capture `{arguments.capture}` of benchmark `{report['benchmark']}`. "
        f"A tie is within {TIE * 1000:.0f} mm.",
        "",
        "| Dimension | Truth (m) | Ours (m) | Our error (cm) | App (m) | App error (cm) | Result |",
        "|---|---|---|---|---|---|---|",
    ]
    results = []
    for room, measured in app["rooms"].items():
        items = [(f"{room}-{wall}", value) for wall, value in (measured.get("walls") or {}).items()]
        if measured.get("ceiling_height") is not None:
            items.append((room, measured["ceiling_height"]))
        items += [(f"{room}-{o}", v) for o, v in (measured.get("openings") or {}).items()]
        for identifier, app_value in items:
            kind = "ceiling" if identifier == room else ""
            row = next(
                (
                    r
                    for r in capture["rows"]
                    if r["id"] == identifier
                    and (kind != "ceiling" or r["kind"] == "ceiling_height")
                ),
                None,
            )
            if row is None or row.get("value") is None:
                lines.append(
                    f"| {identifier} | | not measured | | {app_value:.3f} | | not shared |"
                )
                continue
            our_error = row["value"] - row["truth"]
            app_error = float(app_value) - row["truth"]
            beat = abs(our_error) <= abs(app_error) + TIE
            results.append(beat)
            outcome = "beat or tie" if beat else "lose"
            label = identifier if kind != "ceiling" else f"{room} ceiling"
            lines.append(
                f"| {label} | {row['truth']:.3f} | {row['value']:.3f} | {our_error * 100:+.1f} "
                f"| {float(app_value):.3f} | {app_error * 100:+.1f} | {outcome} |"
            )
    share = sum(results) / len(results) if results else 0.0
    lines += [
        "",
        f"**Beat or tie on {sum(results)} of {len(results)} shared dimensions = {share:.0%}** "
        f"(the brief's bar: 70%, {'met' if share >= 0.7 else 'not met'}).",
    ]
    text = "\n".join(lines) + "\n"
    print(text)
    if arguments.out:
        arguments.out.parent.mkdir(parents=True, exist_ok=True)
        arguments.out.write_text(text)
    del ours
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
