"""Command line: one command per capture.

floorplan run <capture> --out <output folder>
floorplan synth <scene> <folder>      # make a synthetic capture with known dimensions

<capture> is whatever the phone handed over: a Stray Scanner recording, a walkthrough clip,
a folder with one sub-folder of photos per room, or a .zip of any of those.
"""

from __future__ import annotations

from pathlib import Path

import typer

app = typer.Typer(add_completion=False, help="iPhone capture to a measured floor plan.")


def _build_plan(tier: str, source: Path, config):
    """Run the tier's front-end and the shared back-end. Returns the plan and the model the
    front-end loaded (None at the LiDAR tier), so the caller can free it."""
    import time

    from floorplan.pipeline import run as run_pipeline

    if tier == "lidar":
        from floorplan.io.arkitscenes import is_arkitscenes, read_arkitscenes
        from floorplan.io.stray import read_stray

        # Apple's public ARKitScenes layout is read for the public-data benchmark only
        reader = read_arkitscenes if is_arkitscenes(source) else read_stray
        return run_pipeline(reader(source), config), None
    if tier == "photo":
        from floorplan.frontend.photo import photo_plan
        from floorplan.models.depth import DepthModel

        started = time.perf_counter()
        model = DepthModel()
        plan = photo_plan(source, model.view, config)
        plan.stats["depth_model"] = model.describe()
        # time not spent in the shared back-end: loading the model and predicting depth
        spent = sum(plan.timings.values())
        plan.timings["depth_model"] = round(time.perf_counter() - started - spent, 3)
        return plan, model
    if tier == "video":
        from floorplan.frontend.sfm import video_capture
        from floorplan.models.depth import DepthModel

        started = time.perf_counter()
        model = DepthModel()
        loaded = video_capture(source, model)
        front_end = time.perf_counter() - started
        plan = run_pipeline(loaded, config)
        plan.stats["depth_model"] = model.describe()
        plan.stats["video"] = loaded.notes
        plan.timings = {"poses_and_depth": round(front_end, 3), **plan.timings}
        return plan, model
    raise ValueError(f"unknown tier {tier!r}; use lidar, video or photo")


@app.command()
def run(
    capture: Path = typer.Argument(
        ..., exists=True, help="Capture: a folder, a .zip, or a walkthrough clip."
    ),
    out: Path = typer.Option(None, help="Output folder (default: out/<capture name>)."),
    tier: str = typer.Option("auto", help="auto, lidar, video or photo."),
    drift: bool = typer.Option(True, "--drift/--no-drift", help="Correct pose drift."),
    damage: bool = typer.Option(
        True, "--damage/--no-damage", help="Look for damage in the images."
    ),
    debug: bool = typer.Option(False, "--debug", help="Show the full trace when a run fails."),
) -> None:
    """Run the pipeline on one capture and write plan.json, plan.svg, plan.png, run_log.json."""
    import time

    from floorplan.io.intake import CaptureNotFound, find_capture
    from floorplan.output.render import draw_plan
    from floorplan.output.serialize import plan_to_dict, run_log, write_json
    from floorplan.pipeline import config_for

    try:
        intake = find_capture(capture, tier)
    except CaptureNotFound as problem:
        typer.echo(f"error: {problem}", err=True)
        raise typer.Exit(2) from None
    tier, source = intake.tier, intake.path
    out = out or Path("out") / intake.name
    out.mkdir(parents=True, exist_ok=True)
    config = config_for(tier, correct_drift=drift)

    try:
        plan, model = _build_plan(tier, source, config)
    except (RuntimeError, ValueError, OSError) as problem:
        if debug:
            raise
        # a capture the pipeline cannot measure is reported as such, not as a made-up plan
        write_json(
            out / "run_log.json",
            {"status": "failed", "error": str(problem), "tier": tier, "capture": str(capture)},
        )
        typer.echo(f"error: {intake.name}: {tier} tier: {problem}", err=True)
        raise typer.Exit(2) from None
    if intake.notes:
        plan.stats["intake"] = intake.notes

    if damage:
        started = time.perf_counter()
        try:
            from floorplan.models.detect import Detector
            from floorplan.semantics.run import add_semantics

            if tier == "lidar":
                from floorplan.io.stray import attach_images

                attach_images(plan, source)
            elif model is not None:
                model.release()  # the GPU cannot hold the depth model and the detector at once
            detector = Detector()
            add_semantics(plan, detector)
            detector.release()
        except ImportError:
            plan.warnings.append(
                "the learned-model packages are not installed (uv sync --extra learned); "
                "damage was not assessed"
            )
        plan.timings["damage"] = round(time.perf_counter() - started, 3)

    plan_file = out / "plan.json"
    write_json(plan_file, plan_to_dict(plan, intake.name))
    draw_plan(plan, intake.name, out / "plan")
    write_json(
        out / "run_log.json", run_log(plan, source, plan_file, {"tier": tier, "drift": drift})
    )

    typer.echo(
        f"{intake.name}: {tier} tier, {len(plan.rooms)} room(s), "
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
    for region in plan.damage:
        typer.echo(
            f"  {region.id}: {region.kind} on {region.surface}, "
            f"{region.width.value:.2f} x {region.height.value:.2f} m"
        )
    for flag in plan.flags:
        typer.echo(f"  {flag.id}: {flag.rule_id} on {flag.surface}")
    for note in intake.notes:
        typer.echo(f"  note: {note}")
    for warning in plan.warnings:
        typer.echo(f"  warning: {warning}")
    typer.echo(f"  wrote {out / 'plan.json'}, plan.svg, plan.png, run_log.json")


@app.command()
def synth(
    scene: str = typer.Argument(..., help="box_room, furnished_room or flat."),
    out: Path = typer.Argument(..., help="Folder to write the synthetic capture to."),
    seed: int = typer.Option(0, help="Random seed for sensor noise."),
    drift: bool = typer.Option(False, "--drift/--no-drift", help="Add pose drift to the walk."),
    drift_scale: float = typer.Option(
        1.0, help="Multiply the drift (1: 0.04 deg and 0.4% per metre walked, plus noise)."
    ),
) -> None:
    """Write a synthetic capture with exactly known dimensions, in Stray Scanner layout."""
    from floorplan.synth.render import DriftModel, make_capture
    from floorplan.synth.scene import SCENES

    if scene not in SCENES:
        raise typer.BadParameter(f"unknown scene {scene!r}; choose from {sorted(SCENES)}")
    drift_model = (
        DriftModel(
            yaw_bias_deg_per_m=0.04 * drift_scale,
            yaw_sigma_deg_per_sqrt_m=0.05 * drift_scale,
            translation_bias_per_m=0.004 * drift_scale,
            translation_sigma_per_sqrt_m=0.004 * drift_scale,
        )
        if drift
        else None
    )
    make_capture(scene, out, seed=seed, drift=drift_model)
    typer.echo(f"wrote synthetic capture {scene!r} to {out} (ground truth in ground_truth.json)")


if __name__ == "__main__":
    app()
