# Fix declaration

Written 2026-10-03 04:40 IST, before any change to the code it concerns. The baseline is
commit `d8284c4` ("Benchmark the LiDAR tier on real scans against a laser: it fails").

**Which benchmark.** No iPhone is available yet, so this declaration is made on the public-data
benchmark (`bench/benchmarks/arkitscenes.yaml`): one real bedroom, captured three times with
an iPad Pro's LiDAR, with ground truth read off a Faro laser scan of the same room. If our own
iPhone benchmark is captured in time, the same procedure is repeated on it.

## 1. The worst gate and its failing number

**Opening widths, LiDAR tier: 0 of 10 = 0%** (gate: within 2 cm on at least 85%, a missed and a
phantom opening each counting as a miss). Of the 6 measured openings (a door and a window, in
each of three scans), 5 were missed and 1 was found 44.7 cm too narrow; 4 phantom openings were
reported. Every gate that could be evaluated failed, and this one is furthest from its
threshold. The same fault also leaves 8 of the 12 measured walls unmatched (scans b and c).

## 2. Root cause, and the evidence

**Hypothesis.** The room's outline does not stop at its own door or window. Room finding cuts
the floor into cells along the wall lines and glues neighbouring cells together across any
border carrying less than 15% wall (`geometry/layout.py`, `find_rooms`, step 4). The stretch
of a wall line that spans a doorway or a window *is* such a border: it carries no wall because
it is the opening. So the space seen through the opening (the hall, the window bay and the
ground outside) is glued onto the room. The opening then no longer lies on the room's outline
and is missed, and where the outline now crosses the hall or the window bay, new openings are
found that do not exist.

**Evidence.** `fixloop/evidence/before_overlay_{a,b,c}.png` put each scan's LiDAR points and
plan onto the laser scan (`bench/public/overlay.py`):
- scan b: the outline runs out through the window, past the window wall, by about 1 m;
- scan c: the outline runs out through the door into the hall, by about 1 m;
- scan a: the outline's corner beside the door is pulled out into the door's niche.

In all three, the leak is at an opening in a wall that was otherwise seen on both sides of
it. Where the outline follows a seen wall, it is within a few centimetres of the laser.

Not explained by this, and not addressed by this fix: the iPad's points are about 1.6% small
against the laser in all three scans (best-fit scale 1.016, 1.015, 1.009), which shortens every
wall by about 5 cm and the ceiling by about 3 cm; and in scan a the window wall is taken at the
curtains, 12 cm in front of it.

## 3. The fix, and the predicted numbers

**Fix.** A border that lies on a wall line with real wall on both sides of it, within 3 m, is a
gap in that wall: an opening between two spaces. Cells are never glued across it, neither as
open floor (step 4) nor as the footprint of furniture (step 5). The space beyond becomes its
own region, and since the phone never walked into it, it is dropped as before. The extension
of a wall line beyond the wall's end is not affected, so L-shaped rooms still close.

**Prediction**, for the same three scans and the same scorer:

| Number | Before | Predicted after |
|---|---|---|
| Measured openings found (of 6) | 1 | 5 or 6 |
| Phantom openings | 4 | 0 or 1 |
| Openings within 2 cm (gate share) | 0/10 | 1 to 3 of 6 to 7, so 15% to 45%: **still FAIL** |
| Walls matched (of 12) | 4 | 12 |
| Wall errors in scans b and c | not matched | between -2 and -9 cm |

Why the gate will still fail: the window's width will be measured between the curtains (about
0.9 m against 1.33 m) and the door's to within a few centimetres at best, because of the 1.6%
scale shortfall and the depth map's 256 x 192 resolution. If it moves as predicted, the next
fixes are the curtain-as-wall error and the scale.
