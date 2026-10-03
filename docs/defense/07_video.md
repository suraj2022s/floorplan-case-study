# 7. Video tier

**In one sentence:** COLMAP recovers the camera path from the clip (accurate, but with no
metric scale and no "up"); MoGe-2 predicts metric depth for each frame; comparing the two
fixes the scale; the floor fixes "up"; then the same back-end runs.

## How it works (`frontend/sfm.py`)

1. **Frames:** 4 per second, shrunk to 960 px on the long side, at most 360.
2. **COLMAP** (via pycolmap): SIFT features, sequential matching (each frame with its
   neighbours) plus loop closure (80 frames spread through the clip, matched all against all,
   so a walk that comes back past what it saw is recognised), incremental mapping. Output: each frame's pose and the 3D points it sees, up to an
   unknown scale, plus the focal length.
3. **Pieces.** When COLMAP loses the track it starts a new model that re-uses up to 20 earlier
   frames. Shared frames have a pose in both models, which fixes scale, rotation and shift
   between them (Umeyama). A piece sharing fewer than 3 frames, or disagreeing by more than 5%
   of its size, is left out.
4. **Depth:** MoGe-2 (ViT-L, MIT licence) on every second registered frame, given COLMAP's
   focal length.
5. **Scale:** each frame's MoGe depth against the COLMAP points it sees; the median ratio over
   frames sets metres per COLMAP unit, and each frame is rescaled to agree. This removes MoGe's
   frame-to-frame scale noise (about 6%) but not its common bias.
6. **Level:** turn the scene so the floor is horizontal at z = 0.
7. Same back-end as LiDAR, with wider bands (depth from an image bows flat walls slightly), and
   a 5% scale sigma in every interval.

COLMAP's random choices are seeded and its result cached by the frames' content, so a rerun
replays the same poses.

## Why this way (decision 0003), measured on a real 60 s clip against ARKit's own path

| Camera path from | Error |
|---|---|
| depth and walls of each frame (our first tracker) | 0.89 m mean |
| MapAnything, learned multi-view | 0.36 m; 25 s a frame on this laptop's CPU |
| COLMAP global mapping | 0.23 m median |
| COLMAP incremental, loop pairs, pieces joined | **4.5 cm mean, over 85% of the walk** |

## Evidence

On that clip against the laser: walls +1.7% to +5.3% (2 of 4 within the 3% gate), ceiling
+18.7 cm (+7%), intervals 6/7 contain the truth. Run time about 4 min for 60 s of video.

## Weak spots

- MoGe reads about 5% long; that is the error. Calibration on our own benchmark removes a
  consistent bias, which is exactly what this is.
- A fast walk past bare walls splits the track; only joined pieces are used, and the plan
  reports how many frames were used. The protocol says walk slowly.

## Likely questions

- *Why not use the video's own depth?* An ordinary iPhone video has none; that is the point of
  this tier (any iPhone 15, not only Pro).
- *Why median, not mean, for scale?* Frames looking at a window or a mirror give wild ratios;
  the median ignores them.
- *Why does the ceiling come out 7% high?* The same depth-model bias, applied to height.
