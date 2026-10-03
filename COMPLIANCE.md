# Compliance matrix

Requirement → file path → artifact → status. Each requirement is quoted or closely
paraphrased from [spec/case_study.md](spec/case_study.md).

Status values: **Done** (the artifact exists and regenerates from this repo), **Partial**
(what exists, and what is missing), **Blocked** (the reason), **Not started**. A status
says whether the requirement is covered, not whether its gate passes; gate results are
given as they stand, failures included.

Last updated: 2026-10-03 15:30 IST.

**Two blockers affect many rows:** no iPhone 15 Pro has been available for capturing our own
benchmark (rows 17-21, 31-32, 42), and the Round 1 brief with its gate table and JSON schema
is not yet in `spec/` (rows 15, 22). Until the iPhone session (`bench/SESSION.md`), real-data
results come from a public-data benchmark: three iPad Pro LiDAR scans of one bedroom with laser
ground truth (`bench/benchmarks/arkitscenes.yaml`).

## Part 1 — Capture route and tiers

| # | Requirement | File path | Artifact | Status |
|---|---|---|---|---|
| 1 | Capture route: Route 2, a stock protocol naming the off-the-shelf tools | `docs/capture_protocol.md` | One-page protocol: Stray Scanner (LiDAR), Camera app (video, photos) | Partial: written (v2); not yet walked through on an iPhone 15 |
| 2 | Protocol covers install, how to walk, how long, what to avoid, handing files over | `docs/capture_protocol.md` | Same | Partial: all covered; not yet tested on a non-engineer |
| 3 | Photo tier: 2-8 stills per room, no depth, no poses, one folder per room | `src/floorplan/frontend/photo.py`, `frontend/room.py`, `io/intake.py` | `floorplan run <photo folders>` | Partial: runs end to end; within 1-2% on synthetic protocol photos; reads real iPhone 15 Pro HEIC/JPEG; reports "not measured" when photos break the protocol; no real protocol photos measured yet |
| 4 | Video tier: a handheld walkthrough clip | `src/floorplan/frontend/sfm.py` | `floorplan run <clip>` | Partial: on a real 60 s clip, walls +1.7% to +5.3% against a laser; reads real iPhone 15 Pro MOV; scale not yet calibrated |
| 5 | LiDAR tier: depth, poses and intrinsics on Pro-class devices | `src/floorplan/io/stray.py`, `src/floorplan/geometry/` | `floorplan run <Stray Scanner recording>` | Partial: reader verified on a real Stray Scanner recording; accuracy measured on iPad Pro scans (fails gates, see rows 23-25) |
| 6 | Same output contract from each tier; intervals widen honestly as data thins | `src/floorplan/pipeline.py`, `src/floorplan/uncertainty/budget.py` | One back-end, one `plan.json` format | Partial: same contract; video intervals hold (6/7), LiDAR intervals too narrow on real data (3/11) |
| 7 | Device matrix: tier by hardware, and honest accuracy | `docs/device_matrix.md` | Table, each figure with its source | Partial: iPad and synthetic numbers; iPhone numbers pending the session |

## Part 2 — Output contract

| # | Requirement | File path | Artifact | Status |
|---|---|---|---|---|
| 8 | Dimensioned per-room plan: walls, ceiling height, floor area, openings | `src/floorplan/geometry/`, `src/floorplan/pipeline.py` | `plan.json` | Done (accuracy: rows 23-29) |
| 9 | Stitched multi-room plan with correct adjacency | `src/floorplan/stitch.py`, `src/floorplan/geometry/layout.py` | `plan.json` adjacency, `plan.png` | Partial: correct on the synthetic 4-room flat; no real multi-room capture yet |
| 10 | Per-surface damage regions with class and metric extent | `src/floorplan/semantics/damage.py`, `configs/semantics.yaml` | `damage` in `plan.json`, marked on `plan.png` | Partial: placed on surfaces with metric extent; tested with a stand-in detector; OWLv2 not yet tried on real damage |
| 11 | Concealed-damage flags with the rule that fired | `src/floorplan/semantics/rules.py`, `configs/rules.yaml` | `flags` with `rule_id` | Done (tests); real damage pending |
| 12 | Scope line items keyed to surfaces | `src/floorplan/semantics/scope.py`, `configs/scope_catalog.yaml` | `scope` in `plan.json` | Done (tests) |
| 13 | A confidence interval on every measurement | `src/floorplan/uncertainty/budget.py`, `src/floorplan/output/serialize.py` | Every measurement has a 90% interval or is marked not measured | Partial: holds by construction; no schema test enforces it yet |
| 14 | One command per capture | `src/floorplan/cli.py` | `floorplan run <capture>` | Done |
| 15 | JSON to the published schema | `src/floorplan/output/serialize.py` | `plan.json` (`schema: draft-1`) | Blocked: the published Round 1 schema is not in the repo |
| 16 | Rendered plan | `src/floorplan/output/render.py` | `plan.svg`, `plan.png` | Done |

