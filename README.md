# Floor-plan pipeline

Turns an iPhone capture of a property into a dimensioned, stitched floor plan: walls, ceiling
heights, floor areas, doors and windows, damage regions, concealed-damage flags, scope line
items, and a 90% interval on every measurement. Three input tiers: **photos** (2 to 8 per
room, any iPhone 15 or newer), **video** (a walkthrough clip), **LiDAR** (Stray Scanner on a
Pro iPhone). One command per capture.

This is a submission for the Applied AI Engineer case study; the brief is in
[spec/case_study.md](spec/case_study.md). [COMPLIANCE.md](COMPLIANCE.md) maps every
requirement to where it is met and how honestly.

## Install (about 5 GB of downloads; not yet timed on a clean machine)

Needs [uv](https://docs.astral.sh/uv/) and Git. Developed and tested on Windows 11 (Python
3.12, NVIDIA RTX 3050 Ti with 4 GB); the dependencies have builds for Linux and macOS, but
those have not been tried. A GPU is used if there is one; everything also runs on a CPU,
more slowly.

```
git clone https://github.com/suraj2022s/floorplan-case-study.git
cd floorplan-case-study
uv sync --extra learned                      # Python 3.12, PyTorch, MoGe-2, COLMAP (~3 GB)
uv run python scripts/fetch_weights.py       # model weights, SHA-256 checked (2.3 GB)
```

The LiDAR tier alone needs neither of the heavy steps: `uv sync` is enough for it.

## Run

```
uv run floorplan run <capture>
```

`<capture>` is what the phone handed over: a Stray Scanner recording (folder or .zip), a
walkthrough clip (.MOV/.mp4), or a folder holding one sub-folder of photos per room. The tier
is detected from the files; `--tier` forces it. Results go to `out/<capture name>/`:

| File | Contents |
|---|---|
| `plan.png`, `plan.svg` | the stitched floor plan, dimensioned, with intervals |
| `plan.json` | every room, wall, opening, damage region, flag and scope item, each measurement with its 90% interval and whether it was observed or inferred; format: [schema/plan.schema.json](schema/plan.schema.json) |
| `run_log.json` | timings, input hashes, versions |

Warnings printed at the end say what could not be measured and why. A capture the pipeline
cannot measure exits with code 2 and one line saying what to recapture.

How to capture: [docs/capture_protocol.md](docs/capture_protocol.md) (one page).

## Try it without a phone

```
uv run floorplan synth flat .cache/synth/flat          # a synthetic 4-room flat, exact truth
uv run floorplan run .cache/synth/flat
uv run python scripts/fetch_arkitscenes.py --video     # real iPad LiDAR scans + laser truth
uv run floorplan run .cache/arkitscenes/47333462
uv run floorplan run .cache/arkitscenes/raw/47333462.mov
```

## Benchmarks and the fix loop

```
uv run python bench/run_bench.py bench/benchmarks/synthetic.yaml
uv run python bench/run_bench.py bench/benchmarks/arkitscenes.yaml
```

Each capture is run through the public command in its own process and scored against ground
truth; reports go to `reports/bench/<name>/gates.md`. The public-data benchmark uses Apple's
ARKitScenes scans with laser ground truth while our own iPhone benchmark is pending (plan:
[bench/SESSION.md](bench/SESSION.md)). The fix loop is in [fixloop/](fixloop/): declaration,
result and post-mortem for each round, with before and after regenerable at tagged commits.

## Where things are

| Path | Contents |
|---|---|
| `src/floorplan/` | the pipeline: `io/` readers, `frontend/` per-tier front-ends, `geometry/` the shared back-end, `semantics/` damage, rules and scope, `output/` |
| `bench/` | ground truth, scorer, benchmark definitions, measuring protocol |
| `fixloop/` | the fix loop |
| `docs/` | capture protocol, device matrix, design decisions, journal |
| `configs/` | model weights and sample files (pinned), damage rules, scope catalogue |
| `schema/` | the JSON Schema `plan.json` follows (none was supplied, so this one is ours) |
| `tests/` | unit and end-to-end tests (`uv run pytest`) |

## Models, data and licences

| What | Used for | Licence |
|---|---|---|
| MoGe-2 ViT-L (Microsoft) | metric depth, photo and video tiers | MIT |
| OWLv2 base (Google) | finding damage, mirrors and screens in images | Apache-2.0 |
| COLMAP via pycolmap | camera path of a video | BSD-3-Clause |
| ARKitScenes (Apple) | public-data benchmark, development | Apple's dataset licence; not redistributed, fetched by script |
| Stray Scanner sample recording (Diffraction) | testing the LiDAR reader on real files | CC BY 4.0; 4 frames in `tests/data` |
| iPhone 15 Pro sample files (PhotoPrism) | testing the photo and video readers | sample-file terms; not redistributed, fetched by script |

Nothing calls an external service at run time.

## Use of AI tools

The brief allows AI coding tools. Claude Code was used throughout, for writing code and
documents and for running experiments; commits it helped write carry a `Co-Authored-By`
trailer. Design decisions and their evidence are in [docs/decisions/](docs/decisions/) and
[docs/JOURNAL.md](docs/JOURNAL.md).
