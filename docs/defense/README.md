# Defense notes

Plain-language notes for explaining this pipeline live, without notes or tools. One page per
part of the pipeline, in the order the data flows. Each page has the same parts: what it
does in one sentence, how it works step by step, the numbers worth remembering, why it was
built this way and not another, its weak spots (say them before you are asked), and the
questions likely to come.

| # | Page | Code |
|---|---|---|
| 1 | [Capture, tiers and the point cloud](01_capture.md) | `capture.py`, `io/`, `geometry/cloud.py` |
| 2 | [Floor, ceiling and walls](02_planes.md) | `geometry/planes.py` |
| 3 | [Rooms](03_rooms.md) | `geometry/layout.py` |
| 4 | [Doors, windows, passages](04_openings.md) | `geometry/openings.py` |
| 5 | [Drift](05_drift.md) | `geometry/drift.py` |
| 6 | [Intervals and calibration](06_uncertainty.md) | `uncertainty/budget.py`, `bench/calibrate.py` |
| 7 | [Video tier](07_video.md) | `frontend/sfm.py`, `models/depth.py` |
| 8 | [Photo tier and stitching](08_photos.md) | `frontend/views.py`, `room.py`, `photo.py`, `stitch.py` |
| 9 | [Damage, flags, scope](09_damage.md) | `semantics/` |
| 10 | [Output, benchmark, fix loop](10_output_and_bench.md) | `output/`, `schema/`, `bench/`, `fixloop/` |
| 11 | [Hard questions](11_hard_questions.md) | |

## The two-minute version

A phone capture comes in one of three forms: a LiDAR recording (Stray Scanner), a video, or
a few photos per room. Each form has its own front-end, and every front-end produces the same
thing: frames with a camera position, a metric depth map, and a statement of how uncertain
the depth and the overall scale are. From there one back-end does everything:

1. drop near-duplicate frames; build small point clouds from about a second of walking;
2. correct drift by making every fragment see each wall in the same place;
3. merge into one cloud; find the floor and ceiling (height histograms) and the wall faces
   (histograms along each facing direction), each refitted by least squares;
4. extend every wall face into a line; the lines cut the floor into cells; keep the cells
   with evidence of being inside; glue cells unless a wall separates them: those are rooms;
5. find openings by casting every depth pixel's ray at every wall: rays that went through
   the wall mark a hole; the width comes from the jamb faces;
6. give every number a 90% interval from named error sources added in quadrature;
7. look for damage in the images, place it on the surface it lies on, fire rules for
   concealed damage, and price the scope from the plan's own measurements;
8. write `plan.json` (to our published schema), `plan.png` and `plan.svg`.

The honest headline: on real laser-measured scans the LiDAR tier is repeatable but biased
(ceilings about 3 cm low, from the iPad's 1.6% scale shortfall), openings fail their gate,
intervals are too narrow (6 of 11 contain the truth). Every failure has a measured cause, and
calibration on our own iPhone benchmark is what fixes the biases. Nothing is hidden: the
gates are reported as they stand.

## Numbers to have ready

| What | Number | Where it comes from |
|---|---|---|
| Keyframe | moved 5 cm or turned 4 degrees | `capture.select_keyframes` |
| Voxel | 2.5 cm (LiDAR), 3 cm (images) | `CloudConfig` |
| LiDAR depth kept | confidence 2 only, 0.25-4.5 m, no depth edges | `CloudConfig` |
| Wall must reach | within 45 cm of the ceiling, at least 2.15 m | `planes.wall_min_top` |
| Wall line fit | inliers within 3 cm, rms at most 2.5 cm | `PlaneConfig` |
| Room cell inside | half its area has floor/ceiling/path evidence, or 30 cm of wall faces into it | `LayoutConfig` |
| Border is a wall | 15% of it has real wall | `LayoutConfig.wall_share` |
| Step kept as real | 12 cm or more (25 cm tried, made a real room worse) | `max_jog` |
| Opening ray bins | on wall within 3 cm; through if 8 cm behind | `OpeningConfig` |
| Door vs window | sill at most 15 cm and height at least 1.6 m; passage if > 1.6 m wide with no top seen | `openings._kind` |
| Interval | 90%, z = 1.6449, sigmas in quadrature | `budget.py` |
| Scale sigma | LiDAR 1.5%, video 5%, photos 6% | `stray.py`, `sfm.py`, `photo.py` |
| Wall not seen | sigma 15 cm (LiDAR), 25 cm (video), 40 cm (photos) | `BUDGETS` |
| Observed wall | seen over at least 30% of its length | `OBSERVED_SHARE` |
| Damage flat | half the box's depth points within 3 cm of a plane parallel to the surface | `damage.flat_share` |
| LiDAR on real scans (4 rooms, 12 scans) | ceiling -1.6 to +1.3 cm, mean -0.3 (after the iPad factor 1.00945); spread 2.1 cm; intervals 21/25 | `reports/bench/arkitscenes`, `fixloop/ROUND3_RESULT.md` |
| Video on real clip | walls +1.7% to +5.1%; intervals 6/7 | same |
| Drift ablation (synthetic) | footprint +0.04% on, -2.55% off; worst wall 4.2 vs 62.1 cm | `reports/bench/synthetic` |
