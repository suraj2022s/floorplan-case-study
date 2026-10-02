"""Command line: one command per capture.

floorplan run <capture folder> --out <output folder>
floorplan synth <scene> <folder>      # make a synthetic capture with known dimensions
"""

from __future__ import annotations

from pathlib import Path

import typer

app = typer.Typer(add_completion=False, help="iPhone capture to a measured floor plan.")


def detect_tier(capture: Path) -> str:
    """Work out the tier from what is in the folder."""
    from floorplan.io.stray import is_stray_capture

    if is_stray_capture(capture):
        return "lidar"
    videos = [p for p in capture.iterdir() if p.suffix.lower() in (".mov", ".mp4", ".m4v")]
    if videos:
        return "video"
    images = (".heic", ".heif", ".jpg", ".jpeg", ".png")
    if any(
        p.is_dir() and any(q.suffix.lower() in images for q in p.iterdir())
        for p in capture.iterdir()
    ):
        return "photo"
    if any(p.suffix.lower() in images for p in capture.iterdir()):
        return "photo"
    raise typer.BadParameter(
        f"{capture} is not a recognised capture: expected a Stray Scanner folder, a folder "
        "with a video clip, or a folder of per-room photo folders"
    )


@app.command()
def run(
    capture: Path = typer.Argument(..., exists=True, file_okay=False, help="Capture folder."),
    out: Path = typer.Option(None, help="Output folder (default: out/<capture name>)."),
    tier: str = typer.Option("auto", help="auto, lidar, video or photo."),
    drift: bool = typer.Option(True, "--drift/--no-drift", help="Correct pose drift."),
) -> None:
    """Run the pipeline on one capture and write plan.json, plan.svg, plan.png, run_log.json."""
    import time

    from floorplan.output.render import draw_plan
    from floorplan.output.serialize import plan_to_dict, run_log, write_json
    from floorplan.pipeline import config_for
    from floorplan.pipeline import run as run_pipeline

    tier = detect_tier(capture) if tier == "auto" else tier
    out = out or Path("out") / capture.name
    out.mkdir(parents=True, exist_ok=True)
    config = config_for(tier, correct_drift=drift)

    if tier == "lidar":
        from floorplan.io.stray import read_stray

        plan = run_pipeline(read_stray(capture), config)
    elif tier == "photo":
        from floorplan.frontend.photo import photo_plan
        from floorplan.models.depth import DepthModel

        started = time.perf_counter()
        model = DepthModel()
        plan = photo_plan(capture, model.view, config)
        plan.stats["depth_model"] = model.describe()
        # time not spent in the shared back-end: loading the model and predicting depth
        spent = sum(plan.timings.values())
        plan.timings["depth_model"] = round(time.perf_counter() - started - spent, 3)
    else:
        raise typer.BadParameter(f"the {tier} tier is not implemented yet")

    plan_file = out / "plan.json"
    write_json(plan_file, plan_to_dict(plan, capture.name))
    draw_plan(plan, capture.name, out / "plan")
    write_json(
        out / "run_log.json", run_log(plan, capture, plan_file, {"tier": tier, "drift": drift})
    )

    typer.echo(
        f"{capture.name}: {tier} tier, {len(plan.rooms)} room(s), "
        f"{len(plan.openings)} opening(s), {sum(plan.timings.values()):.1f} s"
    )
    for room in plan.rooms:
        typer.echo(
            f"  {room.id}: area {room.floor_area.value:.2f} m2, "
            f"ceiling {room.ceiling_height.value:.3f} m, walls "
            + ", ".join(f"{wall.length.value:.3f}" for wall in room.walls)
        )
    for opening in plan.openings:
        typer.echo(
            f"  {opening.id}: {opening.kind}, width {opening.width.value:.3f} m ({opening.method})"
        )
    for warning in plan.warnings:
        typer.echo(f"  warning: {warning}")
    typer.echo(f"  wrote {out / 'plan.json'}, plan.svg, plan.png, run_log.json")


@app.command()
def synth(
    scene: str = typer.Argument(..., help="box_room, furnished_room or flat."),
    out: Path = typer.Argument(..., help="Folder to write the synthetic capture to."),
    seed: int = typer.Option(0, help="Random seed for sensor noise."),
    drift: bool = typer.Option(False, "--drift/--no-drift", help="Add pose drift to the walk."),
) -> None:
    """Write a synthetic capture with exactly known dimensions, in Stray Scanner layout."""
    from floorplan.synth.render import DriftModel, make_capture
    from floorplan.synth.scene import SCENES

    if scene not in SCENES:
        raise typer.BadParameter(f"unknown scene {scene!r}; choose from {sorted(SCENES)}")
    drift_model = (
        DriftModel(
            yaw_bias_deg_per_m=0.04,
            yaw_sigma_deg_per_sqrt_m=0.05,
            translation_bias_per_m=0.004,
            translation_sigma_per_sqrt_m=0.004,
        )
        if drift
        else None
    )
    make_capture(scene, out, seed=seed, drift=drift_model)
    typer.echo(f"wrote synthetic capture {scene!r} to {out} (ground truth in ground_truth.json)")


if __name__ == "__main__":
    app()
