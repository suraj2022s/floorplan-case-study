# Technical report: iPhone capture to a measured floor plan

Suraj Kumar · 2026-10-03 · repository `suraj2022s/floorplan-case-study`

Every number below names what it was measured on. No iPhone 15 Pro was available while this
was written, so real-data results come from a public-data benchmark: Apple's ARKitScenes
bedroom 47333462, scanned three times by an iPad Pro's LiDAR, filmed once, and scanned by a
Faro laser (`bench/benchmarks/arkitscenes.yaml`). Our own iPhone benchmark is planned as one
two-hour visit (`bench/SESSION.md`); sections 6 and 9 say what it will settle.

## 1. Summary

One command (`floorplan run <capture>`) turns a Stray Scanner recording, a walkthrough clip,
or per-room photo folders into a stitched plan: walls, ceiling heights, floor areas, doors and
windows, damage regions, concealed-damage flags and scope items, each measurement with a 90%
interval or marked *not measured*.

| Tier | On real data, against the laser | Gate status there |
|---|---|---|
| LiDAR | ceiling -2.6 to -3.8 cm on three scans; walls -1 to -13 cm on the scan that can be scored | ceiling FAIL (repeatable but biased), openings FAIL 0/11, intervals 6/11 |
| Video | walls +1.7% to +5.3%, ceiling +7.0%, on one 60 s clip | walls ±3%: 2 of 4; intervals PASS 6/7 |
| Photos | not measured on real protocol photos yet; within 1-2% on synthetic ones | not evaluated |

The largest errors have identified causes: the iPad's LiDAR is about 1.6% small against the
laser, the video depth model reads about 5% long, and curtains are taken for a wall. The
first two are scale biases, which the iPhone benchmark calibrates. The third is a known
failure mode (section 8).

## 2. Architecture

```
 Stray Scanner rec. ─► io/stray.py ─────────────────────────────┐
 walkthrough clip ──► frontend/sfm.py   (COLMAP + MoGe-2) ──────┼─► Capture: posed metric depth
 photo folders ─────► frontend/photo.py (MoGe-2 + room fit) ────┘   frames + their uncertainty
                                                                         │
   keyframes ─► fragments ─► drift correction ─► merged cloud ─► floor, ceiling, wall lines
   ─► rooms (cell complex) ─► openings (ray voting) ─► measurements with intervals
   ─► damage, flags, scope (OWLv2 + rules) ─► stitch ─► plan.json, plan.png
```

Every tier ends in the same `Capture`: frames with a camera-to-world pose in a gravity-aligned
metric frame (z up), intrinsics, a depth map, and the depth and scale uncertainty of the tier.
The back-end never knows which tier it serves; the tiers differ only in where depth and poses
come from and how uncertain they are. This keeps the output contract identical and makes the
widening of intervals from LiDAR to photos a matter of the budget, not of separate code.

Rooms come from a cell complex: wall lines cut the floor into cells, cells with evidence of
being inside are kept, and cells are joined unless a wall separates them. Two rules came from
the real scans: a gap in a wall seen on both sides is an opening, not open floor; and a wall
clearly seen from inside is opaque, so floor seen through its door or window belongs to
another space (section 7). Openings are found by casting each frame's rays at each wall:
rays that pass through the wall's plane mark an opening; its width comes from the jamb faces.

Captures arrive as the phone hands them over: `.zip`, a single clip, a recording inside a
wrapper folder, Live Photo clips next to stills, files a Mac adds (`io/intake.py`).

## 3. Tier design and device matrix

**LiDAR (Stray Scanner, Pro iPhones).** The app's own source fixes the pose convention: its
quaternion is ARKit's orientation times a half turn about x, so the camera axes are already
OpenCV's and only the y-up world needs turning. A public recording made with the app on a
LiDAR iPhone confirmed it: with the poses as written a worktop is level within 3 degrees and
two frames 23 degrees apart agree to 3 mm, while flipping the camera axes (as the recording's
own notes advise) puts the worktop upside down and the frames 12 cm apart. Depth pixels below
the highest confidence level and at depth edges are dropped.

