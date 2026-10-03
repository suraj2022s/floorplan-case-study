"""Run a benchmark: every capture through the pipeline, then score it against ground truth.

    python bench/run_bench.py bench/benchmarks/synthetic.yaml

Each capture is run with the same public command a user would type (`floorplan run`), in a
separate process, and scored only from the files that run writes. Results go to
`reports/bench/<benchmark name>/gates.md` and `gates.json`.

Options:
    --reuse      score existing outputs instead of re-running captures that already have one
    --only ID    run and score only the named capture(s); may be repeated
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gates import CaptureScore, evaluate, score_capture  # noqa: E402
from truth import load_prediction, load_truth  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def _run_capture(capture: Path, out: Path, extra: list[str], reuse: bool) -> None:
    if reuse and (out / "plan.json").is_file():
        return
    command = [sys.executable, "-m", "floorplan.cli", "run", str(capture), "--out", str(out)]
    completed = subprocess.run(command + extra, cwd=ROOT, capture_output=True, text=True)
    if completed.returncode != 0:
        out.mkdir(parents=True, exist_ok=True)
        (out / "error.txt").write_text(completed.stdout + "\n" + completed.stderr)
        print(f"  FAILED: {capture.name} (see {out / 'error.txt'})")


def _ensure_synthetic(entry: dict, capture: Path) -> None:
    if (capture / "odometry.csv").is_file():
        return
    spec = entry["synth"]
    command = [
        sys.executable,
        "-m",
        "floorplan.cli",
        "synth",
        spec["scene"],
        str(capture),
        "--seed",
        str(spec.get("seed", 0)),
    ]
    if spec.get("drift"):
        command += ["--drift", "--drift-scale", str(spec.get("drift_scale", 1.0))]
    subprocess.run(command, cwd=ROOT, check=True, capture_output=True, text=True)


def _score(entry: dict, capture: Path, out: Path) -> CaptureScore | None:
    if not (out / "plan.json").is_file():
        return None
    truth_path = Path(entry.get("truth", "ground_truth.json"))
    truth_path = (
        truth_path
        if truth_path.is_absolute()
        else (capture / truth_path if (capture / truth_path).is_file() else ROOT / truth_path)
    )
    log = json.loads((out / "run_log.json").read_text()) if (out / "run_log.json").is_file() else {}
    return score_capture(
        entry["id"],
        load_truth(truth_path),
        load_prediction(out / "plan.json"),
        entry.get("group"),
        log,
    )


def _fmt(value: float | None, scale: float = 100.0, digits: int = 1, signed: bool = True) -> str:
    if value is None:
        return "not found"
    return f"{value * scale:+.{digits}f}" if signed else f"{value * scale:.{digits}f}"


def _markdown(
    name: str,
    description: str,
    scores: list[CaptureScore],
    gates: list[dict],
    ablation: list[dict],
    failed: list[str],
) -> str:
    lines = [f"# Benchmark report: {name}", "", description.strip(), ""]
    if failed:
        lines += ["**Captures that did not produce a plan:** " + ", ".join(failed), ""]

    lines += [
        "## Gates",
        "",
        "| Tier | Gate | Status | Result | Threshold | Notes |",
        "|---|---|---|---|---|---|",
    ]
    for gate in gates:
        lines.append(
            f"| {gate['tier']} | {gate['gate']} | **{gate['status']}** | "
            f"{gate['value']} | {gate['threshold']} | {gate['detail']} |"
        )

    lines += [
        "",
        "## Captures",
        "",
        "| Capture | Tier | Rooms found / measured | Adjacency | Overlap (m²) | Time (s) |",
        "|---|---|---|---|---|---|",
    ]
    for score in scores:
        lines.append(
            f"| {score.capture} | {score.tier} | {score.rooms_found} / {score.rooms_measured} | "
            f"{'correct' if score.adjacency_correct else 'WRONG'} | {score.overlap_area:.3f} | "
            f"{sum(score.timings.values()):.1f} |"
        )

    for kind, title, unit, scale in [
        ("wall_length", "Wall lengths", "cm", 100.0),
        ("ceiling_height", "Ceiling heights", "cm", 100.0),
        ("opening_width", "Opening widths", "cm", 100.0),
        ("floor_area", "Floor areas", "m²", 1.0),
        ("footprint_area", "Footprint", "m²", 1.0),
    ]:
        rows = [row for score in scores for row in score.rows if row.kind == kind]
        if not rows:
            continue
        lines += [
            "",
            f"## {title}",
            "",
            f"| Capture | Item | Truth (m) | Measured [90% interval] | Error ({unit}) | "
            "Truth in interval |",
            "|---|---|---|---|---|---|",
        ]
        for row in rows:
            measured = (
                "not found"
                if row.value is None
                else f"{row.value:.3f} [{row.lo:.3f}, {row.hi:.3f}]"
            )
            covered = "" if row.covered is None else ("yes" if row.covered else "NO")
            lines.append(
                f"| {row.capture} | {row.id} | {row.truth:.3f} | {measured} | "
                f"{_fmt(row.error, scale, 1 if scale == 100 else 3)} | {covered} |"
            )

    outcomes = [(score.capture, o) for score in scores for o in score.openings]
    if outcomes:
        lines += [
            "",
            "## Opening detection",
            "",
            "| Capture | Opening | Outcome | Measured kind | Found kind | Width error (cm) |",
            "|---|---|---|---|---|---|",
        ]
        for capture, o in outcomes:
            error = "" if "width_error" not in o else f"{o['width_error'] * 100:+.1f}"
            lines.append(
                f"| {capture} | {o['id']} | {o['outcome']} | {o.get('truth_kind', '')} | "
                f"{o.get('predicted_kind', '')} | {error} |"
            )

    if ablation:
        lines += [
            "",
            "## Drift ablation",
            "",
            "The same capture run with drift correction on and off.",
            "",
            "| Capture | Correction | Rooms | Walls found / measured | Footprint error | "
            "Worst wall error (cm) | Room overlap (m²) |",
            "|---|---|---|---|---|---|---|",
        ]
        for item in ablation:
            lines.append(
                f"| {item['capture']} | {item['correction']} | {item['rooms']} | "
                f"{item['walls_found']} / {item['walls_measured']} | {item['footprint_error']} | "
                f"{item['worst_wall_cm']} | {item['overlap']:.3f} |"
            )

    timed = [score for score in scores if score.timings]
    if timed:
        stages = sorted({stage for score in timed for stage in score.timings})
        lines += [
            "",
            "## Timing (seconds)",
            "",
            "| Capture | " + " | ".join(stages) + " | total |",
            "|---|" + "---|" * (len(stages) + 1),
        ]
        for score in timed:
            cells = " | ".join(f"{score.timings.get(stage, 0):.1f}" for stage in stages)
            lines.append(f"| {score.capture} | {cells} | {sum(score.timings.values()):.1f} |")
    return "\n".join(lines) + "\n"


def _ablation_row(score: CaptureScore | None, capture: str, correction: str) -> dict:
    if score is None:
        return {
            "capture": capture,
            "correction": correction,
            "rooms": "run failed",
            "walls_found": 0,
            "walls_measured": 0,
            "footprint_error": "n/a",
            "worst_wall_cm": "n/a",
            "overlap": 0.0,
        }
    walls = [row for row in score.rows if row.kind == "wall_length"]
    errors = [abs(row.error) for row in walls if row.error is not None]
    footprint = [
        row for row in score.rows if row.kind == "footprint_area" and row.error is not None
    ]
    return {
        "capture": capture,
        "correction": correction,
        "rooms": f"{score.rooms_found} / {score.rooms_measured}",
        "walls_found": len(errors),
        "walls_measured": len(walls),
        "footprint_error": f"{footprint[0].error / footprint[0].truth:+.2%}"
        if footprint
        else "n/a",
        "worst_wall_cm": f"{max(errors) * 100:.1f}" if errors else "n/a",
        "overlap": score.overlap_area,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run and score a benchmark.")
    parser.add_argument("benchmark", type=Path)
    parser.add_argument("--reuse", action="store_true")
    parser.add_argument("--only", action="append", default=[])
    parser.add_argument("--out", type=Path, default=None, help="where run outputs go")
    parser.add_argument("--report", type=Path, default=None, help="where the report goes")
    arguments = parser.parse_args()

    spec = yaml.safe_load(arguments.benchmark.read_text())
    name = spec["name"]
    runs = arguments.out or ROOT / "out" / "bench" / name
    report = arguments.report or ROOT / "reports" / "bench" / name
    entries = [e for e in spec["captures"] if not arguments.only or e["id"] in arguments.only]

    scores: list[CaptureScore] = []
    failed: list[str] = []
    for entry in entries:
        capture = ROOT / entry["path"]
        if "synth" in entry:
            _ensure_synthetic(entry, capture)
        print(f"{entry['id']}: running")
        extra = ["--tier", entry["tier"]] if entry.get("tier") else []
        _run_capture(capture, runs / entry["id"], extra, arguments.reuse)
        score = _score(entry, capture, runs / entry["id"])
        if score is None:
            failed.append(entry["id"])
        else:
            scores.append(score)

    ablation: list[dict] = []
    for capture_id in (spec.get("ablations") or {}).get("drift", []):
        entry = next((e for e in entries if e["id"] == capture_id), None)
        if entry is None:
            continue
        capture = ROOT / entry["path"]
        off = runs / f"{capture_id}__no_drift"
        print(f"{capture_id}: running without drift correction")
        _run_capture(capture, off, ["--no-drift"], arguments.reuse)
        on_score = next((s for s in scores if s.capture == capture_id), None)
        ablation.append(_ablation_row(on_score, capture_id, "on"))
        ablation.append(_ablation_row(_score(entry, capture, off), capture_id, "off"))

    gates = evaluate(scores)
    report.mkdir(parents=True, exist_ok=True)
    (report / "gates.json").write_text(
        json.dumps(
            {
                "benchmark": name,
                "gates": gates,
                "ablation": ablation,
                "failed_captures": failed,
                "captures": [
                    {
                        "capture": s.capture,
                        "tier": s.tier,
                        "site": s.site,
                        "group": s.group,
                        "rooms_found": s.rooms_found,
                        "rooms_measured": s.rooms_measured,
                        "adjacency_correct": s.adjacency_correct,
                        "adjacency": s.adjacency_detail,
                        "overlap_area": round(s.overlap_area, 4),
                        "openings": s.openings,
                        "rows": [r.to_dict() for r in s.rows],
                        "timings_s": s.timings,
                        "warnings": s.warnings,
                    }
                    for s in scores
                ],
            },
            indent=2,
        )
        + "\n",
        newline="\n",
    )
    (report / "gates.md").write_text(
        _markdown(name, spec.get("description", ""), scores, gates, ablation, failed),
        encoding="utf-8",
        newline="\n",
    )
    for gate in gates:
        print(f"  [{gate['status']:>13}] {gate['tier']:<5} {gate['gate']}: {gate['value']}")
    print(f"report: {report / 'gates.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
