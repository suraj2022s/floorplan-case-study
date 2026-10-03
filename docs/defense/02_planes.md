# 2. Floor, ceiling and walls

**In one sentence:** because the world frame is gravity-aligned, finding planes becomes
one-dimensional: floor and ceiling are peaks in a histogram of heights, and each wall face is
a peak in a histogram of distances along the direction it faces.

## How it works (`geometry/planes.py`)

1. **Floor.** Take the up-facing points and histogram their heights in 2 cm bins. The floor is
   the *lowest* strong peak (beds and tables sit above it). A peak must hold at least 20% of
   the largest one and at least 300 points (about 0.2 m²).
2. **Ceiling.** Same with down-facing points; the *highest* strong peak (table undersides and
   door heads sit below it). If there is none, the plan says "no ceiling found: tilt the
   phone up" and reports every ceiling height as not measured.
3. **Each level is refitted** on the points within 6 cm of its peak as a slightly tilted plane
   `z = ax + by + c`, by robust least squares. The histogram only chooses the points; the fit
   sets the height.
4. **Walls.** Take the side-facing points (normal at most 0.3 vertical, more than 10 cm above
   the floor, so skirting is ignored). Find the main directions walls face. For each
   direction, histogram the points' distances along it in 1 cm bins; each peak is a wall face.
   Refit each as a line by total least squares on the points within 3 cm.
5. **A wall must be a wall.** It must reach within 45 cm of the ceiling and never less than
   2.15 m high. Door leaves stop at 2.0-2.1 m and most wardrobes below the ceiling. It needs
   250 points, 35 cm of supported length, and a fit rms under 2.5 cm (real phone walls come
   out at 1.2-1.4 cm).
6. **Clutter is pruned** (`prune_clutter`), found on the first real scan, where curtains, a
   window reveal and a door frame each made their own line:
   - *direction:* rooms are mostly square; a line more than 6 degrees off both main directions
     is kept only if long (1.2 m) and well supported;
   - *shadow:* a weak line within 45 cm of a much stronger parallel line, overlapping it, is
     something in front of that wall. The strong line is the wall.
7. **Copies are merged:** two lines facing the same way within 8 cm and 3 degrees, overlapping,
   are one wall seen twice. Lines side by side are a real step and are kept.

## Why this way

- RANSAC on 3D points would also work, but the gravity-aligned frame makes histograms simpler,
  deterministic and easy to debug: one plot shows every candidate wall.
- Millimetre plane positions come from fitting thousands of points; no single depth reading
  is that good.

## Weak spots

- **Curtains** in front of a wall pass every test (they are tall and fairly flat) and are taken
  for the wall: on the public bedroom 12 cm short. The interval is widened by the surface's own
  scatter (curtains 20-50 mm, plain walls 7-9 mm), but the error remains.
- **One ceiling per room** is reported (the strongest plane), so a room with a false ceiling
  over part of it gets one height (seen on the supplied sample data: 2.28 m in one room).
- A capture aimed low (no wall tops) fails the height test; a relaxed retry accepts surfaces
  reaching 1.5 m and warns that furniture may have been taken for walls.

## Likely questions

- *Why least squares after the histogram?* The histogram bin is 1-2 cm; the fit over thousands
  of points places the plane to millimetres.
- *Why not take the lowest points as the floor?* Noise and reflections put stray points below
  the floor; a peak needs many points to agree.
- *How do you tell a wardrobe from a wall?* Height (it stops below the ceiling) and, if it
  survives that, the shadow test (weaker and in front of a stronger wall).
