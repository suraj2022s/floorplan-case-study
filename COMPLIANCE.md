# Compliance matrix

Requirement → file path → artifact → status. Each requirement is quoted or closely
paraphrased from [spec/case_study.md](spec/case_study.md).

Status values: **Done** (the artifact exists and regenerates from this repo), **Partial**
(what exists, and what is missing), **Blocked** (the reason), **Not started**. A status
says whether the requirement is covered, not whether its gate passes; gate results are
given as they stand, failures included.

Last updated: 2026-10-04 15:38 IST.

**Two gaps affect many rows:** no iPhone 15 Pro has been available for capturing our own
benchmark (rows 17-21, 31-32, 42), and the assessment supplied no Round 1 gate table or JSON
schema ([spec/assessment_email.md](spec/assessment_email.md)), so we publish our own schema
(row 15) and state the gates we apply (row 22). Until the iPhone session (`bench/SESSION.md`), real-data
results come from a public-data benchmark: four real rooms from Apple's ARKitScenes, each
scanned three times by an iPad Pro's LiDAR, with laser ground truth
(`bench/benchmarks/arkitscenes.yaml`).

## Part 1 — Capture route and tiers

| # | Requirement | File path | Artifact | Status |
|---|---|---|---|---|
| 1 | Capture route: Route 2, a stock protocol naming the off-the-shelf tools | `docs/capture_protocol.md` | One-page protocol: Stray Scanner (LiDAR), Camera app (video, photos) | Partial: written (v3: damage shown twice for 2 s, added after a crack in the sample data was glimpsed once); not yet walked through on an iPhone 15 |
| 2 | Protocol covers install, how to walk, how long, what to avoid, handing files over | `docs/capture_protocol.md` | Same | Partial: all covered; not yet tested on a non-engineer |
| 3 | Photo tier: 2-8 stills per room, no depth, no poses, one folder per room | `src/floorplan/frontend/photo.py`, `frontend/room.py`, `io/intake.py` | `floorplan run <photo folders>` | Partial: runs end to end; within 1-2% on synthetic protocol photos; reads real iPhone 15 Pro HEIC/JPEG; reports "not measured" when photos break the protocol; no real protocol photos measured yet |
| 4 | Video tier: a handheld walkthrough clip | `src/floorplan/frontend/sfm.py` | `floorplan run <clip>` | Partial: on a real 60 s clip, walls +1.7% to +5.1% against a laser; reads real iPhone 15 Pro MOV; scale not yet calibrated |
| 5 | LiDAR tier: depth, poses and intrinsics on Pro-class devices | `src/floorplan/io/stray.py`, `src/floorplan/geometry/` | `floorplan run <Stray Scanner recording>` | Partial: runs on the assessors' three LiDAR iPhone recordings (row 48) and a public one; accuracy measured on iPad Pro scans (fails gates, see rows 23-25) |
| 6 | Same output contract from each tier; intervals widen honestly as data thins | `src/floorplan/pipeline.py`, `src/floorplan/uncertainty/budget.py` | One back-end, one `plan.json` format | Partial: same contract; on real data LiDAR intervals 21/25 and video 6/7 contain the laser's value (both pass the calibration gate); photo not measured on real data |
| 7 | Device matrix: tier by hardware, and honest accuracy | `docs/device_matrix.md` | Table, each figure with its source | Partial: iPad and synthetic numbers; iPhone numbers pending the session |

## Part 2 — Output contract

| # | Requirement | File path | Artifact | Status |
|---|---|---|---|---|
| 8 | Dimensioned per-room plan: walls, ceiling height, floor area, openings | `src/floorplan/geometry/`, `src/floorplan/pipeline.py` | `plan.json` | Done (accuracy: rows 23-29) |
| 9 | Stitched multi-room plan with correct adjacency | `src/floorplan/stitch.py`, `src/floorplan/geometry/layout.py` | `plan.json` adjacency, `plan.png` | Partial: correct on the synthetic 4-room flat; no real multi-room capture yet |
| 10 | Per-surface damage regions with class and metric extent | `src/floorplan/semantics/damage.py`, `configs/semantics.yaml` | `damage` in `plan.json`, marked on `plan.png` | Partial: placed on surfaces with metric extent, tested with a stand-in detector; OWLv2 finds the right class on 5 of 7 real damage photos; on the assessors' three undamaged homes, two false regions were removed by requiring damage to lie flat on its surface and one is left (row 48); not yet tried on real damage in a capture |
| 11 | Concealed-damage flags with the rule that fired | `src/floorplan/semantics/rules.py`, `configs/rules.yaml` | `flags` with `rule_id` | Done (tests); real damage pending |
| 12 | Scope line items keyed to surfaces | `src/floorplan/semantics/scope.py`, `configs/scope_catalog.yaml` | `scope` in `plan.json` | Done (tests) |
| 13 | A confidence interval on every measurement | `src/floorplan/uncertainty/budget.py`, `src/floorplan/output/serialize.py`, `tests/test_output_contract.py` | Every measurement has a 90% interval or is marked not measured | Done: enforced by a test over the whole written plan, damage and scope included |
| 14 | One command per capture | `src/floorplan/cli.py` | `floorplan run <capture>` | Done |
| 15 | JSON to the published schema | `schema/plan.schema.json`, `src/floorplan/output/serialize.py`, `tests/test_schema.py` | `plan.json` (`schema_version: 1.0`) | Done: no schema was supplied with the assessment, so we publish our own (JSON Schema 2020-12); a test checks every plan the tests produce, and the three sample plans, against it and as strict JSON |
| 16 | Rendered plan | `src/floorplan/output/render.py` | `plan.svg`, `plan.png` | Done |