## Part 2 — Benchmark composition

| # | Requirement | File path | Artifact | Status |
|---|---|---|---|---|
| 17 | One multi-room capture, 3+ rooms plus a connector | `bench/SESSION.md` | Capture + ground truth | Blocked: no iPhone 15 Pro yet |
| 18 | One furnished room with staged damage of two classes | `bench/SESSION.md` | Capture + ground truth | Blocked: same |
| 19 | The same rooms at all three tiers, multi-room included | `bench/SESSION.md` | Per-tier captures | Blocked: same. Public-data stand-in: one room at LiDAR and video |
| 20 | One room captured twice at the same tier | `bench/benchmarks/arkitscenes.yaml` | Repeat captures | Partial: three LiDAR captures of one real room (public data); own repeats pending |
| 21 | Laser or tape ground truth on everything; raw data and measurements submitted | `bench/GT_PROTOCOL.md`, `bench/ground_truth/` | Ground-truth files | Partial: laser ground truth for the public room (`arkitscenes-467138.yaml`, read off by `bench/public/laser_truth.py`); own measurements pending |

## Part 2 — Gates (results on the public-data benchmark, `reports/bench/arkitscenes/gates.md`)

| # | Requirement | File path | Artifact | Status |
|---|---|---|---|---|
| 22 | Round 1 gates apply | `bench/gates.py` | Gate table | Blocked: Round 1 gate table not in the repo; the LiDAR wall gate is reported as "not evaluated" until it is |
| 23 | Opening widths ≤ 2 cm on ≥ 85%; misses and phantoms count | `bench/gates.py` | Gate row | Reported: **FAIL**, LiDAR 0/11, video 0/2 |
| 24 | Ceiling ≤ 1.5 cm per room; repeat spread ≤ 1 cm; say biased or unrepeatable | `bench/gates.py` | Gate rows | Reported: LiDAR **FAIL** (-2.6 to -3.8 cm), spread 0.96 cm **PASS**: repeatable but biased (the iPad's 1.6% scale) |
| 25 | Repeatability: same room, same tier, within 1 cm or 0.5% per wall | `bench/gates.py` | Repeatability table | Partial: implemented; not evaluable yet (two of the three scans' walls cannot be matched) |
| 26 | Drift accountability: method stated, footprint with it on and off | `src/floorplan/geometry/drift.py`, `docs/decisions/0002-drift-correction.md` | Ablation table | Partial: plane-anchored correction; ablation on the synthetic drifting flat: footprint +0.04% with it, -2.55% without, worst wall 4.2 vs 62.1 cm (`reports/bench/synthetic`); real multi-room pending |
| 27 | Photo-tier whole-property stitch: adjacency, no overlaps, footprint ±8% | `src/floorplan/stitch.py`, `bench/gates.py` | Gate row | Partial: gate implemented; no real photo set yet |
| 28 | Photo tier: walls ±8% with calibrated intervals | `bench/gates.py` | Gate row | Partial: met on synthetic protocol photos; no real photo set yet |
| 29 | Video tier: walls ±3% | `bench/gates.py` | Gate row | Reported: **FAIL**, 2 of 4 walls within 3% (worst +5.0%) |
| 30 | Calibration scored at every tier | `bench/gates.py`, `src/floorplan/uncertainty/budget.py` | Coverage per tier | Partial: LiDAR **FAIL** 3/11, video **PASS** 6/7, photo not yet; calibration factors not yet fitted |

## Part 3 — Head-to-head

| # | Requirement | File path | Artifact | Status |
|---|---|---|---|---|
| 31 | LiDAR tier vs a consumer app on 2 rooms; app and version named; export submitted | `bench/SESSION.md` step 6 | App exports | Blocked: no Pro iPhone yet |
| 32 | One table, our error and theirs; beat or tie on ≥ 70% | `bench/headtohead/` | Table | Blocked: same |

## Part 4 — Fix loop

| # | Requirement | File path | Artifact | Status |
|---|---|---|---|---|
| 33 | Fix declaration before the fix: worst gate, root cause with evidence, fix, predicted number | `fixloop/DECLARATION.md`, `fixloop/ROUND2_DECLARATION.md` | Committed before each fix | Done (two rounds, on the public-data benchmark) |
| 34 | Shipped fix; before and after regenerable; readable diff | `fixloop/ROUND1_RESULT.md`, `fixloop/ROUND2_RESULT.md`, tags `fixloop-before`, `fixloop-round2-before` | Results and post-mortems | Done: the gate did not move; round 1's prediction was badly wrong, round 2's root cause was right and its leaks are gone |

## Part 5 — Process evidence

| # | Requirement | File path | Artifact | Status |
|---|---|---|---|---|
| 35 | Commit as you work | git history, `docs/JOURNAL.md` | Commit log, journal | In progress |

## Deliverables

| # | Requirement | File path | Artifact | Status |
|---|---|---|---|---|
| 36 | Compliance matrix | `COMPLIANCE.md` | This file | In progress |
| 37 | README to running on a fresh capture in under 15 minutes on a clean machine | `README.md` | Install, run, try without a phone | Partial: written; the clean-machine timing is still to be done |
| 38 | Reproduction bundle; caches replay, live path runs | `scripts/fetch_*.py`, `bench/run_bench.py`, `configs/*.json` | Fetch and rerun commands | Partial: weights, samples and public data fetched by script with checksums; depth and COLMAP results cached and replayed; no single reproduce-everything command yet |
| 39 | Benchmark report: gates at all three tiers, repeatability, head-to-head, timing | `reports/bench/` | `gates.md`, `gates.json` | Partial: LiDAR and video tiers on public data, timing included; photo tier, own benchmark and head-to-head pending |
| 40 | Fix loop bundle | `fixloop/` | Rows 33-34 | Done |
| 41 | Technical report, max 6 pages | `reports/technical_report.md` | Report | Not started |
| 42 | Raw benchmark data: sensor logs, ground truth, app exports | `scripts/fetch_arkitscenes.py` (public data) | Data bundle | Blocked: no own captures yet |

## Walk-in test and constraints

| # | Requirement | File path | Artifact | Status |
|---|---|---|---|---|
| 43 | All three tiers ready to run cold on the evaluators' iPhone capture | `src/floorplan/cli.py`, `src/floorplan/io/intake.py` | One command per tier | Partial: all three run on real files of the right formats; not yet on an iPhone 15 capture of a room |
| 44 | Every pretrained model, dataset or API disclosed | `README.md` (models, data and licences), `configs/weights.json`, `configs/samples.json` | Table with licences; pinned hashes | Done |
| 45 | Runs without calling our own infrastructure | `src/floorplan/` | No network calls at run time | Done |
| 46 | Weights and large binaries fetched by script | `scripts/fetch_weights.py`, `configs/weights.json` | Fetch script, SHA-256 checked | Done |
| 47 | Mirrors, glass, wet-look surfaces and low light covered | `src/floorplan/semantics/run.py`, `src/floorplan/geometry/layout.py` | Handling and failure modes | Partial: mirrors and screens are not taken for openings; space seen through glass is kept out of the room; curtains, wet-look surfaces and low light not yet handled or tested |
