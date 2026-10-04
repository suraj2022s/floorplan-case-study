# Runs on the supplied sample data

The assessment email asked us to run the code on its sample data: three Stray Scanner
recordings made with a LiDAR iPhone. This folder holds, unedited, what one command produced
for each. **No tape or laser measurements came with the recordings**, so these runs show
whether the pipeline holds up on real iPhone captures it had never seen. They do not show how
accurate it is; accuracy against a laser is in [reports/bench/](../bench/).

## Reproduce

```
uv run python scripts/fetch_supplied.py        # 0.9 GB from the email's Drive folder, SHA-256 checked
uv run floorplan run captures/supplied/c00a170fe1 --out out/samples/single_room
uv run floorplan run captures/supplied/1a8384c3f6 --out out/samples/single_scan_floor_only
uv run floorplan run captures/supplied/c7d28f72c6 --out out/samples/single_scan_with_ceiling
```

The zips can also be given to `floorplan run` as they are. On our laptop (RTX 3050 Ti, 4 GB),
the three runs took 18 s, 100 s and 163 s (`run_log.json`, `total_s`). `plan.json` follows
[schema/plan.schema.json](../../schema/plan.schema.json), and `tests/test_schema.py` checks
these three files against it.

## The recordings

| Zip | Scan | Frames | Length | Walk | What it shows (12 evenly spaced frames) |
|---|---|---|---|---|---|
| `single_room.zip` | `c00a170fe1` | 1,715 | 37 s | 14 m | A small sitting room (television, fridge, sofa, wardrobe), the corridor outside it and a bathroom; the phone is level or aimed down, the ceiling hardly in view. [frames.jpg](single_room/frames.jpg) |
| `single_scan_floor_only.zip` | `1a8384c3f6` | 5,251 | 115 s | 54 m | A floor of a home: kitchen, bathrooms, rooms with curtains, a staircase; the phone is aimed at the floor and the foot of the walls throughout. [frames.jpg](single_scan_floor_only/frames.jpg) |
| `single_scan_with_ceiling.zip` | `c7d28f72c6` | 9,745 | 215 s | 100 m | A floor of a home, walked with the phone tilted up so that walls and ceilings are captured. [frames.jpg](single_scan_with_ceiling/frames.jpg) |

The three appear to be of the same home: the same fridge, with the same magnets, and the same
bathroom appear in all three. The pipeline does not know this, and each plan has its own
coordinate frame, so they are not compared with each other here.

## Results

Areas in m², heights in m, each with its 90% interval (± half its width). "Inferred" means
some wall bounding the room was seen over less than 30% of its length, so its position comes
from the walls around it, with a wider interval.

### single_room (`c00a170fe1`)

![plan](single_room/plan.png)

| Room | Floor area | Ceiling | Walls (inferred) | Openings |
|---|---|---|---|---|
| room_1 | 7.5 ± 1.0 (inferred) | not measured | 4 (4) | 3 doors |
| room_2 | 7.6 ± 0.5 | not measured | 4 (0) | 2 doors |

Footprint 15.1 ± 1.3 m². room_2 is probably the bathroom: a 0.55 m "window" in its far wall
was dropped because the detector saw a television screen there; most likely it was the
shower's dark glass, which a depth sensor also sees through. Dropping it was right, the reason
given probably not. No damage regions, although this bathroom has a real hairline crack: see
finding 4.

### single_scan_floor_only (`1a8384c3f6`)

![plan](single_scan_floor_only/plan.png)

| Room | Floor area | Ceiling | Walls (inferred) | Walls < 0.3 m | Openings |
|---|---|---|---|---|---|
| room_1 | 21.1 ± 2.3 (inferred) | not measured | 27 (24) | 8 | 5 doors, 1 passage, 3 windows |
| room_2 | 5.1 ± 1.4 (inferred) | not measured | 6 (5) | 0 | 3 doors, 1 passage |
| room_3 | 2.2 ± 0.7 (inferred) | not measured | 6 (6) | 0 | 4 doors, 1 passage |
| room_4 | 6.5 ± 1.0 (inferred) | not measured | 11 (10) | 3 | 2 doors, 2 passages |
| room_5 | 3.8 ± 0.5 (inferred) | not measured | 16 (14) | 9 | 6 doors |
| room_6 | 3.1 ± 0.4 (inferred) | not measured | 10 (7) | 2 | 2 doors, 2 windows |
| room_7 | 4.6 ± 0.6 (inferred) | not measured | 12 (12) | 6 | 3 doors, 1 window |

