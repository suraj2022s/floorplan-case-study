# Compliance matrix

Requirement → file path → artifact → status. Each requirement is quoted or closely
paraphrased from [spec/case_study.md](spec/case_study.md).

Status values: **Not started**, **In progress**, **Partial** (with the reason),
**Blocked** (with the reason), **Done**. For rows that are not Done, the file path is the
planned location and may not exist yet. A row is only marked Done when its artifact can be
regenerated from this repo.

Last updated: 2026-10-02.

## Part 1 — Capture route and tiers

| # | Requirement | File path | Artifact | Status |
|---|---|---|---|---|
| 1 | Capture route chosen: Route 2, a stock capture protocol naming the off-the-shelf tool | `docs/capture_protocol.md` | One-page protocol | Not started |
| 2 | Protocol covers what to install, how to walk, how long, what to avoid, how to hand files to the pipeline | `docs/capture_protocol.md` | One-page protocol, tested on a non-engineer | Not started |
| 3 | Photo tier: 2 to 8 stills per room, iPhone 15 or newer, no depth, no poses, one folder per room | `src/floorplan/frontend/photo.py` | Photo-tier run output | Not started |
| 4 | Video tier: a handheld walkthrough clip from any iPhone 15 or newer | `src/floorplan/frontend/video.py` | Video-tier run output | Not started |
| 5 | LiDAR tier: depth, poses and intrinsics on Pro-class devices | `src/floorplan/frontend/lidar.py` | LiDAR-tier run output | Not started |
| 6 | Same output contract from each tier, intervals widen honestly as sensor data thins | `src/floorplan/uncertainty/` | Interval widths per tier in the benchmark report | Not started |
| 7 | Device matrix: which tier runs on which hardware, and the accuracy each tier honestly delivers | `docs/device_matrix.md` | Table with numbers taken from benchmark output | Not started |

## Part 2 — Output contract

| # | Requirement | File path | Artifact | Status |
|---|---|---|---|---|
| 8 | Dimensioned per-room plan: walls, ceiling height, floor area, openings | `src/floorplan/geometry/` | `plan.json`, per-room rendering | Not started |
| 9 | Stitched multi-room plan with correct adjacency; every room placed, connected and dimensioned | `src/floorplan/geometry/stitch.py` | `plan.svg`, adjacency check in the benchmark | Not started |
| 10 | Per-surface damage regions with class and metric extent | `src/floorplan/semantics/damage.py` | Damage entries in `plan.json`, overlays | Not started |
| 11 | Concealed-damage flags with the rule that fired | `src/floorplan/semantics/rules.py`, `configs/rules.yaml` | Flags in `plan.json` with `rule_id` | Not started |
| 12 | Scope line items keyed to surfaces | `src/floorplan/semantics/scope.py` | Scope entries in `plan.json` | Not started |
| 13 | A confidence interval on every measurement | `src/floorplan/uncertainty/` | Schema test: no measurement without an interval | Not started |
| 14 | One command per capture | `src/floorplan/cli.py` | `floorplan run <capture>` | Not started |
| 15 | JSON to the published schema | `spec/schema.json`, `src/floorplan/output/schema.py` | Schema validation in tests | Blocked: Round 1 schema not yet in the repo |
| 16 | Rendered plan | `src/floorplan/output/render.py` | `plan.svg`, `plan.png` | Not started |

## Part 2 — Benchmark composition

| # | Requirement | File path | Artifact | Status |
|---|---|---|---|---|
| 17 | One multi-room capture, three or more rooms plus a connector | `bench/ground_truth/`, raw data bundle | Capture + ground truth | Blocked: no iPhone available yet (2026-10-02) |
| 18 | One furnished room with staged damage spanning two damage classes | `bench/ground_truth/`, raw data bundle | Capture + ground truth | Blocked: no iPhone available yet |
| 19 | The same rooms captured at all three input tiers, multi-room set included | raw data bundle | Photo folders, video, LiDAR per site | Blocked: no iPhone available yet |
| 20 | At least one room captured twice at the same tier | raw data bundle | Repeat capture | Blocked: no iPhone available yet |
| 21 | Laser or tape ground truth on everything; raw sensor data and measurements submitted | `bench/ground_truth/*.yaml`, `bench/GT_PROTOCOL.md` | Ground-truth files with photos of readings | Blocked: no captures yet |

## Part 2 — Gates

