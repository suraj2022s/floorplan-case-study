# Device matrix

Which tier runs on which hardware, what each tier delivers, and how much of that has been
measured. Every accuracy figure below says what it was measured on; where nothing has been
measured yet, it says so instead of guessing.

## Phones

| Tier | Phones | What the phone records | Tested with |
|---|---|---|---|
| LiDAR | iPhone 15 Pro, 15 Pro Max, and newer **Pro** models (the ones with a LiDAR scanner); iPad Pro 2020 and newer | Stray Scanner: video 1920 x 1440, LiDAR depth 256 x 192 in mm, confidence, ARKit camera poses and intrinsics, 60 frames a second | a real Stray Scanner recording from a LiDAR iPhone (format, pose convention); Apple's ARKitScenes iPad Pro LiDAR scans (accuracy) |
| Video | any iPhone 15 or newer, including non-Pro models | the Camera app's clip: HEVC or H.264, 1080p or 4K, often 10-bit HDR, portrait or landscape | a real iPhone 15 Pro clip (decoding, rotation); a 10-bit HEVC stream (decoding); the original video of an ARKitScenes iPad scan (accuracy) |
| Photos | any iPhone 15 or newer | HEIC or JPEG with EXIF (focal length, orientation), 0.5x, 1x or telephoto lens | real iPhone 15 Pro HEIC and JPEG files, a Live Photo (reading, orientation, field of view); synthetic protocol photos (geometry) |

The iPhone 16e has no 0.5x lens: the protocol falls back to 1x, which shows less floor and
ceiling per photo. No iPhone 15 or newer has been used to capture a benchmark room yet.

## The computer that runs the pipeline

| | Minimum tested | Notes |
|---|---|---|
| OS | Windows 11 | Linux and macOS builds of every dependency exist; not tried |
| GPU | none (CPU only) or NVIDIA with 4 GB | MoGe-2 ViT-L peaks at 2.3 GB, OWLv2 at 0.8 GB; never loaded together |
| RAM | 16 GB | |
| Disk | 8 GB | environment 3 GB, weights 2.3 GB, caches |

Run time on the development laptop (i7-12700H, RTX 3050 Ti 4 GB), per capture:

| Tier | Input | Time | Measured on |
|---|---|---|---|
| LiDAR | one room, 600 frames | 20 to 26 s | ARKitScenes bedroom, three scans |
| Video | one room, 60 s clip | about 4 min (COLMAP 100 s, depth 80 s) | ARKitScenes bedroom video |
| Photos | one room, 4 photos | about 10 s | synthetic and real frames |

## What each tier delivers

Measured against laser ground truth on the public-data benchmark (one real bedroom,
`reports/bench/arkitscenes/gates.md`), unless marked otherwise. These are iPad Pro numbers;
the iPhone numbers come from the benchmark session.

| | LiDAR | Video | Photos |
|---|---|---|---|
| Wall length error | -1 to -14 cm on the one scan scored (1.6% scale shortfall of the iPad, plus curtains taken for a wall); two scans not scorable yet | +1.7% to +5.3% on one clip (the depth model's scale bias) | within 1-2% on synthetic protocol photos; real photos: not measured yet |
| Ceiling height error | -2.6 to -3.8 cm, repeat spread 0.96 cm | +18.7 cm (+7%) | within 4 cm on synthetic photos |
| Openings within 2 cm | 0 of 11 (curtains hide a window's edges; leftover notches) | 0 of 2 | not measured |
| 90% intervals that contain the truth | 3 of 11 (too narrow) | 6 of 7 | not measured |
| Brief's gate for walls | (Round 1 table not in hand) | 3%: 2 of 4 walls | 8%: met on synthetic only |

What the tiers have in common, and why they differ: all three end in the same back-end, so
a room's outline, its openings and its intervals are computed the same way. They differ in
where depth and the camera's path come from. LiDAR has measured depth and ARKit's path;
video has a learned depth model scaled against COLMAP's path, so its scale is the depth
model's; photos have the depth model alone and the protocol's assumption of where each
photo was taken, so a photo room is measured only when its photos show every wall.
