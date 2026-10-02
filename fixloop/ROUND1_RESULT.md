# Round 1: result and post-mortem

Declared in `fixloop/DECLARATION.md` (commit `aad0d05`), shipped in the commit after it.
Before: tag `fixloop-before` (`d8284c4`). After: the commit that adds this file.
Both regenerate with `python bench/run_bench.py bench/benchmarks/arkitscenes.yaml` at the
commit concerned; results are in `fixloop/evidence/before_gates.md` and
`fixloop/evidence/round1_after_gates.md`.

## What the fix did

| Number | Before | Predicted after | After |
|---|---|---|---|
| Measured openings found (of 6) | 1 | 5 or 6 | **1** |
| Phantom openings | 4 | 0 or 1 | **4** |
| Openings within 2 cm (gate) | 0/10 | 15% to 45% | **0/10** |
| Walls matched (of 12) | 4 | 12 | **4** |
| Scan a, wall W2 | -13.9 cm | | **-1.2 cm** |
| Scan b, floor area | +0.62 m² | | **+0.22 m²** |

The prediction was badly wrong. The fix did what it was meant to do in the one place the
mechanism applied (scan a's outline no longer runs into the door's niche, and its wall W2
went from 13.9 cm short to 1.2 cm short), but the gate did not move.

## Why: the root cause was only partly right

The hypothesis was that the room leaks through the gap in a wall that spans its door or
window. Drawing room finding's own internals for scans b and c
(`bench/public/layout_debug.py`; `fixloop/evidence/round1_layout_{b,c}.png`) shows two leaks
that do not go through such a gap:

- **Scan c** leaks through the last 0.6 m of the door wall, beside the corner, where a
  wardrobe hides the wall from floor to top. The wall is seen on one side of that stretch
  only, so the new rule (wall seen on both sides) correctly does not call it a gap; nothing
  stops the merge. The doorway itself was never the leak: the wall above the door was seen,
  so that stretch already counted as wall. The operator also started the recording standing
  in the hall, so the hall counts as "walked into" and is not dropped.
- **Scan b** leaks into the window bay. The true window wall is found as a clean line (9 mm
  scatter), but the curtains in front of it and the window glass and garden behind it add
  five more lines within 50 cm. They cut the floor near the window into thin cells, several
  of which see floor and are counted as inside, and these get glued to the room past the
  wall.

What the evidence supports instead: the code has no notion that **a wall is opaque**. It
asks whether the border between two cells carries wall, never whether a cell lies behind a
wall that was clearly seen from the room. The round-2 declaration starts from that.

## What was wrong with the process

The declaration was written from the overlays of the plans on the laser scan, which show
where the outline leaks but not through which border. Drawing the cells and the merge
decisions takes ten minutes and would have shown the corner and the window bay before the
declaration was committed. Round 2 was declared only after that drawing was made.
