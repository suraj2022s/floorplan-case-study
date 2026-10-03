# 4. Doors, windows and passages

**In one sentence:** every depth pixel of every frame taken in a room is a ray; where it
crosses each wall, the sensor either hit the wall, saw through it, was blocked in front of
it, or got nothing back. A compact region of see-through rays is an opening, measured
between its jamb faces.

## How it works (`geometry/openings.py`)

1. **A map per wall** on a 2 cm grid (along the wall x up the wall).
2. **Cast every pixel's ray** (every second pixel) from each frame taken inside the room at
   each wall within 4.5 m. Where the ray crosses the wall plane, compare with what the sensor
   measured along it:
   - *hit:* the measured point is within 3 cm of the wall: solid wall;
   - *open:* the measured point is 8 cm or more behind the wall: the ray went through a hole;
   - *blocked:* the measured point is in front of the wall: furniture hides that spot;
   - *void:* nothing trustworthy came back (glass, or open space beyond range).
3. **Regions.** A compact region where open rays dominate is an opening: at least 40 x 40 cm,
   filling 55% of its bounding rectangle, with 10% see-through rays. A region of void with
   nothing in front of it can also be one (glass), if it is a clean rectangle.
4. **Width from the jamb faces.** The jambs are the narrow surfaces lining the sides of the
   opening. They are planes, so their position comes from a fit over many points, not from
   the ragged edge of the open region. If a jamb face was not seen well, the edge of the open
   region is used instead and the interval is wider (`width_method` says which).
5. **Kind.**
   - sill above 15 cm, or height under 1.6 m: **window**;
   - from the floor nearly to the ceiling: **passage**;
   - otherwise **door**;
   - if the top was **never seen** (nothing observed on the wall just above it): its height is
     not measured, and on the floor it is a door (a passage if wider than 1.6 m). This came
     from the supplied sample scans, filmed low, where doorways became "windows" 1.3-1.6 m tall.
6. **Twins.** A door between two rooms is found from both sides; the two records are merged,
   widths combined by inverse-variance weighting (the better-seen side counts more), and the
   top counts as seen if either side saw it (fixed on 3 October; before, the merge ignored that).
7. **Linking.** The room on the far side is found by stepping outward from the opening; the
   distance gives the wall thickness, and the pair goes into `adjacency`.

## Why this way

- Keeping *blocked* separate from *open* is what stops a wardrobe in front of a wall looking
  like a doorway: nothing was seen on the wall there, but nothing was seen through it either.
- Jamb faces give centimetre widths from a fit; the depth image edge is a few centimetres
  ragged at 256 x 192.

## Weak spots (the gate fails: 1 of 10 on the public scans)

- The public scans' doorway was hardly looked at (mostly unseen, partly blocked by the open
  leaf), so it was missed in all three. The protocol now asks to show each doorway for 2 s
  from 1.5 m; only a protocol capture will tell if that is enough.
- Curtains hide a window's true edges, so its width is measured between the curtains.
- Mirrors and dark screens read as holes to a depth sensor; the image detector drops openings
  where it sees a mirror or a television (on a sample scan, a shower's dark glass was dropped
  this way, under the name "television").
- Very wide openings with a seen top (2.3-2.5 m wide, 2.7-2.9 m tall on a sample scan) are
  called doors; they are probably glazed sliding doors. Depth alone cannot tell.

## Likely questions

- *Why 3 cm and 8 cm?* LiDAR noise is millimetres at room range; 3 cm absorbs fit error. A ray
  must clearly pass the wall (8 cm, more than a thin wall's face noise) to count as through.
- *How do you score a missed door?* The gate counts a missed opening and a phantom opening
  each as a miss, as the brief says.
