# 3. Rooms

**In one sentence:** every wall face is extended into an infinite line, the lines cut the floor
into cells, cells with evidence of being inside are kept, and neighbouring cells are glued
together unless a wall separates them; each glued group is a room.

## How it works (`geometry/layout.py`, `find_rooms`)

1. **Cut.** Extend every wall line across a working area (the walls plus 60 cm). The lines
   cut it into convex cells (a "cell complex", like cutting a cake with straight cuts).
2. **Borders.** For each border between two cells, record which wall line it lies on and how
   much of it has real wall seen on it (coverage).
3. **Inside or outside.** A cell is inside if either:
   - at least half of it has evidence: floor or ceiling points over it (on a 5 cm grid), or
     the phone itself passed through it (25 cm around the path), or
   - wall faces looking into it add up to 30 cm. Walls are only ever seen from inside a room,
     so the side a wall faces is inside, even behind a wardrobe.
   Cells touching the edge of the working area are outside.
4. **Glue.** Two inside neighbours join unless their border has wall on 15% of its length.
   A doorway does not join two rooms: there is wall beside and above it. Since round 1 of the
   fix loop, a stretch of a wall line with real wall on *both* sides within 3 m (a gap in a
   wall: a door, a window) never joins cells either.
5. **Furniture footprints.** A glued region under 2.5 m² that the phone never entered is the
   footprint of tall furniture; it goes back to the room it borders most.
6. **Opaque walls** (round 2 of the fix loop, `_split_behind_walls`). A wall seen to full
   height over a good length with little scatter is opaque. Floor seen *behind* it was seen
   through its door or window. That space is a separate room if the walk went there (20% of
   the path), otherwise dropped.
7. **Clean-up.** Regions under 1 m² are dropped; small steps under 12 cm between parallel walls
   are straightened (`_remove_jogs`); spaces only glimpsed through a door are not measured (and
   the plan says so); rooms are numbered in the order the phone first entered them.
8. **Refine** (`refine_room`). The cell complex decides *which* walls a room has; each wall is
   then refitted on its own points between its corners, and the corners are recomputed as
   intersections of the refitted lines.

## Why this way

- **Not tracing the floor's outline:** furniture hides the bottom of walls, so the floor
  outline follows the furniture. Here a wall only needs to be seen somewhere along its length
  and height; the line supplies the rest.
- **Corners are exact intersections** of fitted lines, not pixel edges, so a wall's length is
  set by two well-measured planes.

## Weak spots

- **A wall never seen** is not a line, so the cells beyond leak. Then the room is drawn with a
  fallback rectangle around what was seen, the unseen sides dashed and given a 15 cm sigma.
- **Filmed low** (supplied scan `1a8384c3f6`): walls are seen only at their foot, most are
  inferred, and outlines are jagged (28 walls under 0.3 m). We tried straightening steps up
  to 25 cm: 28 short walls fell to 15, but on the laser-measured bedroom the area error went
  from +0.38 to +0.57 m², so 12 cm stayed. The data, not the plot, decided.
- **A door next to a corner hidden by furniture** can still leak.

## Likely questions

- *How many cells?* Tens to hundreds; each test is cheap (shapely polygons, a union-find).
- *Why 15% wall share?* Below it, a border is mostly open floor that happens to lie on a wall
  line (an L-shaped room's extension); above it, there is real wall.
- *What is round 1 / round 2?* The fix-loop rounds: round 1 stopped joining across gaps in
  walls; round 2 made seen walls opaque. Round 2's root cause was right (leaks went from
  +3.9 m² to +0.4 m²), but the openings gate did not move.
