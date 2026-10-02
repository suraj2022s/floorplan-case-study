# Fix declaration, round 2

Written 2026-10-03 05:05 IST, before any change to the code it concerns. Baseline: the
commit that adds this file (round 1's fix included). Same benchmark, same scorer, same gate.

## 1. The gate and its failing number

**Opening widths, LiDAR tier: 0 of 10 = 0%**, unchanged by round 1 (1 of 6 measured openings
found, 44.7 cm off in the before run and 49.5 cm off now; 4 phantoms). Alongside it: 8 of the 12
measured walls cannot be matched (scans b and c), and scan c's floor area is 3.9 m² too large.

## 2. Root cause, and the evidence

**Hypothesis.** Room finding has no notion that a wall it has clearly seen is opaque. Floor
seen *through* an opening in that wall (the hall through the door, the window bay and the garden
through the glass) is counted as inside, and cells there get glued to the room, around the
opening rather than through it (round 1's post-mortem: beside a wardrobe in scan c, through the
thin cells that curtain lines cut in scan b).

**Evidence, gathered this time before declaring.** `bench/public/behind_walls.py` measures,
on the rooms the current code finds, how much area lies behind a strongly seen wall line (wall
seen to full height over at least 1 m, scatter under 15 mm), within that wall's length, and what
share of the phone's path is there:

| Scan | Room found | Behind a strongly seen wall | Path there |
|---|---|---|---|
| a | 11.15 m² | 0.00 m² | — |
| b | 12.07 m² | 0.99 m² (behind the window wall) | 0.0% |
| c | 15.73 m² | 3.77 m² (behind the door wall: the hall) | 11.1% |

The truth is 11.86 m². Removing those areas would leave 11.08 m² (b) and 11.96 m² (c), in
line with scan a. The drawings in `fixloop/evidence/round1_layout_{b,c}.png` show the same areas.

## 3. The fix, and the predicted numbers

**Fix.** After cells are grouped into rooms: for each strongly seen wall line, the cells of a
room that lie behind it, within its length, and were counted inside on their own evidence (seen
floor), were seen through an opening in that wall. If less than 20% of the phone's path is
among them, they are dropped; otherwise they are split off as a room of their own (a
multi-room walk). Cells added as the footprint of tall furniture are not affected, and nor is
the extension of a wall line past its end, so L-shaped rooms still close.

The fix was not run before this declaration; the numbers below are reasoned from the table
above and from the per-wall offsets measured in round 1 (the iPad's points lie 2 to 5 cm in
front of the laser's walls in scans b and c).

| Number | Now | Predicted after |
|---|---|---|
| Walls matched (of 12) | 4 | 12 |
| Wall errors in scans b and c | not matched | all between -2 and -10 cm |
| Floor area error, scan b | +0.22 m² | between -1.0 and -0.3 m² |
| Floor area error, scan c | +3.88 m² | between -0.9 and +0.3 m² |
| Scan a | | unchanged |
| Measured openings found (of 6) | 1 | 2 to 4 |
| Phantom openings | 4 | 0 to 2 |
| Openings within 2 cm (gate) | 0/10 | 0 to 2 of 6 to 8, at most 30%: **still FAIL** |

Why the gate will still fail: the window is hung with curtains that hide its edges from inside
(the laser saw them; the iPad cannot), so its width will come out about 0.4 m narrow, and the
door's width will carry the iPad's 1.6% scale shortfall plus the depth map's coarse resolution.