| # | Requirement | File path | Artifact | Status |
|---|---|---|---|---|
| 22 | Round 1 gates apply | `spec/round1_gates.md`, `bench/gates.py` | Gate table in the benchmark report | Blocked: Round 1 gate table not yet in the repo |
| 23 | Opening widths ≤ 2 cm on ≥ 85% of openings; a missed or phantom opening counts as a miss | `bench/gates.py` | Gate row | Not started |
| 24 | Ceiling height ≤ 1.5 cm per room; spread across repeat captures ≤ 1 cm; report says biased or unrepeatable | `bench/gates.py` | Gate row + bias/spread statement | Not started |
| 25 | Repeatability: two captures of the same room at the same tier agree within 1 cm or 0.5% per wall | `bench/gates.py` | Repeatability table | Not started |
| 26 | Drift accountability: method stated, ablation shows the stitched footprint with it on and off | `src/floorplan/geometry/drift.py` | Ablation figure and table | Not started |
| 27 | Photo-tier whole-property stitch: correct adjacency, no room overlaps, footprint within ±8%, calibrated intervals | `src/floorplan/geometry/stitch.py`, `bench/gates.py` | Gate row | Not started |
| 28 | Photo tier: wall lengths within ±8% with calibrated intervals | `bench/gates.py` | Gate row | Not started |
| 29 | Video tier: wall lengths within ±3% | `bench/gates.py` | Gate row | Not started |
| 30 | Calibration scored at every tier | `src/floorplan/uncertainty/`, `bench/gates.py` | Coverage table per tier | Not started |

## Part 3 — Head-to-head

| # | Requirement | File path | Artifact | Status |
|---|---|---|---|---|
| 31 | LiDAR tier vs one consumer scanning app on 2 benchmark rooms; app and version named, export submitted | `bench/headtohead/` | App export files | Blocked: no Pro iPhone available yet |
| 32 | One table, our error and theirs, dimension by dimension; beat or tie on ≥ 70% of shared dimensions | `bench/headtohead/` | Head-to-head table | Blocked: no Pro iPhone available yet |

## Part 4 — Fix loop

| # | Requirement | File path | Artifact | Status |
|---|---|---|---|---|
| 33 | One-page fix declaration: worst gate with the failing number, root-cause hypothesis and evidence, intended fix and predicted number | `fixloop/DECLARATION.md` | Declaration, committed before the fix | Not started |
| 34 | Shipped fix with a before run and an after run, both regenerable, and a readable diff | `fixloop/` | Before/after gate tables, diff, git tags | Not started |

## Part 5 — Process evidence

| # | Requirement | File path | Artifact | Status |
|---|---|---|---|---|
| 35 | Commit as you work; the history could belong to the person who built the thing | git history, `docs/JOURNAL.md` | Commit log, journal | In progress |

## Deliverables

| # | Requirement | File path | Artifact | Status |
|---|---|---|---|---|
| 36 | Compliance matrix: requirement → file path → artifact → status | `COMPLIANCE.md` | This file | In progress |
| 37 | README to running on a fresh capture in under 15 minutes on a clean machine | `README.md` | Timed clean-machine run | Not started |
| 38 | Reproduction bundle: regenerate every reported number from raw inputs; cached model outputs replay deterministically and the live path also runs | `scripts/`, `bench/run_bench.py` | One reproduce command | Not started |
| 39 | Benchmark report: gates at all three tiers, repeatability table, head-to-head table, timing | `reports/bench/` | `gates.md`, `gates.json` | Not started |
| 40 | Fix loop bundle | `fixloop/` | See rows 33–34 | Not started |
| 41 | Technical report, max 6 pages: architecture, tier design and device matrix, drift handling, error budget, calibration analysis, fix loop story, known failure modes | `reports/technical_report.pdf` | PDF | Not started |
| 42 | Raw benchmark data: sensor logs, ground truth, app exports | raw data bundle, `scripts/fetch_data.py` | Downloadable bundle with checksums | Blocked: no captures yet |

## Walk-in test and constraints

| # | Requirement | File path | Artifact | Status |
|---|---|---|---|---|
| 43 | All three tiers ready to run cold on an unseen capture from the evaluators' iPhone | `src/floorplan/cli.py` | Rehearsal run on an unseen space | Not started |
| 44 | Handheld consumer capture only; every pretrained model, dataset or API disclosed | `MODELS.md` | Model and dataset list with licences and hashes | Not started |
| 45 | Everything runs without calling our own infrastructure | `src/floorplan/` | Offline run log | Not started |
| 46 | Weights and large binaries fetched by script or volume | `scripts/fetch_weights.py` | Fetch script with checksums | Not started |
| 47 | Mirrors, glass, wet-look surfaces and low light covered | `src/floorplan/geometry/`, technical report | Hard-surface capture and failure-mode section | Not started |