Footprint 46.4 ± 3.7 m². No damage regions. One space seen through an opening but not walked
into is left out, and the plan says so.

### single_scan_with_ceiling (`c7d28f72c6`)

![plan](single_scan_with_ceiling/plan.png)

| Room | Floor area | Ceiling | Walls (inferred) | Openings |
|---|---|---|---|---|
| room_1 | 8.8 ± 0.5 | 2.95 ± 0.07 | 5 (0) | 2 doors |
| room_2 | 21.1 ± 1.8 (inferred) | **2.28 ± 0.06** | 6 (5) | 1 door, 1 passage, 1 window |
| room_3 | 9.3 ± 0.5 | 3.07 ± 0.08 | 5 (0) | 2 doors |
| room_4 | 9.8 ± 0.5 | 3.08 ± 0.08 | 5 (0) | 2 doors |

Footprint 49.0 ± 2.9 m². No damage regions. Two spaces seen through openings but not walked
into are left out, and the plan says so.

### The video tier on the same recordings

Each recording also holds the iPhone's video (`rgb.mp4`), so the video tier was run on it too
(`uv run floorplan run captures/supplied/<scan> --tier video`; plans in `<recording>/video/`).
There is no tape truth, so each video plan is compared with the LiDAR plan of the same walk.

| Recording | Frames placed by the camera tracker | Video plan | LiDAR plan |
|---|---|---|---|
| single_room | 25 of 143 (17%), in 6 pieces | 1 room, 2.30 m² | 2 rooms, 15.1 m² |
| single_scan_floor_only | 82 of 350 (23%), in 18 pieces | 1 room, 1.25 m² | 7 rooms, 46.4 m² |
| single_scan_with_ceiling | 22 of 348 (6%), in 13 pieces | 1 room, 2.26 m² | 4 rooms, 49.0 m² |

