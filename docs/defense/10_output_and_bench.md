# 10. Output, benchmark and fix loop

**In one sentence:** a run writes `plan.json` (to a published schema), `plan.png`/`plan.svg`
and `run_log.json`; a benchmark runs every capture through the same public command in its own
process and scores only what it wrote; the fix loop declares a root cause and a predicted
number before each fix and reports what happened.

## Output (`output/`, `schema/`)

- `plan.json`: rooms (polygon, walls, area, ceiling height and its range, openings), openings
  (kind, width, height, sill, room behind), adjacency, damage regions, flags, scope items,
  footprint, whether the intervals are calibrated, and warnings in words a capturer can act on.
- It holds only measurements: no clock times, no machine paths. Two runs on the same capture
  give byte-identical files ("same room in, same plan out" is checkable by comparing files).
  Timings, input hashes and versions go in `run_log.json`.
- **Schema.** None was supplied with the assessment, so `schema/plan.schema.json` (JSON Schema
  2020-12) is ours. `tests/test_schema.py` checks every plan the tests make and the three
  sample plans against it, and parses them strictly: it caught a photo room writing `NaN`,
  which is not JSON.
- **Drawing** (`render.py`): rooms outlined, a dimension with its interval on every wall, doors
  as a gap with a swing, windows as a double line, area and ceiling height in each room;
  inferred walls dashed, so the drawing itself shows what was measured. Turned so the longest
  wall runs across the page.
- A capture the pipeline cannot measure exits with code 2 and one line saying what to
  recapture, never a made-up plan.

## Benchmark (`bench/`)

- `run_bench.py` runs each capture with `floorplan run` in a separate process, as a user would.
- `gates.py` scores from the written files and the ground truth only. It does not import the
  pipeline, so the scorer cannot be bent toward the output and a fix can never be a change to
  the scorer.
- Gates, each worded as the brief words it: opening widths (2 cm on 85%, misses and phantoms
  count), ceiling (1.5 cm, repeat spread 1 cm, says biased or unrepeatable), repeatability
  (1 cm or 0.5% per wall), wall lengths (video 3%, photos 8%; the LiDAR figure only Round 1
  sets, and none was supplied, so it is reported but not evaluated), stitch (footprint 8%, no
  overlaps), calibration (coverage within two standard errors of 90%).
- **Two benchmarks:** synthetic scenes with exact truth (checks the code and the scorer; never
  quoted as accuracy) and ARKitScenes (three real iPad LiDAR scans and one video of a bedroom,
  laser ground truth). Our own iPhone benchmark is planned (`bench/SESSION.md`).
- `scripts/reproduce.py` regenerates every reported number in about 10 minutes with caches.

## Fix loop (`fixloop/`)

**Round 1.** Worst gate: openings, 0 of 10. Declared cause: the room leaks through the gap at
its door and window. Fix: never join cells across a gap with wall on both sides. Predicted 5-6
of 6 openings found. Result: one wall improved (-13.9 to -1.2 cm), the gate did not move; the
prediction was badly wrong. Post-mortem: drawing the cells showed the leaks went round the
openings, through a corner hidden by a wardrobe and thin cells cut by curtain lines. The
declaration had been written from overlays that show *where* an outline leaks, not *through
which border*.

**Round 2.** Declared only after measuring the mechanism without changing code: 0.99 m² of
one room and 3.77 m² of another lay behind a clearly seen wall. Fix: seen walls are opaque.
Result: the root cause was right and the leaks are gone (floor-area errors +3.9 to +0.4 m²),
but the gate still failed: notches next to the dropped cells, and curtains hiding the window's
edges.

Lesson to say out loud: measure the mechanism before declaring the cause. Round 2 did, round 1
did not.

## Likely questions

- *How do you know the scorer is fair?* It reads only files, never imports the pipeline; the
  synthetic benchmark with exact truth checks the scorer itself.
- *Is the plan deterministic?* Yes; the depth model and COLMAP results are cached by content,
  COLMAP is seeded, and a test runs the same capture twice and compares.
