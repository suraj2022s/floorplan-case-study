# Head-to-head stand-in: Pointorama on a public bedroom

**This is not the brief's head-to-head.** The brief asks for a consumer scanning app on two of
our own benchmark rooms. Those apps (magicplan, Polycam) scan live on a phone, and no Pro
iPhone was available. What was done instead, on 4 October 2026, between 15:20 and 15:45 IST:

1. `bench/headtohead/export_cloud.py` wrote the raw point clouds of ARKitScenes scans 47333462
   (bedroom 467138) and 42897672 (bedroom 423441): the iPad's own depth on its own poses, no
   drift or depth correction of ours, as LAS files.
2. They were uploaded to **Pointorama** (pointorama.com, web app, free trial; no version number
   is shown). Only its automatic tools were used: on the Floor tab, its automatic floor tool with
   one box drawn around the whole scan; on the Room tab, its automatic room tool, brushed inside
   the bedroom and accepted with Enter (a second Enter closes the outline it proposes). The
   outlines were not edited. A first attempt on the first bedroom left stray clicks; it was
   abandoned and the room redone.
3. Its exports, **`bedroom_467138.dxf`** and **`bedroom_423441.dxf`** (one closed outline each,
   24 and 20 corners, in metres), and its room panels (`room_panel_*.png`: area 9.92 and
   20.07 m², room height 2.59 and 2.33 m) are here. It reported no doors or windows.

Scored by `python bench/headtohead/pointorama.py` against Apple's laser truth
(`bench/ground_truth/arkitscenes-*.yaml`). Width and length are measured the same way on both
outlines: the sides of the smallest rectangle around it. Only dimensions both sides report are
compared, so openings are left out (in the tool's favour). The second bedroom's laser truth is
its ceiling only (eight walls; the wall read-off handles four), so its other dimensions are
shown but not scored. "Ours, raw" switches off the iPad's depth factor from fix-loop round 3,
so it starts from exactly the tool's input.

| Room | Dimension | Laser | Pointorama | Ours | Ours, raw |
|---|---|---|---|---|---|
| bedroom 467138 | width (m) | 3.184 | -0.019 | -0.026 x | -0.053 x |
| bedroom 467138 | length (m) | 3.725 | +0.655 | +0.023 | -0.005 |
| bedroom 467138 | floor area (m²) | 11.859 | -1.941 | -0.602 | -0.704 |
| bedroom 467138 | ceiling height (m) | 2.640 | -0.050 | -0.013 | -0.033 |
| bedroom 423441 | ceiling height (m) | 2.334 | -0.004 | +0.002 | -0.012 x |
| bedroom 423441 | width (m), not scored | | 5.052 | 4.400 | 4.559 |
| bedroom 423441 | length (m), not scored | | 5.064 | 4.828 | 4.828 |
| bedroom 423441 | floor area (m²), not scored | | 20.067 | 19.533 | 19.453 |

Errors are measured minus truth; x marks a dimension where the tool's error is smaller (a tie
is within 5 mm). **Beaten or tied: 4 of 5 (80%) as shipped; 3 of 5 (60%) raw.** The brief's bar
is 70%: met as shipped, not from the raw input alone.

What it does and does not show: from the same raw data, our outline of the first bedroom is
the closer one in length, area and ceiling, and the tool's in width, by 7 mm; the tool's outline
follows clutter at the wall foot in places (spikes that make its rectangle 65 cm long and its
area 1.9 m² short). In the second bedroom both ceilings are within 1.2 cm, the tool's within
4 mm. Five dimensions in two rooms is a small sample, the tool is a point-cloud product rather
than a phone app, and the scans are an iPad's, not an iPhone's.