**On these recordings the video tier fails.** They were made for LiDAR, turning fast; with
video alone the camera tracker (COLMAP) loses the camera on the turns and splits the walk into
pieces it cannot join, and only the largest piece is measured. The plans now say so in their
first warning ("the camera could be followed for only 23% of the clip ... the plan covers
only that part of the walk"); before that check was added (commit after `9fa65d4`), the
floor-only plan reported a 1.25 m² room for a whole floor without saying why. On the
benchmark's real clip, walked slowly, the tracker placed 200 of 241 frames (83%). Our capture
protocol asks for a slow walk and smooth turns for this reason; whether that is enough on an
iPhone is untested.

## Findings

1. **A false ceiling, found.** room_2 of `c7d28f72c6` measures 2.28 m against 2.95-3.08 m in
   the other rooms. The frames looking up in that room ([false_ceiling.jpg](single_scan_with_ceiling/false_ceiling.jpg))
   show why: an access hatch in a lowered ceiling, and a step up to a higher ceiling at its
   edge. The room has two ceiling levels; the plan reports one height per room (the
   strongest ceiling plane), so the higher level is not reported.
2. **No ceiling, said so.** Two recordings hardly look up. Their plans report every ceiling
   height, and the height of every opening whose top was never seen, as not measured
   (`null`, with `basis: not_measured`), never a guess, and print the fix: "no ceiling
   found: tilt the phone up so the ceiling is captured".
3. **Filmed low, the outline is noisy.** In `1a8384c3f6` the walls were seen mostly at their
   foot, so most walls are inferred and the outlines are jagged (27 walls
   in room_1, 28 shorter than 0.3 m in all). The intervals widen accordingly (room_1: ±2.3
   m²). We tried straightening steps of up to 25 cm instead of 12 cm: the short walls fell
   from 28 to 15, but on the laser-measured benchmark room the area error grew from +0.38 to
   +0.57 m², so 12 cm stayed (commit `c001417`). Our capture protocol asks for the phone at
   chest height, with one slow turn tilted up to where the walls meet the ceiling.
4. **Damage: two false regions fixed, one real crack missed.** The home has one real defect we
   know of: a hairline crack on the bathroom wall above the cistern, in view for about 1.1 s of
   `c00a170fe1` (28.4-29.5 s, [bathroom_crack.jpg](single_room/bathroom_crack.jpg)). We first
   wrote that the rooms looked undamaged; another candidate's public write-up pointed at the
   crack and we confirmed it in the video. The detector (OWLv2, open-vocabulary, threshold
   0.20) put 108 boxes on surfaces across the three recordings, and requiring each region to
   be seen in two frames left two, both wrong ([damage_false_positives.jpg](damage_false_positives.jpg)):
   - a **pot plant taken for mould** on a wall (0.59 m², two concealed-damage flags and five
     scope lines). Fixed: damage is part of a surface, so at least half of the depth points in
     a box must lie within 3 cm of one plane parallel to it. Bare walls and floors score
     0.9-1.0; the plant 0.06 and 0.10 (commit `7660e74`).
   - the **edge of a shower door frame taken for a 0.30 m floor crack**. Fixed: every damage
     class is wall damage by its own phrase ("crack in the wall"), so boxes landing on the
     floor are ignored; on these recordings all of them were mats, rugs, a pet mat or the foot
     of a shower screen (commit `2d1d205`).
   - the **real crack is missed.** The detector scores it 0.30-0.47 on the frames that show
     it, but of the 40 frames examined only one falls in that 1.1 s, and a region needs two
     views. Examining the frames either side of each candidate finds it on all three
     recordings, but also confirms a dark shower screen as mould (0.45) and a small wall
     fixture as a water stain (0.48), both above the crack's score: no threshold separates
     them, and inventing damage is worse than missing a glimpse. The capture protocol (v3) now
     asks for any damage to be shown for 2 s from 1.5 m, then again after a step sideways.
5. **Doorways filmed low were called windows.** A doorway whose top is never seen has no
   measured height, and the two sides of a doorway, merged into one opening, were classed
   by that height alone: two doorways joining rooms in `1a8384c3f6` came out as 0.6-0.9 m
   windows standing on the floor. Fixed (commit `d6c0b8f`).
6. **Very wide "doors".** In `c7d28f72c6`, three openings 1.7-2.5 m wide and 2.7-2.9 m tall
   are reported as doors (`room_1-D2`, `room_3-D1`, `room_4-D2`). At that size they are more
   likely glazed sliding doors or open bays; depth alone does not tell which.
7. **Not every room is linked.** In `c7d28f72c6` only room_1 and room_2 are joined
   (`adjacency`); the doors of room_3 and room_4 open onto space that was not walked into
   (the plan says two such spaces are left out), so the links through it are missing.
8. **A room walked into was dropped; fixed.** Space seen through a doorway is taken out of the
   room in front; it was kept as a room of its own only if 20% of the whole walk was in it, a
   share set on one-bedroom scans. In `1a8384c3f6` a 5.1 m² room with 2.8 m of walk in it was
   dropped. Now 1.5 m of walk inside is what counts: the scan goes from 6 rooms and 41.3 m² to
   7 rooms and 46.4 m² (other public runs of this scan report 48-51 m²), while the hall seen
   from the door of the laser-measured bedroom (0.8 m of walk) is still left out (commit
   `3f9e6dd`).

## Limitations

- **No ground truth.** Nothing here is checked against a tape or laser. The numbers are the
  pipeline's measurements with their stated intervals, nothing more.
- **Intervals are not calibrated** for the LiDAR tier; every plan says so in its warnings.
  On the public laser-measured benchmark, 6 of 11 LiDAR intervals contained the laser's
  value: they are still too narrow.
- **One ceiling height per room**, as finding 1 shows.
- **Rooms are numbered, not named** (no "kitchen" or "bathroom").
