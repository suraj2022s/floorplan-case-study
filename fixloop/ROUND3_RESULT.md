# Round 3: result

Declared in `fixloop/ROUND3_DECLARATION.md` (commit `77c8019`, baseline tag
`fixloop-round3-before`), shipped in `de2f1e6` (tag `fixloop-round3-after`). The fix is one
number: every depth map of an ARKitScenes capture is multiplied by 1.00945 as it is read
(`fixloop/round3.diff`). Regenerate either side with
`python bench/run_bench.py bench/benchmarks/arkitscenes.yaml` at the tag. Full results:
`fixloop/evidence/round3_{before,after}_gates.md`.

| Number | Before | Predicted | After | |
|---|---|---|---|---|
| Ceilings within 1.5 cm (gate: every room) | 2/12, FAIL | 12/12, PASS | **11/12, FAIL** | wrong by one scan, by 1 mm |
| Worst ceiling error | -3.6 cm | about 1.4 cm | **-1.6 cm** | close |
| Mean ceiling error | -2.4 cm | about 0 | **-0.3 cm** | as predicted |
| Repeat spread (gate 1 cm) | 1.72 cm, FAIL | about 1.7 cm, FAIL | **2.12 cm, FAIL** | as predicted (fails) |
| Bedroom 467138 walls | -1 to -13 cm | each about +3 cm | **-20 to +2 cm**, layout changed | wrong |
| Bedroom 467138 floor areas | -0.70, -0.85, +0.38 m² | each about +0.2 m² | **-0.60, -0.48, -0.31 m²** | a, b the right way (+0.10, +0.36); c the other way (-0.69): its outline changed |
| Opening widths (gate 2 cm on 85%) | 0/11 | unchanged | **1/10** | better than predicted |
| Interval calibration (not predicted) | 15/20, FAIL | | **21/25, PASS** | |
| Synthetic benchmark | | unchanged | **unchanged** | as predicted |

**The root cause was right: the bias is gone.** Before, all twelve ceilings were low (mean
-2.4 cm); after, they scatter around the truth (mean -0.3 cm, from -1.6 to +1.3 cm). Of the
twelve scans, eleven are within the gate's 1.5 cm. The one outside is bedroom-b, at -1.6 cm,
where the other two scans of the same room read -1.3 and -0.5 cm: what is left is the scatter
between scans of one room, not a bias, and a single scale factor cannot remove scatter. The
repeat-spread gate says the same: 2.12 cm (the bathroom's three scans span +1.3 to -0.8 cm).
In the brief's words, the LiDAR ceiling went from *repeatable but biased* to *unbiased but not
repeatable to 1 cm*.

**Why the prediction said 12/12 and the run gave 11/12.** The prediction multiplied each
measured ceiling by the factor. Scaling the depth instead of the answer also moves where the
room's outline is, and a ceiling is read at the outline's centre on slightly tilted floor and
ceiling planes, so each scan moved by its own amount: bedroom-b by +2.0 cm instead of the
predicted +2.5 cm. The leave-one-room-out check, rerun on the after numbers, also reads 11/12
(`python bench/fit_depth_scale.py reports/bench/arkitscenes/gates.json`, factor still
missing: 1.0017).

**The wall prediction was wrong, and the reason is a weakness of room finding, not of the
fix.** The declaration expected every wall about 0.9% longer. Instead the outlines changed: in
scan a, two walls improved (-13.2 to -2.2 cm, -12.3 to +1.6 cm) and two got worse (-1.2 to
-20.0 cm, -4.8 to -10.0 cm); scan b's room, whose walls could not be matched before, now has
four matched walls, its window within 0.9 cm and its door within 4.1 cm. A 0.9% change of
depth should not do that on its own. Checked rather than assumed: the walls are not thinner
with the factor (wall scatter 35.2 against 36.0 mm in scan a, 39.2 against 39.3 mm in scan b),
yet the number of wall lines and walls per room changed (scan a: 14 walls to 8; scan b: 6 to
8). So room finding on these curtained scans sits close to its thresholds, and a small change
of input tips walls in or out. That fragility is the next thing to fix, not something to
tune around on this benchmark.

**What changed for the iPhone:** nothing. The factor is the iPad's; iPhone recordings are
read at 1.0 and keep the 1.5% scale term in every interval until an iPhone benchmark gives
their own factor.

## Post-mortem

- The hypothesis held on what it was about (ceilings, areas): every number moved the declared
  way. The prediction was too exact because it was computed on the answers, not by rerunning
  the pipeline on scaled depth; a declaration that can be checked by a run should be made by
  a run of a copy, before the fix is shipped.
- The fix was fitted on the same four rooms it is judged on. The leave-one-room-out count
  (11/12 after) is the honest number; the in-sample count would flatter it.
- Two rooms that were looked at were left out by the selection rule, one of them after its
  numbers were seen: bathroom 483605, whose ceiling has two levels 10 cm apart (its three
  scans read 2.54, 2.53 and 2.65 m against the laser's upper level, 2.565 m). It is reported
  here rather than dropped silently.
