# Round 2: result

Declared in `fixloop/ROUND2_DECLARATION.md` (commit `16731ab`, tag `fixloop-round2-before`),
shipped in the commit that adds this file. Regenerate either side with
`python bench/run_bench.py bench/benchmarks/arkitscenes.yaml` at the commit concerned. Full
results: `fixloop/evidence/round2_after_gates.md`; plans: `round2_after_plan_{b,c}.png`.

| Number | Before | Predicted | After | |
|---|---|---|---|---|
| Floor area error, scan b | +0.22 m² | -1.0 to -0.3 m² | **-0.85 m²** | as predicted |
| Floor area error, scan c | +3.88 m² | -0.9 to +0.3 m² | **+0.38 m²** | just outside, by 0.08 m² |
| Scan a | | unchanged | **unchanged** | as predicted |
| Walls matched (of 12) | 4 | 12 | **4** | wrong |
| Measured openings found (of 6) | 1 | 2 to 4 | **1** | wrong |
| Phantom openings | 4 | 0 to 2 | **5** | wrong |
| Openings within 2 cm (gate) | 0/10 | at most 30%, FAIL | **0/11, FAIL** | as predicted |
| Ceiling repeat spread (not predicted) | 1.05 cm, FAIL | | **0.96 cm, PASS** | |

**The root cause was right this time, and the fix removed what it was aimed at.** The space
seen through the window (scan b) and through the door (scan c) is no longer part of the room:
scan c's room went from 15.7 m² to 12.2 m² against a true 11.9 m², and scan b's from 12.1 m² to
11.0 m², next to scan a's 11.2 m². What is left of the error in all three is the iPad's 1.6%
scale shortfall (about 0.4 m² of area) and, in scan a, the curtains.

**The gate did not move, and the wall prediction was wrong**, for a reason the declaration
did not foresee: the cells dropped were the ones where floor was seen through the opening,
and the cells beside them where little floor was seen stayed. Each outline keeps a step where
they were: a 0.47 m notch beside the window in scan b, and a 1.5 m by 0.8 m strip past the door
in scan c. A tape-style ground truth has four walls; the outlines have six and eight sides,
so the scorer cannot pair them, and the openings on those walls are not on the matched walls.
The phantoms are openings found on the edges of these leftovers.

**Next step, not yet declared:** the leftovers are regions behind a clearly seen wall with
little floor seen and no path, attached to the room through the same opening. Dropping the
whole connected region behind the wall, not only its well-seen cells, would remove them. The
remaining shortfall after that is the scale, which needs a calibration against an iPhone
benchmark, and the curtains.
