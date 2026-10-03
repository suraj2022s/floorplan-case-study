# Fix declaration, round 3

Written 2026-10-04, before any change to the code it concerns. Baseline: tag
`fixloop-round3-before` (the public-data benchmark grown from one room to four). Same scorer,
gates as the brief words them.

## 1. The gate and its failing number

**Ceiling height, LiDAR tier: 2 of 12 captures within 1.5 cm** (worst -3.6 cm), and the gate
asks for every room. Four rooms from four separate ARKitScenes visits, three iPad Pro scans each, truth from Apple's
Faro laser scans (`reports/bench/arkitscenes/gates.md` at the tag):

| Room (ceiling) | Errors of the three scans |
|---|---|
| bedroom 467138 (2.640 m) | -3.3, -3.6, -2.6 cm |
| bedroom 423441 (2.334 m) | -1.2, -1.9, -1.9 cm |
| bathroom 438802 (2.402 m) | -0.9, -2.0, -2.6 cm |
| kitchen 482863 (2.573 m) | -3.0, -3.2, -1.9 cm |

The repeat-spread gate (1 cm) also fails, at 1.72 cm: the bathroom's three scans span 1.7 cm
and the kitchen's 1.2 cm. That is scatter, not bias, and this round does not address it.

## 2. Root cause, and the evidence

**Hypothesis.** The iPad's LiDAR reads every distance about 1% short. A ceiling height is the
sum of two depth readings from the same camera (up to the ceiling, down to the floor), so it
comes out the same fraction short.

**Evidence.**

- All twelve errors have the same sign, in four rooms from four separate visits. Noise would
  scatter both ways; a misplaced floor or ceiling plane would differ room
  by room.
- The error grows with the height: -1.7 cm on average at 2.33 m, -3.2 cm at 2.64 m. A fixed
  fraction of each distance does that; a fixed offset would not.
- It agrees with what the first room showed before (round 2's notes, the technical report):
  the iPad's walls and areas short against the laser, by 0.9-1.6%.
- Arithmetic on the numbers above, with no code changed (`bench/fit_depth_scale.py` on the
  baseline's `gates.json`): the mean of truth / measured is 1.00945, and each room corrected
  with the factor fitted on the *other three* rooms lands within 1.5 cm in all 12 scans
  (worst +1.5 cm, bathroom-a).

## 3. The fix, and the predicted numbers

**Fix.** A depth-scale factor for the device, applied to every depth map as it is read: 1.00945
for the iPad Pro of ARKitScenes (`io/arkitscenes.py`), fitted on the four rooms by
`bench/fit_depth_scale.py`. iPhone recordings (`io/stray.py`) are left at 1.0: one device's
factor says nothing certain about another's, and the iPhone's comes from the iPhone benchmark.
The 1.5% scale term stays in every LiDAR interval.

**Predicted after the fix.**

| Number | Before | Predicted |
|---|---|---|
| Ceilings within 1.5 cm (gate: all) | 2/12, FAIL | **12/12, PASS**; worst about +/-1.4 cm |
| Held out (each room with the other rooms' factor) | | 12/12 within 1.5 cm |
| Repeat spread (gate: 1 cm) | 1.72 cm, FAIL | about 1.7 cm, still FAIL |
| Bedroom 467138 walls | -1 to -13 cm | about 3 cm longer each (+0.9%) |
| Bedroom 467138 floor area | -0.70, -0.85, +0.57 m² | each about +0.2 m² (+1.9%) |
| Opening widths | 0/11 | unchanged (curtains and an unseen door, not scale) |
| Synthetic benchmark | | unchanged (its scenes are read through `io/stray.py`) |

If a ceiling ends up outside 1.5 cm, or the walls do not move by about +0.9%, the hypothesis
is wrong or incomplete, and the result file will say so.
