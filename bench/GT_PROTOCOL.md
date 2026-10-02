# Ground-truth measuring protocol

How every benchmark room is measured. Follow it literally and in this order, so that the
pipeline and the tape measure mean the same thing by "wall length" and "opening width".
Record the numbers in a copy of [ground_truth/TEMPLATE.yaml](ground_truth/TEMPLATE.yaml).

## What you need

- A laser distance meter (preferred) or a steel tape. Write down the model and its stated
  accuracy. A cloth or fibreglass tape is not acceptable: it stretches.
- Masking tape and a marker for labels.
- A phone to photograph each reading.

## Before measuring

1. Measure the rooms in the same state they were captured in: same doors open, same
   furniture positions.
2. Label each room with a short name (`living`, `bed1`, `corridor`).
3. In each room, stand in the middle and face the wall that has the door you came in
   through. That wall is `W1`. Turning to your **right**, the next walls are `W2`, `W3`,
   and so on. Stick a label on each wall.
4. Label openings by the wall they are in: `D1`, `D2` for doors and open passages, `WIN1`
   for windows.

## What to measure

Every length in metres to the millimetre (for example `3.352`). Measure each one twice; if
the two readings differ by more than 3 mm, measure a third time and note it.

### Walls

- Measure along the wall face, from the face of the wall at one corner to the face of the
  wall at the other corner, at about 1.0 m above the floor.
- Measure the wall itself, not the skirting board and not furniture standing in front of it.
- If furniture blocks the line at 1.0 m, measure at a height that is clear and write that
  height in `note`.
- A wall is measured corner to corner **straight through** any door or window in it.

### Ceiling height

- Floor to ceiling, laser standing on the bare floor (not on a rug), at three places: the
  middle of the room, and about 0.5 m in from two opposite corners.
- The three values show whether the ceiling or floor slopes. The benchmark uses the middle
  value.

### Openings (doors, open passages, windows)

- **Width**: the clear width between the two inner faces of the frame (the jambs), measured
  at three heights: near the top, the middle, near the bottom. The benchmark uses the middle
  value. For a door, open it fully and measure the frame, not the door leaf.
- **Height**: from the floor (doors) or the sill (windows) to the underside of the top of
  the frame.
- **Sill height** (windows only): floor to the top of the sill.
- **Position**: distance along the wall from the wall's **left** corner (as you face the
  wall from inside the room) to the nearer jamb.
- **Wall thickness** at each doorway: the depth of the frame from one room's wall face to
  the other's.
- Write which room is on the other side (`connects`), or `outside`.

### Checks that catch mistakes

- **Diagonals**: in each four-walled room measure both diagonals, corner to corner. If they
  agree within about 1 cm the room is square; if not, the room is a parallelogram and the
  plan should show it.
- **Across rooms**: measure two long distances that pass through doorways, each from a wall
  in one room to a wall in another (for example from the far wall of the living room,
  through the door, to the far wall of the corridor). These check the stitched plan and the
  drift correction, and they are the only ground truth for how rooms sit relative to each
  other.

## Recording

- Photograph every reading with the laser display or the tape mark readable. Name the photo
  after the measurement (`living_W1.jpg`) and keep them with the YAML file.
- Draw a rough sketch of the property with the room names, wall labels and opening labels.
  A photo of a pencil sketch is fine.
- Do not round, and do not "fix" a number that looks odd. Re-measure it instead and keep
  both readings.

## What ground truth is not

Ground-truth files are never edited to make a result look better, and nothing in the
pipeline reads them. Only the benchmark scorer does.
