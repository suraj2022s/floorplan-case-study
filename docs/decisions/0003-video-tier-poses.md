# 0003: Camera poses for the video tier

Date: 2026-10-03. Status: adopted.

## Context

A walkthrough clip has no poses and no depth. Depth per frame comes from MoGe-2 (decision
0001). The camera path must come from the images. Everything here was measured on the one
real clip available without an iPhone: Apple's ARKitScenes scan 47333462, a 60 s iPad Pro
walkthrough of a bedroom (1920 x 1440, 60 frames a second), whose ARKit poses serve as the
reference for the path and whose laser scan serves as ground truth for the room
(`bench/benchmarks/arkitscenes.yaml`).

## Options tried, in order, with what they measured

| Approach | On the real clip | Verdict |
|---|---|---|
| Follow the camera from each frame's depth and the walls in it (plane fits + ICP) | path 0.89 m off on average over 12.8 m; 33 of 120 frames showed no usable wall | rejected |
| MapAnything, Apache-2.0 checkpoint (learned multi-view poses and depth) | 4.9 GB, CPU only on a 4 GB GPU, 25 s per frame; on 24 frames positions 0.36 m off (after the best similarity fit), rotations 9.9 degrees off (median) | rejected |
| COLMAP, global mapping (GLOMAP) | one piece with all frames, but 23 cm median and 6 m worst position error | rejected |
| COLMAP, incremental mapping, default settings | where it holds the track, 1 cm median position error and 0.7 degrees rotation error; but the clip splits into 4 to 6 pieces and only 35% of it is used | not enough alone |
| ... plus loop-closure pairs, registration on fewer matches, and joining the pieces through the frames they share | 200 of 241 frames (85% of the walk) in one frame; position error 4.5 cm mean, 15.8 cm worst | **adopted** |

## Decision

`frontend/sfm.py`: frames at 4 a second, 960 px; COLMAP incremental mapping with SIFT,
sequential matching plus all-against-all matching of 80 frames spread through the clip,
registration on 15 inliers; separate models joined by a similarity fit on shared frames.
MoGe-2 predicts depth for every second placed frame, given COLMAP's focal length. Each
frame's depth is compared with the COLMAP points it sees; the median ratio over frames gives
metres per COLMAP unit, and each frame's depth is rescaled to agree with the reconstruction.
The frame is levelled from the surfaces' normals, the floor put at z = 0, and the result goes
through the same back-end as a LiDAR capture.

COLMAP is seeded and its result cached by the frames' content and the method's version, so
a rerun replays the same poses.

## Result and what is left

On the clip, against the laser: walls +1.7%, +2.6%, +4.0%, +5.3%; ceiling +7.0%; every
wall's 90% interval contains the truth. The error is almost entirely the depth model's
scale, which reads long (+5% measured against LiDAR on 40 frames earlier). That is a bias,
not noise, and calibrating it is what the iPhone benchmark is for; until then the interval
carries a 5% scale uncertainty.

Known failure: a fast walk past bare walls or close to furniture breaks the track into pieces
that share no frames, and only the largest is used. The capture protocol asks for a slow walk
with walls and furniture in view; the plan says how much of the clip was placed.
