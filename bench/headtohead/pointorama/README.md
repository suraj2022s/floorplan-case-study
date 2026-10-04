# Head-to-head stand-in: Pointorama on a public bedroom

**This is not the brief's head-to-head.** The brief asks for a consumer scanning app on two of
our own benchmark rooms. Those apps (magicplan, Polycam) scan live on a phone, and no Pro
iPhone was available. What was done instead, on 4 October 2026, between 15:20 and 15:45 IST:

1. `bench/headtohead/export_cloud.py` wrote the raw point cloud of ARKitScenes scan 47333462
   (the bedroom 467138: the iPad's own depth on its own poses, no drift or depth correction
   of ours) as a LAS file.
2. It was uploaded to **Pointorama** (pointorama.com, web app, free trial; no version number
   is shown). Only its automatic tools were used: on the Floor tab, its automatic floor tool
   with one box drawn around the whole scan (it found one level, 2.59 m); on the Room tab, its
   automatic room tool, brushed inside the room and accepted with Enter. The outline was not
   edited. A first attempt left stray clicks; it was abandoned and the room redone.
3. Its export, **`bedroom_467138.dxf`** (one closed outline, 24 corners, in metres), and its
   room panel (`room_panel.png`: 24 walls, area 9.92 m², room height 2.59 m) are here. It
   reported no doors or windows. The second bedroom was not done for lack of time.

Scored by `python bench/headtohead/pointorama.py` against Apple's laser truth
(`bench/ground_truth/arkitscenes-467138.yaml`). Width and length are measured the same way on
both outlines: the sides of the smallest rectangle around it. Only dimensions both sides report
are compared, so openings are left out (in the tool's favour). "Ours, raw" switches off the
iPad's depth factor from fix-loop round 3, so it starts from exactly the tool's input.

| Dimension | Laser | Pointorama | Ours | Ours, raw |
|---|---|---|---|---|
| width (m) | 3.184 | -0.019 | -0.026 x | -0.053 x |
| length (m) | 3.725 | +0.655 | +0.023 | -0.005 |
| floor area (m²) | 11.859 | -1.941 | -0.602 | -0.704 |
| ceiling height (m) | 2.640 | -0.050 | -0.013 | -0.033 |

Errors are measured minus truth; x marks a dimension where the tool's error is smaller (a tie
is within 5 mm). **Beaten or tied: 3 of 4 (75%)**, as shipped and raw alike; the brief's bar is
70%.

What it does and does not show: on this one room, from the same raw data, our outline is the
closer one in length, area and ceiling, and the tool's is closer in width, by 7 mm. The tool's
outline follows clutter at the wall foot in places (spikes that make its rectangle 65 cm long
and its area 1.9 m² short). One room and four dimensions is a small sample, the tool is a
point-cloud product rather than a phone app, and the scan is an iPad's, not an iPhone's.
