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
  depth points into voxels I had binned points by the compass direction of their normal, in
  30-degree sectors. A wall facing exactly along a sector boundary was split into two
  populations by the sign of its normal noise, each averaging to a normal about 7 degrees
  off. Wall directions were then wrong by 7 degrees, which smears a 4 m wall over 47 cm in
  the distance histogram. Fix: bin by up / down / sideways only, and take each facing
  direction from the strongest fitted wall rather than from point normals.
- **23:20** Synthetic flat (3 rooms + corridor, 1385 frames) end to end from one command:
  16 walls within 1.5 mm, 4 doors and 2 windows within 6 mm, adjacency correct, footprint
  42.396 m² against 42.404 m². These are synthetic results: they show the geometry code is
  right, not that it works on a real sensor.
