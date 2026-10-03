# 8. Photo tier and stitching

**In one sentence:** each photo gets metric depth from MoGe-2 and is levelled from its own
surfaces; a protocol (back against the middle of each wall, photograph the opposite wall,
walk clockwise) lets a small least-squares fit recover the room's width and depth and every
photo's position; rooms are then joined at matching doors.

## How it works

1. **One photo** (`frontend/views.py`). MoGe-2 gives a metric point map. The field of view
   comes from EXIF (the "35 mm equivalent" focal length), corrected for square and 16:9 crops,
   whose EXIF still describes the 4:3 frame (seen on real iPhone 15 Pro files; otherwise a
   square photo looks 15% wider than it is).
2. **Level it.** Up is the direction floor and ceiling normals agree with and wall normals are
   perpendicular to: one eigenvector problem. Then turn the view until its walls line up with
   the axes. Walls seen *through* an open door (behind another wall of this view) are dropped.
3. **Fit the room** (`frontend/room.py`). Unknowns: the room's width and depth, and per photo its
   position, its turn (a multiple of 90 degrees, from the protocol order) and its scale. Every
   wall a photo sees gives one equation, linear in all of them:
   `scale × (wall's distance in the photo) + (wall normal · camera position) = wall's place`.
   Solved by weighted least squares.
   - A photo that sees both side walls measures the distance between them by itself.
   - The wall behind the camera is never seen; the protocol puts the camera about 35 cm in
     front of it (sigma 15 cm). That is why depth-direction intervals are wider.
4. **Honesty checks** (`frontend/photo.py`), no ground truth needed:
   - `sides_seen`: a side no photo saw directly was placed by assumption, so the size along
     it is not measured;
   - `floor_outside`: the floor each photo shows, placed by the fit, must fit inside the fitted
     room (at most 15% outside). Photos taken from the middle of the room, close-ups or a
     wrong order spill out. Then the room is drawn but its size is **not measured**.
   Before these checks, real frames gave 1.9 x 1.6 m for a 3.2 x 3.7 m room, with tight
   intervals: confident garbage, which the brief says caps the score.
5. **Stitch** (`stitch.py`). Every door or passage is a candidate link. Two doors can be the
   same door only if widths and heights agree within their uncertainty. Joining at a pair
   fixes where the second room goes (doors face each other, a wall's thickness apart). All
   ways of joining are searched; placements where rooms overlap are thrown out; the best
   agreement wins. A join is also rejected if what was seen *through* each door does not fit
   the room placed behind it (a bedroom door shows the corridor's far wall 1.3 m away, not
   the living room's 4.5 m; tolerance 0.6 m or 40%). A room that cannot be joined is drawn
   beside the plan and flagged, never forced into a wrong place.

## Evidence

Synthetic protocol photos: walls within 1-2%. Real iPhone 15 Pro HEIC and JPEG files read
correctly (orientation, field of view). No real protocol photo set has been measured yet.
On the synthetic flat photographed by protocol v2: bedroom and living room join the corridor
correctly; the kitchen is left beside the plan, flagged; no wrong join.

## Weak spots

- Scale is MoGe's alone (6% sigma); nothing inside a room can detect a scale error.
- Rooms must be roughly rectangular for the fit; an L-shaped room is drawn as its rectangle.
- It depends on the protocol being followed; the checks catch when it was not, but then the
  answer is "not measured".

## Likely questions

- *Why not structure from motion on the photos?* 2-8 photos with little overlap give COLMAP too
  little to match; the protocol replaces overlap with known positions.
- *What if someone takes photos their own way?* The size is reported as not measured, with the
  reason, rather than a confident wrong number.
