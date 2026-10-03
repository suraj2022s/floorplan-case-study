# 1. Capture, tiers and the point cloud

**In one sentence:** every input, whatever the phone produced, becomes the same `Capture`
(frames with a pose, a metric depth map and their uncertainty), and the frames become one
clean point cloud.

## How it works

1. **Finding the capture** (`io/intake.py`). The user points at whatever the phone gave
   them: a zip, a folder inside a folder, a single clip, photo folders with Live Photo clips
   and Mac junk files (`__MACOSX`, `._IMG.HEIC`). Intake finds the real files and names the
   tier: a Stray Scanner folder is LiDAR, a clip is video, folders of images are photos.
   `--tier` can force it.
2. **Reading a Stray Scanner recording** (`io/stray.py`). It holds `rgb.mp4`, one 16-bit
   depth PNG per frame in millimetres (256 x 192), a confidence PNG (0, 1, 2), and
   `odometry.csv` with each frame's position and quaternion. The only conversion is turning
   ARKit's y-up world into our z-up world.
3. **The pose convention was checked, not assumed.** The app's source writes ARKit's
   orientation times a half turn about x, so the camera axes are already OpenCV style. On a
   real recording: as written, a worktop is level within 3 degrees and two frames 23 degrees
   apart agree to 3 mm; with the extra flip the recording's notes suggest, the worktop is
   upside down and the frames 12 cm apart. A test fails if this is changed.
4. **Keyframes** (`capture.py`). A phone records 60 frames a second. A frame is kept only
   when the camera moved 5 cm or turned 4 degrees since the last kept one, so the result does
   not depend on walking speed.
5. **Point cloud** (`geometry/cloud.py`). Each depth pixel is pushed into 3D with the
   intrinsics and pose. Dropped first: confidence below 2, closer than 0.25 m or farther than
   4.5 m, and depth edges (a pixel straddling a near and a far surface reports a distance
   that belongs to neither). Points are averaged in 2.5 cm voxels, separately for up-, down-
   and side-facing points, so the floor and the foot of a wall stay apart.
6. **Fragments.** Short runs of frames (about a second) become small clouds of their own. The
   poses inside one fragment are trusted; drift correction moves whole fragments.

## Why this way

- One `Capture` for every tier means one back-end and one output contract. The tiers differ
  only in where depth and poses come from and how uncertain they are.
- Stray Scanner (a stock app, Route 2) because no Mac was available to build an app, and its
  source is public, so its format could be verified.

## Weak spots

- The LiDAR depth sigma (2 mm + 0.25% of distance) and scale sigma (1.5%) are starting values;
  the 1.5% was set from the iPad's measured shortfall, not an iPhone's.
- Only the highest-confidence depth is used; on dark or shiny surfaces that can leave gaps.

## Likely questions

- *Why voxel averaging?* A wall seen in 300 frames would otherwise be 300 noisy copies;
  averaging gives one clean layer and cuts the point count.
- *Why separate the facing classes in a voxel?* Averaging a floor point with a wall point in
  the same corner voxel gives a point that is neither. An earlier version split by compass
  direction too and biased wall normals by about 7 degrees; now only up/down/sideways.
- *What if the capture is a zip?* It is unpacked once and reused.