## Part 2 — Benchmark composition

| # | Requirement | File path | Artifact | Status |
|---|---|---|---|---|
| 17 | One multi-room capture, 3+ rooms plus a connector | `bench/SESSION.md` | Capture + ground truth | Blocked: no iPhone 15 Pro yet |
| 18 | One furnished room with staged damage of two classes | `bench/SESSION.md` | Capture + ground truth | Blocked: same |
| 19 | The same rooms at all three tiers, multi-room included | `bench/SESSION.md` | Per-tier captures | Blocked: same. Public-data stand-in: one room at LiDAR and video |
| 20 | One room captured twice at the same tier | `bench/benchmarks/arkitscenes.yaml` | Repeat captures | Partial: four real rooms (public data), each captured three times at the LiDAR tier; own repeats pending |
| 21 | Laser or tape ground truth on everything; raw data and measurements submitted | `bench/GT_PROTOCOL.md`, `bench/ground_truth/` | Ground-truth files | Partial: laser truth for four public rooms (`arkitscenes-*.yaml`, read off Apple's Faro scans by `bench/public/laser_truth.py`): one with walls, ceiling, area and openings, three with the ceiling only; own measurements pending |

## Part 2 — Gates (results on the public-data benchmark, `reports/bench/arkitscenes/gates.md`)

| # | Requirement | File path | Artifact | Status |
|---|---|---|---|---|
| 22 | Round 1 gates apply | `bench/gates.py` | Gate table | Partial: no Round 1 gate table was supplied (`spec/assessment_email.md`); the brief's five added gates and the photo and video wall gates are applied; the LiDAR wall gate, set only by Round 1, is reported but not evaluated |
| 23 | Opening widths ≤ 2 cm on ≥ 85%; misses and phantoms count | `bench/gates.py` | Gate row | Reported: **FAIL**, LiDAR 1/10 (bedroom-b's window within 0.9 cm), video 0/2 |
| 24 | Ceiling ≤ 1.5 cm per room; repeat spread ≤ 1 cm; say biased or unrepeatable | `bench/gates.py` | Gate rows | Reported: LiDAR **FAIL** 11/12 scans within 1.5 cm (worst -1.6 cm, mean -0.3 cm), spread 2.12 cm **FAIL**: unbiased but not repeatable to 1 cm, after fix-loop round 3 removed the iPad's depth bias (before: 2/12, all low: repeatable but biased) |
| 25 | Repeatability: same room, same tier, within 1 cm or 0.5% per wall | `bench/gates.py` | Repeatability table | Reported: **FAIL**, 0 of 4 walls agree between the two scans of the bedroom whose walls can be matched (worst 15.1 cm); outlines on these curtained scans change from scan to scan |
| 26 | Drift accountability: method stated, footprint with it on and off | `src/floorplan/geometry/drift.py`, `docs/decisions/0002-drift-correction.md` | Ablation table | Partial: plane-anchored correction; ablation on the synthetic drifting flat: footprint +0.04% with it, -2.55% without, worst wall 4.2 vs 62.1 cm (`reports/bench/synthetic`); real multi-room pending |
| 27 | Photo-tier whole-property stitch: adjacency, no overlaps, footprint ±8% | `src/floorplan/stitch.py`, `bench/gates.py` | Gate row | Partial: gate implemented; no real photo set yet |
| 28 | Photo tier: walls ±8% with calibrated intervals | `bench/gates.py` | Gate row | Partial: met on synthetic protocol photos; no real photo set yet |
| 29 | Video tier: walls ±3% | `bench/gates.py` | Gate row | Reported: **FAIL**, 2 of 4 walls within 3% (worst +5.0%) |
| 30 | Calibration scored at every tier | `bench/gates.py`, `bench/calibrate.py`, `bench/fit_depth_scale.py`, `src/floorplan/uncertainty/budget.py` | Coverage per tier; factors with leave-one-room-out | Partial: LiDAR **PASS** 21/25, video **PASS** 6/7, photo not measured on real data; the iPad's depth-scale factor is fitted on four rooms and checked with each room left out; iPhone factors wait for the iPhone benchmark |

## Part 3 — Head-to-head

| # | Requirement | File path | Artifact | Status |
|---|---|---|---|---|
| 31 | LiDAR tier vs a consumer app on 2 rooms; app and version named; export submitted | `bench/SESSION.md` step 6, `bench/headtohead/TEMPLATE.yaml`, `bench/headtohead/export_cloud.py` | App exports | Blocked: no Pro iPhone, and consumer apps scan only live. A stand-in was tried on 4 October: a public bedroom's raw iPad cloud (`export_cloud.py`) given to Pointorama (web, free trial); its automatic floor step worked (2.59 m against the laser's 2.64 m) but its room step could not be finished without drawing by hand, which would not be a fair comparison, so no number is reported |
| 32 | One table, our error and theirs; beat or tie on ≥ 70% | `bench/headtohead.py` | Table | Blocked: same (tool written and checked) |

## Part 4 — Fix loop

| # | Requirement | File path | Artifact | Status |
|---|---|---|---|---|
| 33 | Fix declaration before the fix: worst gate, root cause with evidence, fix, predicted number | `fixloop/DECLARATION.md`, `fixloop/ROUND2_DECLARATION.md`, `fixloop/ROUND3_DECLARATION.md` | Committed before each fix | Done (three rounds, on the public-data benchmark) |
| 34 | Shipped fix; before and after regenerable; readable diff | `fixloop/ROUND{1,2,3}_RESULT.md`, tags `fixloop-*-before/after`, `fixloop/round{1,2,3}.diff` | Results and post-mortems | Done: rounds 1-2 (openings) did not move the gate; round 3 (ceiling) removed the bias, 2/12 to 11/12 within 1.5 cm, the gate short by one scan, and moved interval calibration from FAIL to PASS |

## Part 5 — Process evidence

| # | Requirement | File path | Artifact | Status |
|---|---|---|---|---|
| 35 | Commit as you work | git history, `docs/JOURNAL.md` | Commit log, journal | In progress |

## Deliverables

| # | Requirement | File path | Artifact | Status |
|---|---|---|---|---|
| 36 | Compliance matrix | `COMPLIANCE.md` | This file | In progress |
| 37 | README to running on a fresh capture in under 15 minutes on a clean machine | `README.md` | Install, run, try without a phone | Partial: written; the clean-machine timing is still to be done |
| 38 | Reproduction bundle; caches replay, live path runs | `scripts/reproduce.py`, `scripts/fetch_*.py`, `bench/run_bench.py`, `configs/*.json` | One command: fetch, test, both benchmarks, calibration report | Done for the public and synthetic data (depth and COLMAP results replay from cache; deleting `.cache` runs live); own benchmark pending |
| 39 | Benchmark report: gates at all three tiers, repeatability, head-to-head, timing | `reports/bench/` | `gates.md`, `gates.json` | Partial: LiDAR (four rooms, twelve scans) and video (one clip) tiers on public data, repeatability and timing included; photo tier, own benchmark and head-to-head pending |
| 40 | Fix loop bundle | `fixloop/README.md` | Declarations, results, tags before/after, `round1.diff`, `round2.diff` | Done |
| 41 | Technical report, max 6 pages | `reports/technical_report.md` | Report | Partial: complete draft; iPhone results to add |
| 42 | Raw benchmark data: sensor logs, ground truth, app exports | `scripts/fetch_arkitscenes.py` (public data) | Data bundle | Blocked: no own captures yet |

## Walk-in test and constraints

| # | Requirement | File path | Artifact | Status |
|---|---|---|---|---|
| 43 | All three tiers ready to run cold on the evaluators' iPhone capture | `src/floorplan/cli.py`, `src/floorplan/io/intake.py` | One command per tier | Partial: all three run on real files of the right formats; LiDAR has run cold on the assessors' three iPhone recordings (row 48); video and photos not yet on an iPhone 15 capture of a room |
| 44 | Every pretrained model, dataset or API disclosed | `README.md` (models, data and licences), `configs/weights.json`, `configs/samples.json` | Table with licences; pinned hashes | Done |
| 45 | Runs without calling our own infrastructure | `src/floorplan/` | No network calls at run time | Done |
| 46 | Weights and large binaries fetched by script | `scripts/fetch_weights.py`, `configs/weights.json` | Fetch script, SHA-256 checked | Done |
| 47 | Mirrors, glass, wet-look surfaces and low light covered | `src/floorplan/semantics/run.py`, `src/floorplan/geometry/layout.py` | Handling and failure modes | Partial: mirrors and screens are not taken for openings (on a sample recording, a shower's glass was dropped as an opening, though named a television); space seen through glass is kept out of the room; curtains, wet-look surfaces and low light not yet handled or tested |
| 48 | Run the code on the supplied sample data (assessment email) | `reports/samples/README.md`, `scripts/fetch_supplied.py` | Plans, run logs and findings for the three Stray Scanner recordings | Done: each runs with one command; no ground truth was supplied, so this shows robustness, not accuracy. Found a false ceiling (2.28 m against 2.95-3.08 m); fixed two false damage detections and a doorway classed as a window; one false crack left and reported |
