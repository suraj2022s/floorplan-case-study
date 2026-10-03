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
- **03:20-03:53** Testing without an iPhone, against real files instead of our own:
  - a public recording made with Stray Scanner on a LiDAR iPhone (CC BY 4.0). Its header is
    exactly the one derived from the app's source. Its dataset notes say the camera axes must
    be flipped; with the poses as written, a worktop is level to 3 degrees and two frames 23
    degrees apart agree to 3 mm, while with the flip the worktop faces the floor. The reader
    was right. Four frames are now a test fixture. The same recording, a worktop close-up,
    was being reported as a 0.84 m² room; a capture with no wall and no ceiling is now
    refused with a reason.
  - real iPhone 15 Pro photo and video files. Two real bugs: a square photo's field of view
    came out 15% too wide (the 35 mm focal length in its EXIF describes the full 4:3 frame),
    and the clip half of a Live Photo made a folder of photos look like a video capture.
    Portrait HEIC and portrait MOV come out upright; 10-bit HEVC decodes.
  - the command now takes a .zip, a clip as a file, or a recording inside a wrapper folder,
    and ignores what a Mac leaves behind.
- **03:50** The code went to a private GitHub repository at the user's request, full history.
- **03:55** MapAnything measured on the real scan's own video frames: 25 s per frame on the
  CPU (the 4 GB GPU cannot hold it), camera positions 0.36 m off, rotations 10 degrees off.
  Rejected (decision 0003).
- **04:10-04:30** First real ground truth: Apple published Faro laser scans of some
  ARKitScenes rooms. The bedroom used so far has one, and two more iPad scans of the same
  room. `bench/public/laser_truth.py` reads the room off the laser (walls 3.188, 3.721,
  3.180, 3.728 m; ceiling 2.640 m). The LiDAR tier fails every gate it can be scored on:
  ceiling 2.7 to 3.8 cm low, walls up to 14 cm short, openings 0 of 10, no interval right.
  Drawing the scans onto the laser shows why: the room leaks through its window and door;
  curtains and furniture are taken for walls; and the iPad's points are 1.6% small.
- **04:36-04:56** Fix loop, two rounds on that benchmark (`fixloop/`). Round 1 was declared
  from the overlays alone and its prediction was badly wrong: the leaks did not go through
  the gap in the wall the declaration blamed. The post-mortem drew room finding's own cells,
  which showed the real mechanism. Round 2 was declared only after measuring that mechanism:
  the leaks are gone (floor area errors from +3.9 m² to +0.4 m²), but the opening gate did
  not move, because leftover cells beside the dropped ones keep a notch in two outlines.
- **05:00-14:40** Paused.
- **14:47** Video tier rebuilt on COLMAP for the camera path and MoGe-2 for depth and scale.
  On the real 60 s clip: 85% of the walk placed in one frame, 4.5 cm from ARKit's path; walls
  +1.7% to +5.3% against the laser, every wall's interval containing the truth. The remaining
  error is the depth model's +5% scale bias, which only an iPhone benchmark can calibrate.
- **14:55** Photo tier: on real frames that were not taken by the protocol it reported a
  1.9 x 1.6 m room for a 3.2 x 3.7 m one, with tight intervals. A room is now measured only
  if every wall appears in a photo and the floor the photos show fits inside the fitted
  room; otherwise its size is reported as not measured, with the reason. Protocol photos of
  the synthetic rooms are still measured.
- **14:56-15:00** Documents caught up with the code: capture protocol v2 (rules taken from
  what failed on real captures), a one-visit benchmark session plan, README with install
  and run, device matrix, compliance matrix with every gate result as it stands.
- **15:05** LiDAR intervals: 3 of 11 contained the laser's value. A wall's face had only its
  plane-fit uncertainty, whatever stood in front of it. Added the surface's own scatter
  (curtains scatter 20-50 mm), a term for hidden wall, and a 1.5% scale term from the iPad's
  measured shortfall: 6 of 11, all ceilings in. Calibration factors fitted on this one room
  would be in-sample, so they wait for the iPhone benchmark.
- **15:17** The drift ablation showed nothing: the synthetic drift was too small to matter
  (-0.05% footprint with correction on and off). At three times that drift (0.12 degrees and
  1.2% per metre): +0.04% on, -2.55% off, worst wall 4.2 cm against 62.1 cm.
- **15:17** Technical report, first complete draft.
- **15:24** Damage detector on seven real damage photos (Wikimedia Commons): the right class
  among those reported in 6 of 7, but classes bleed into each other. One class per patch:
  wrong classes 8 to 6, right class 6/7 to 5/7. Kept for coherent flags and scope; not tuned
  further on seven photos.
- **15:27-15:46** Tooling the iPhone session needs, so its evening goes fast: calibration
  factors with leave-one-room-out checking, the head-to-head table, a test that every
  measurement in plan.json has an interval (it caught item counts written with zero width),
  one reproduce command, and the fix-loop bundle with tags and diffs.
- **15:50** Why the door was missed in all three real scans: drawn from the opening votes,
  the doorway was hardly looked at in those captures (mostly unseen, partly blocked by the
  open door leaf). Our protocol asks for each doorway to be shown for 2 seconds from 1.5 m;
  only a protocol capture will tell whether that is enough.
- **15:56** The one reproduce command ran end to end in 9 min 49 s with caches and
  regenerated every measurement identically (only timings differ). Correction: the
  times on this afternoon's entries were first written from estimates and ran up to
  1.5 hours ahead of the clock; they now match the commit times.
- **16:12** Photo-tier stitching: on the synthetic flat photographed by protocol v2, the
  stitcher joined the bedroom straight to the living room (their door widths matched; the
  corridor's doors were not found). A join is now rejected unless what each door shows of
  the space behind it fits the room placed there (every room door shows about 1.3 m: the
  corridor). With every pixel's ray cast for photos, the corridor's side doors are found:
  bedroom and living room join the corridor correctly; the kitchen is left beside the plan,
  flagged; no wrong join.
- **16:05-16:20** At the user's request, the two public submissions for this case study found
  earlier were cloned outside this repository and their LiDAR tiers run on the same three
  real scans of the public benchmark, to see how they perform. Nothing from them is used
  here. Neither produced a better plan of the room; this does not change any of our numbers.
