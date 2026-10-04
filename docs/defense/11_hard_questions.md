# 11. Hard questions

Short, honest answers. Lead with the fact, then the evidence, then what would change it.

**Most of your gates fail. Why is this not mediocre?**
They fail on public data from an iPad, scored exactly as the brief words them, misses and
phantoms included; nothing was hidden or re-worded. Each failure has a measured cause: the
ceiling was biased by the iPad's depth reading 0.9% short, which round 3 corrected (2/12 to
11/12 within 1.5 cm; what is left is scatter between scans); openings fail because the doorway
was hardly looked at in those captures; curtains are taken for walls. Three fix-loop rounds are
documented, including the predictions that were wrong. And the pipeline refuses confident garbage: unmeasured things are
`null`, photos taken against the protocol are "not measured", every plan says when intervals
are uncalibrated.

**You never captured anything yourself.**
True: no iPhone 15 Pro was available. The benchmark session is planned to fit in one visit
(`bench/SESSION.md`), and every tool it needs (ground-truth format, calibration fitting,
head-to-head table) is written and tested. Meanwhile: Apple's laser-measured scans for
accuracy, the assessors' three iPhone recordings for robustness, real iPhone 15 Pro files for
the readers.

**What did the supplied sample data show?**
All three ran with one command each (11 s to 141 s). It found a real false ceiling (2.28 m
against about 3 m, an access hatch in the frames). It exposed three faults, fixed with tests
that fail before the fix: a plant taken for mould, a duplicated inspection, low-filmed doorways
called windows. One false crack is left and reported. No ground truth came with it, so it
shows robustness, not accuracy.

**How much of this did AI write?**
Claude Code was used throughout, for code, documents and experiments, as the brief allows;
the commits it helped write say so. The design choices were made on measured evidence (the
decision records and the journal show what was tried and rejected, with numbers), and I can
explain each module from these notes.

**Why are the LiDAR intervals too narrow, and why not just widen them?**
The misses are walls set by a curtain line, a window measured between curtains, and areas
built from those walls: errors from what was taken for the wall, which the error terms
underrate. Widening is calibration's job: per measurement type, fitted with each room left out
and checked on it. Fitting on one public room would only tune to that room.

**Why not use a learned model end to end?**
Measured alternatives lost: a learned multi-view model was 36 cm off on the camera path
against COLMAP's 4.5 cm, and needed a bigger GPU. Geometry is explainable and each number
traces to fitted planes; learned models are used where nothing else works (depth from one
image, damage in images).

**What happens at the walk-in test?**
`uv run floorplan run <capture>`; the tier is detected. LiDAR: about 10-150 s. Video: about
4 min a minute of clip. Photos: seconds per room. Things that could go wrong, and what the
plan does: no ceiling captured (heights not measured, warning), walls not closing (fallback
rectangle, unseen sides dashed, warning), photos off-protocol (size not measured), curtains
(walls short, interval widened), wide glazed doors (called doors).

**What would you do next?**
Capture the iPhone benchmark and fit calibration; use door frames seen in the images to find
doorways the depth missed; when a curtain-like surface is in front of a seen wall, use the wall
behind it; report a second ceiling level per room; solve photo positions from overlap instead
of the protocol.

## Walk-in checklist

1. `uv sync --extra learned` done, weights fetched (`scripts/fetch_weights.py`), GPU free.
2. Copy the capture locally; run `uv run floorplan run <capture> --out out/walkin`.
3. Read the warnings first; open `plan.png`; check the dashed walls and "not measured" labels.
4. If it exits with code 2, read the one-line reason; it says what to recapture.
5. Say what the intervals mean (90%, uncalibrated) before anyone asks.