**Video (any iPhone 15+).** Camera path from COLMAP; depth and metric scale from MoGe-2.
Alternatives were measured on the real clip before this was chosen (decision 0003):

| Camera path from | Error against ARKit's path |
|---|---|
| depth and walls of each frame (plane tracker) | 0.89 m mean |
| MapAnything, learned multi-view (Apache checkpoint) | 0.36 m; 25 s a frame on CPU |
| COLMAP global mapping | 0.23 m median |
| COLMAP incremental, loop pairs, pieces joined by shared frames | **4.5 cm mean, 85% of the walk** |

Each frame's MoGe-2 depth is compared with the COLMAP points it sees; the median ratio sets
metres per COLMAP unit and each frame is rescaled to agree, removing MoGe's 6% frame-to-frame
scale noise but not its common bias.

**Photos (any iPhone 15+).** MoGe-2 depth per photo, levelled from its own normals, with the
field of view from EXIF (corrected for square and 16:9 crops, whose EXIF focal length still
describes the 4:3 frame). Without overlap between photos there is no way to place them from
the images, so the protocol fixes where each is taken (back against the middle of a wall,
photographing the opposite wall, clockwise) and a least-squares rectangle fit recovers the
room, each photo's position and its scale. A room is measured only if every wall appears in
a photo and the floor the photos show fits inside the fitted room; otherwise its size is
reported as not measured. Before that check, real photos taken against the protocol gave a
1.9 x 1.6 m room for a 3.2 x 3.7 m one, with tight intervals.

| Tier | Phones | Run time, one room (laptop, RTX 3050 Ti 4 GB) |
|---|---|---|
| LiDAR | iPhone 15 Pro and newer Pro; iPad Pro 2020+ | 6-11 s |
| Video | any iPhone 15+ | about 4 min for a 60 s clip |
| Photos | any iPhone 15+ (0.5x lens preferred) | about 10 s |

Full matrix with what each row was tested on: `docs/device_matrix.md`.

## 4. Drift

The multi-room walk accumulates drift; using poses as recorded is not an option. The first
correction, an ICP pose graph over fragments, moved poses by up to 32 cm on a capture with no
drift at all: fragments from the turn-up and turn-down sweeps share a thin strip of wall,
and point-to-point weights treat sliding along a plane as measured. It was replaced by
plane-anchored correction (`geometry/drift.py`, decision 0002): walls are fitted to all
fragments; each fragment gets a yaw and horizontal shift that puts its points back on the
walls; all fragments are solved jointly with a smoothness prior, the first fixed. On a
drift-free capture it moves poses by 0.1 mm; it does no harm when there is nothing to fix.

Ablation, synthetic four-room flat with drift of 0.12 degrees and 1.2% per metre walked
(`reports/bench/synthetic/gates.md`):

| Correction | Rooms found | Footprint error | Worst wall error |
|---|---|---|---|
| on | 4 of 4 | +0.04% | 4.2 cm |
| off | 4 of 4 | -2.55% | 62.1 cm |

With the drift doubled again, "off" also splits the corridor into two rooms; "on" keeps every
wall within 10 cm.

The real multi-room ablation is part of the iPhone session.

## 5. Error budget

Each wall's length gets the uncertainty of its two end corners, each set by where the
neighbouring walls' faces sit, plus scale and definition:

σ²(length) = σ²(corner a) + σ²(corner b) + (scale · L)² + σ²(definition)

σ²(face) = σ²(fit) + rms² + σ²(plane, tier) + (6 cm · hidden share)²

| Term | LiDAR | Video | Photos | Source |
|---|---|---|---|---|
| scale (relative) | 1.5% | 5% (+ frame spread) | 6% | iPad vs laser 0.9-1.6%; MoGe vs LiDAR +5.2% mean, 6.1% spread (40 frames) |
| plane (tier) | 4 mm | 12 mm | 25 mm | depth noise per tier |
| surface scatter | measured per wall | | | walls 7-9 mm, curtains 20-50 mm (laser benchmark) |
| hidden share | up to 6 cm | | | faces behind furniture and curtains up to 12 cm off |
| wall not seen | 15 cm | 25 cm | 40 cm | placed by the room's shape alone |

