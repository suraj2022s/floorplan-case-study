# Design questions and answers

The questions a reviewer is most likely to ask, each answered in a few lines with the
evidence behind it. Longer reasoning is in `docs/decisions/`, the numbers in
`reports/bench/`, the history in `docs/JOURNAL.md`.

**Why one back-end for three tiers?**
So the output contract is identical by construction and only the uncertainties differ. Each
tier's front-end produces posed metric depth frames plus their depth and scale uncertainty;
the back-end (planes, rooms, openings, intervals) never knows which tier it serves. Widening
intervals from LiDAR to photos is then a matter of the error budget, not separate code.

**Why a stock app (Route 2) rather than our own iOS app?**
No Mac or iPhone was available to build and sign an app, and a stock app removes install
risk at the defence. Stray Scanner is free, on the App Store, records LiDAR depth, confidence,
ARKit poses and intrinsics, and its source is public, so its file format and pose convention
could be checked rather than assumed.

**How do you know the pose convention is right?**
From the app's source (the quaternion is ARKit's orientation times a half turn about x) and
from a real recording made with it: with the poses as written a worktop is level within 3
degrees and two frames 23 degrees apart agree to 3 mm; with the camera axes flipped, as the
recording's own notes advise, the worktop is upside down and the frames 12 cm apart.
`tests/test_real_recording.py` fails if anyone changes it.

**What do you do about drift?**
Plane-anchored correction (decision 0002): every fragment of the walk that sees a wall must
see it in the same place; each fragment gets a yaw and shift solved jointly with a smoothness
prior. An ICP pose graph was tried first and moved poses 32 cm on a capture with no drift,
because fragments sharing a thin strip of wall leave sliding along it unconstrained. Ablation
on the synthetic flat with 1.2% per metre drift: footprint +0.04% with correction, -2.55%
without, worst wall 4.2 cm against 62.1 cm. The real multi-room ablation needs the iPhone
session.

**Why COLMAP for video and not a learned model?**
Measured on a real 60 s clip against ARKit's path: plane tracker 0.89 m off, MapAnything
(Apache checkpoint) 0.36 m and 25 s a frame on this laptop's CPU, COLMAP global mapping 23 cm,
COLMAP incremental with loop pairs and joined pieces 4.5 cm over 85% of the walk (decision
0003). The learned model would need a bigger GPU and was still less accurate.

**Where does metric scale come from at each tier?**
LiDAR: the sensor (the iPad scans read 0.9-1.6% small against a laser; the iPhone's figure
comes from its benchmark). Video: MoGe-2's metric depth, compared with COLMAP's points frame
by frame, median taken; it reads about 5% long. Photos: MoGe-2 alone. Scale is the dominant
uncertainty of the image tiers and is in every interval.

**How are the intervals built, and are they calibrated?**
Each wall's length gets the uncertainty of its two end corners (set by where the neighbouring
walls' faces sit), plus scale times length, plus a definition term. A face's uncertainty is
its fit, the surface's own scatter (curtains scatter 20-50 mm), the hidden share of the wall,
and the tier's plane term. On real data: LiDAR 6 of 11 intervals hold the laser's value (too
narrow on curtained walls), video 6 of 7. Calibration factors per tier and measurement type are
fitted on the iPhone benchmark with each room left out in turn (`bench/calibrate.py`); fitting
them on the single public room would only tune to it.

**Your LiDAR ceiling fails the gate. Biased or unrepeatable?**
On one room it was repeatable but biased (-3.2 cm, 0.96 cm spread). On four rooms every
ceiling was low, more so the higher the room: the iPad reads depth about 0.9% short. Fix-loop
round 3 corrects that for the iPad (factor 1.00945; each room left out of the fit, 11 of 12
scans land within 1.5 cm). Now it is unbiased (mean -0.3 cm) but not repeatable to 1 cm: scans
of one room scatter by up to 2.1 cm. The iPhone's own factor needs iPhone data.

**What if the photos are not taken as the protocol says?**
Then the room's size is reported as not measured, with the reason, instead of a number.
Without overlap between photos nothing in the images places them relative to each other, so
the protocol fixes where each is taken (back to the middle of a wall). Two checks catch photos
that break it, without ground truth: every wall must appear in some photo, and the floor the
photos show must fit inside the fitted room. Before them, real frames gave 1.9 x 1.6 m for a
3.2 x 3.7 m room with tight intervals.

**How are rooms found, and why did they leak?**
Wall lines cut the floor into cells; cells with floor or ceiling evidence are inside; cells
are joined unless a wall separates them. On real scans the room leaked through its window
and door: a seen wall was not treated as opaque. Round 2 of the fix loop: floor seen through a
clearly seen wall belongs to another space, dropped unless the walk went there. The leaks went
from +3.9 m² of floor area to +0.4 m².

**How are openings found, and why were the doors missed?**
Each frame's rays are cast at each wall; rays passing through the wall's plane mark it open,
rays stopping on it mark it wall; a door-shaped region of open votes is an opening, its width
taken from the jamb faces. In the public scans the doorway was hardly looked at (mostly
unseen, partly blocked by the open leaf); the protocol asks for each doorway to be shown for 2
seconds from 1.5 m.

**How good is damage detection?**
OWLv2 with phrases per class. On seven real damage photos the right class is reported in 5
of 7 after keeping one class per patch; the classes are confused with each other (a crack can
score as a water stain). On the assessors' three undamaged homes it left two false regions:
a pot plant as mould, removed by requiring damage to lie flat on its surface, and a shower
door edge as a crack, still reported. It has not yet seen the benchmark's staged damage.

**How do flags and scope items work?**
Rules in `configs/rules.yaml` fire on a damage region's class and position: for example
`WALL_BASE_MOISTURE` fires on a water stain, mould or peeling paint whose lower edge is within
30 cm of the floor, and flags likely wet wall base and floor edge behind the skirting, with a
moisture inspection. Each flag names the rule that fired. Scope items come from `configs/scope_catalog.yaml`, keyed to the surface, with
quantities computed from the plan's own measurements and their intervals (repaint is the
wall's area less its openings).

**What fails?**
Curtains (taken for the wall, 12 cm off; window width measured between them), a door next to a
corner hidden by furniture, fast video walks past bare walls (the track splits), photos not
taken by the protocol (reported as not measured). Mirrors are not taken for openings; glass no
longer lets the room leak. Low light and wet-look surfaces are untested.

**Does it run offline, and how long does it take?**
Yes: weights are fetched by script beforehand; nothing calls a service at run time. On the
development laptop: LiDAR 7-13 s for one room, 11-141 s for the assessors' recordings (up to a
floor of a home); photos about 10 s a room; a 60 s video about 4 min.

**What would you do next?**
Capture the iPhone benchmark; fit calibration factors on it; make the opening detector use the
door frames visible in the images; replace curtain-like surfaces by the wall behind them when
the wall is seen above or beside them; and take the photo tier from the protocol's fixed
positions to positions solved from overlapping photos.
