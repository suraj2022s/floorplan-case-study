# Benchmark session: one visit, everything the brief asks for

About two hours with an iPhone 15 Pro (or any newer Pro model) and a laser measurer or a
steel tape. The order matters: ground truth first, while the rooms are untouched; captures
next; the consumer app last.

## What the brief requires, and how this session covers it

| Requirement | Covered by |
|---|---|
| A multi-room capture: 3+ rooms plus a connector | the whole property, steps 3 to 5 |
| A furnished room with staged damage of two classes | step 1 |
| The same rooms at all three tiers, multi-room included | steps 3, 4, 5 |
| One room captured twice at the same tier | the "repeat" captures in steps 3 to 5 |
| Laser or tape ground truth on everything | step 2 |
| Head-to-head on 2 rooms against a consumer app | step 6 |
| Raw data, measurements and app exports submitted | step 7 |

## 0. Before you start (10 min)

- Install **Stray Scanner** and **Polycam** (free tier) from the App Store. Write down both
  version numbers (App Store page, or the app's settings).
- Charge the phone. Free 5 GB of storage.
- Choose the property: at least three rooms and a corridor or hall joining them.

## 1. Stage the damage (10 min), in one furnished room

Two classes, both removable, both on surfaces the captures will see:

- **Water stain:** brush diluted tea on a sheet of plain paper, let it dry to a brown ring,
  tape it flat to the ceiling near a corner, or low on a wall.
- **Crack:** draw a jagged 40-60 cm line with a soft pencil on a strip of masking tape stuck
  to a wall near a door or window frame.

## 2. Ground truth (40 min)

Follow `bench/GT_PROTOCOL.md` exactly and fill in a copy of `ground_truth/TEMPLATE.yaml`:
every wall, three ceiling heights per room, every opening, both diagonals of each room, two
distances across rooms through doorways, and each staged damage's size and position.
Photograph every reading.

## 3. LiDAR captures (15 min)

Follow `docs/capture_protocol.md`, section 3a, with Stray Scanner.

1. **Whole property** in one recording.
2. **Repeat:** the furnished room alone, a second time.

## 4. Video captures (15 min)

Section 3a again, with the Camera app.

1. **Whole property** in one clip.
2. **Repeat:** the furnished room alone.

## 5. Photo captures (20 min)

Section 3b: one folder per room, 4 photos per rectangular room, corridor from both ends.

1. **Every room.**
2. **Repeat:** the furnished room, a second set of 4.

## 6. Consumer app (15 min)

Polycam, free tier, LiDAR room mode: scan **the furnished room and one other room**. Export
the floor plan with its dimensions (PDF and, if offered, JSON or DXF). Note the app version.

## 7. Hand over (15 min)

Into `captures/<property>/` on the laptop:

```
captures/<property>/
    lidar-all/            Stray Scanner recording (folder or .zip)
    lidar-repeat/
    video-all.MOV
    video-repeat.MOV
    photos-all/<room>/    one folder per room
    photos-repeat/<room>/
    polycam/              the app's exports, and a note of the app version
    ground_truth.yaml     plus the reading photos and the sketch
```

Then run each capture once (`uv run floorplan run captures/<property>/lidar-all`, and so on)
and read the warnings before leaving: a room reported as not measured is retaken now, not
tomorrow.