Ceiling height combines the floor and ceiling fits, the tier's plane term twice and scale on
the height. Area combines each wall's face uncertainty along its length and scale twice. A
calibration factor per tier and measurement type (`configs/calibration/<tier>.json`, 1.0
until fitted) multiplies each σ; until it is fitted every plan carries a warning.

## 6. Calibration

Share of 90% intervals containing the laser's value (target 90%; a small set passes at 72%):

| Tier | Before the measured terms | After |
|---|---|---|
| LiDAR (11 items, 3 scans) | 3/11 | 6/11: all ceilings in; out: two walls set by a curtain line, a window measured between curtains, one area |
| Video (7 items, 1 clip) | 6/7 | 6/7 |
| Synthetic (89 items) | 89/89 | 89/89 |

The LiDAR ceiling is **repeatable but biased**: -3.3 cm on average with a 0.96 cm spread over
three scans, from the iPad's 1.6% scale shortfall. The video tier is biased the other way by
the depth model (+5%). Both are what calibration is for. The factors will be fitted on the
iPhone benchmark with one room left out at a time and checked on the room left out; fitting
them on this one public room would only tune to it, so they are 1.0 here.

## 7. The fix loop

Two rounds on the public benchmark, each declared before its fix (`fixloop/`).

**Round 1.** Worst gate: opening widths, 0 of 10. Declared cause: the room leaks through the
gap in a wall at its door and window, so those openings are not on its outline. Fix: never
join cells across a gap with wall on both sides. Result: one wall improved from -13.9 to
-1.2 cm, but the gate did not move, and the prediction (5-6 of 6 openings found) was badly
wrong. The post-mortem drew the cells themselves: the leaks went round the openings, through
a corner hidden by a wardrobe and through thin cells cut by curtain lines. The declaration had
been written from overlays that show where an outline leaks, not through which border.

**Round 2.** Declared only after measuring the mechanism without changing the code: 0.99 m²
of one scan's room and 3.77 m² of another's lay behind a clearly seen wall. Fix: a clearly seen
wall is opaque; floor seen through it is dropped, or becomes its own room if the walk went
there. Result: the root cause was right and the leaks are gone (floor-area errors +3.9 m² to
+0.4 m², +0.2 to -0.8 m², both within or just outside the predicted ranges), but the gate still
failed: cells next to the dropped ones, where little floor was seen, leave a notch in two
outlines, and the window's true edges are hidden behind its curtains.

## 8. Known failure modes

| Situation | What happens | Status |
|---|---|---|
| Curtains in front of a wall | taken as the wall (12 cm short); window width measured between them | open; interval widened by surface scatter |
| Glass | space seen through windows kept out of the room | handled (round 2) |
| Mirrors, TV screens | not taken for openings (detector) | handled; untested on real mirrors |
| Door next to a corner, hidden by a wardrobe | room can leak through the unseen corner | partly handled (round 2) |
| Fast video walk, bare walls | COLMAP track splits; only joined pieces used | protocol: walk slowly; plan reports frames used |
| Photos not taken by the protocol | room size reported as not measured, with the reason | handled |
| Low light, wet-look surfaces | untested | open |
| HDR (Dolby Vision) video | 10-bit HEVC decodes; no real iPhone HDR clip tested | partly verified |
| iPhone 16e (no 0.5x lens) | photos at 1x show less floor and ceiling | protocol fallback |
| Scale | iPad LiDAR 1.6% short; video depth 5% long | calibration on the iPhone benchmark |

## 9. What the iPhone session settles

The session (`bench/SESSION.md`) provides our own benchmark as the brief specifies: a
multi-room property at all three tiers with a repeat of one room per tier, staged damage of
two classes, tape or laser ground truth, and a consumer-app comparison on two rooms. It will
give: iPhone scale bias and calibration factors per tier; the photo tier's first real
accuracy; the real multi-room drift ablation; damage detection on real damage; and the
head-to-head table.
