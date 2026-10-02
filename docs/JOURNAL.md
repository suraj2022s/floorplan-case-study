# Journal

Short, dated notes on what was done and why. Times are IST.

## 2026-10-02 (Fri)

- **21:45** Repo created. Deadline is Sunday 2026-10-04, 19:00, so about 45 hours remain.
- No iPhone is available yet. Every row that needs a real capture is marked Blocked in
  `COMPLIANCE.md`. Until a phone arrives the pipeline is built and tested on synthetic rooms
  with known dimensions. Synthetic results are development evidence only and will not be
  reported as benchmark numbers.
- Round 1 gate table and JSON schema are still to be added under `spec/`.
- Laptop checked: Dell G15 5520, i7-12700H, 15.7 GB RAM, RTX 3050 Ti with 4 GB VRAM.
  The 4 GB limit drives the model choices; see `docs/decisions/0001-starting-decisions.md`.
- **22:05** Checked the capture app instead of assuming. Stray Scanner 1.4 is on the App
  Store (free, iOS 18.6+). Its `OdometryEncoder.swift` multiplies the ARKit orientation by a
  half turn about x before writing, so poses are already in the OpenCV camera convention.
  Flipping the camera axes again at ingest, as an early plan suggested, would have mirrored
  every scene. The reader converts the world frame only, and a test derived from the app's
  source pins this down.
- **22:40** Dependency install was crawling at 20 to 100 kB/s. Measured the line: about
  100 kB/s per connection to the package host, about 1 MB/s over eight connections. Wrote
  `scripts/fetch.py` (parallel byte ranges, SHA-256 verified) and fetched the three large
  wheels in 3 minutes, checking each against the hash in `uv.lock`.
- **22:50** First end-to-end run on the synthetic box room: walls 3.3500 and 4.2000 m
  (exact), ceiling 2.7399 m (truth 2.74), window 1.2007 m (truth 1.20).
- **23:00** The first drift-correction stage (ICP pose graph) moved poses by up to 32 cm on a
  capture with no drift. Replaced with plane-anchored correction; see
  `docs/decisions/0002-drift-correction.md`.
- **23:10** Four-room flat came out with tilted and duplicated walls. Cause: when merging
  depth points into voxels, points were binned by the compass direction of their normal, in
  30-degree sectors. A wall facing exactly along a sector boundary was split into two
  populations by the sign of its normal noise, each averaging to a normal about 7 degrees
  off. Wall directions were then wrong by 7 degrees, which smears a 4 m wall over 47 cm in
  the distance histogram. Fix: bin by up / down / sideways only, and take each facing
  direction from the strongest fitted wall rather than from point normals.
- **23:20** Synthetic flat (3 rooms + corridor, 1385 frames) end to end from one command:
  16 walls within 1.5 mm, 4 doors and 2 windows within 6 mm, adjacency correct, footprint
  42.396 m² against 42.404 m². These are synthetic results: they show the geometry code is
  right, not that it works on a real sensor.
- **23:35** Benchmark scorer written. It runs each capture through the public command in
  its own process and scores only the files that run writes. Ground truth is coordinate-free
  (a tape gives lengths, not positions), so the scorer works out which predicted room and
  which wall is which from lengths and opening positions.

## 2026-10-03 (Sat)

- **00:00** Photo tier, first version. Depth from MoGe-2: 0.8 s per image and 2.25 GB peak
  on the laptop's RTX 3050 Ti, so it fits the 4 GB card. Each photo is levelled from its own
  surface normals; the views of a room are fitted to one rectangle by least squares. On
  synthetic photos with 3% scale error each, three of four rooms came out within about 3%.
  Problem found: a photo also shows walls of the next room through an open door, and those
  were being fitted as walls of this room. Fixed by dropping walls that lie behind another
  wall of the same view.
- **01:00-02:30** Video tier, first version: camera path recovered from depth frames and the
  walls they see. Worked on a synthetic single room (walls within 1%). On the synthetic
  four-room walk it held position to 5-25 cm for most of the path but slipped at doorways.
- **02:45** Damage, concealed-damage rules and scope items in place, with OWLv2 as the
  detector (0.4 s per image, 0.76 GB). On two undamaged indoor images every damage phrase
  scored 0.14 or lower, under the 0.20 threshold. Not yet tried on real damage.
- **03:00** First real data. With no iPhone available, ran the LiDAR tier on a bedroom from
  ARKitScenes (Apple's public iPad LiDAR scans). It produced a sensible room straight away:
  main walls 3.06 / 3.6 / 3.6 m, ceiling 2.607 m. The window end, with curtains, a reveal
  and a view outside through the glass, produced a zig-zag outline and unstable openings.
  Added clutter pruning. There is no ground truth for this scan, so "better" here means
  "looks right against the RGB frames", nothing more.
- **03:05** Measured the depth model against LiDAR on 40 frames of that scan: it reads 5.2%
  long on average with 6.1% frame-to-frame spread. This is the dominant error at the photo
  and video tiers and it replaces the guessed 3-5%.
- **03:08** The video tracker fails on real footage. On the RGB frames of the real scan the
  recovered path was off by 0.9 m on average over a 12.8 m walk; 33 of 120 frames showed no
  usable wall (close-ups of furniture); the plan was unusable. Clean synthetic rooms had
  hidden this. Decision: use a learned multi-view model (MapAnything) for poses.
- **03:10** Searched for existing projects. Two public repositories are submissions for
  this same case study; their READMEs were read only to recognise what they were, and none
  of their code is used. Useful open-source finds: MapAnything (poses and metric depth from a
  set of images) and a crack-segmentation model. Plane-DUSt3R, RoomFormer and several SLAM
  systems were considered and set aside for licence, GPU memory or integration time.
