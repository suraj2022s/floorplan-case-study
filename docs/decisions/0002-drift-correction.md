# 0002 — Drift correction: plane anchoring, not pairwise registration

Date: 2026-10-02. Status: accepted.

## The requirement

The brief fails any submission that uses poses as recorded on the multi-room capture, and
asks for an ablation with the correction on and off.

## What was tried first, and why it was dropped

The first version was the textbook pose graph: cut the walk into fragments, register
consecutive fragments with point-to-plane ICP (odometry edges), register fragments that see
the same place at different times (loop-closure edges), then optimise all fragment poses
together with Open3D's global optimisation.

On the synthetic box room, which has **no drift at all**, it moved poses by up to 32 cm and
turned a clean four-wall room into a 44-edge polygon.

Cause: the walk includes a full turn with the phone tilted up and another with it tilted
down. A fragment from the first turn and one from the second share only a thin horizontal
strip of wall. Registration on that strip leaves height and tilt unconstrained, and
registration between partly overlapping fragments also pairs points across the edge of the
overlap. The library's edge weights are built for point-to-point matching and do not know
that sliding along a plane is free, so the optimiser treated those arbitrary values as
measurements.

A correction stage that can damage a good capture is worse than none, so it was replaced
before any tuning was attempted.

## What is used instead

Plane-anchored correction (`src/floorplan/geometry/drift.py`): a wall is one plane, and
every fragment that sees it must see it in the same place.

1. Fragments of about 24 keyframes; poses inside a fragment are trusted.
2. Walls are fitted to all fragments together. Copies of one wall pulled apart by drift
   (same facing direction, within 15 cm, overlapping along their length) are merged.
3. Each fragment gets a correction of yaw and horizontal shift that puts its wall points on
   their walls. All fragments are solved jointly, with a prior that the correction changes
   slowly along the walk, so a fragment that sees one bare wall follows its neighbours.
4. Repeated six times with a shrinking assignment distance.

Only yaw and horizontal position are corrected. Gravity is observable to the phone, so tilt
does not drift, and height is left alone so a real step between rooms is never flattened.

## Why this is the better fit here

- It cannot harm a capture that already fits its walls: residuals are zero, so corrections
  are zero. Measured on the drift-free box room: largest correction 0.1 mm.
- It corrects exactly the quantity the product reports. Room dimensions are distances
  between wall planes; the correction minimises disagreement about where wall planes are.
- Loop closure is implicit. Seeing a wall again at the end of the walk is a constraint
  between the start and the end, with no place-recognition step that could mismatch.

## Evidence so far (synthetic, development only)

Box room, 4.20 x 3.35 m, with injected drift of about 5 cm and 1 degree over the walk:

| | walls found | floor area | area error |
|---|---|---|---|
| truth | 4 | 14.07 m² | |
| correction off | 11 | 14.40 m² | +2.4% |
| correction on | 4 | 14.08 m² | +0.07% |

With correction on, the four walls are within 5 mm of truth.

## Known limits

- Drift larger than the merge distance (15 cm between two sightings of one wall) is not
  recognised as one wall and is not corrected. The output then shows doubled walls and the
  residual stays high; both are reported in `run_log.json`.
- A fragment's correction is rigid. Drift inside one fragment (about a second) is not
  corrected.
- It needs walls. A capture of a space with no flat vertical surfaces gets no correction,
  and the output says so.
- The ablation on a real multi-room capture is still to be run.
