# 9. Damage, concealed-damage flags, scope

**In one sentence:** an open-vocabulary detector (OWLv2) finds damage in the images; each box
is followed along its camera ray to the plan surface it shows and measured there in metres;
rules turn damage in certain places into flags for hidden damage; a catalogue turns damage and
flags into priced line items whose quantities come from the plan's own measurements.

## How it works (`semantics/`)

1. **Detect** (`models/detect.py`). OWLv2 base (Google, Apache-2.0) is asked short phrases per
   class: "water stain", "crack in the wall", "mold on the wall", "peeling paint", "hole in the
   wall", threshold 0.20 (`configs/semantics.yaml`). It also looks for mirrors, televisions,
   doors and windows (threshold 0.30). At most 40 images, spread through the capture.
2. **One class per patch.** Classes bleed (a mould patch also scores as a crack); where boxes of
   different classes overlap, only the highest-scoring one is kept.
3. **Place on a surface** (`damage.place_box`, `surfaces.py`). The box's centre pixel is a ray;
   the first wall, floor or ceiling of the plan it meets is the surface. Two checks that it is
   really *on* that surface:
   - the sensor's depth at the centre must not be well in front of it (25 cm or 12%): then it
     is on furniture;
   - **flatness** (added after the supplied sample data): at least half of the box's depth
     points must lie within 3 cm of one plane parallel to the surface. Damage is part of a
     surface and as flat as it; a plant or a door frame is not. Bare surfaces score 0.9-1.0,
     the pot plant that had been taken for mould 0.06-0.10.
4. **Measure.** The corners are pushed onto the surface; since a tilted view turns a rectangle
   into a trapezoid, the rectangle on the surface that would project to exactly this box is
   solved for. Boxes of one class on one surface that overlap are merged across views,
   weighted by score and by how squarely each view looked. LiDAR and video need 2 views.
5. **Flags** (`rules.py`, `configs/rules.yaml`). Each rule names classes, a surface and a place:
   e.g. `WALL_BASE_MOISTURE`: water stain, mould or peeling paint whose lower edge is within
   30 cm of the floor (rising damp, a leak under the floor). Others: ceiling water stain, top
   of wall, beside a window, a crack at a door or window corner (structural), mould over 0.5
   m². Each flag names the rule and the evidence it fired on. A flag is a reason to inspect,
   never a diagnosis.
6. **Scope** (`scope.py`, `configs/scope_catalog.yaml`). Per class: e.g. stain block over the
   damage area with a margin, repaint the whole wall (its area less its openings, from the
   plan), crack fill along the crack's length; per flag, an inspection. One repaint and one
   inspection per surface, however many regions or rules ask (the duplicate inspection was found
   on the sample data). Every quantity carries an interval.

## Evidence

- Seven real damage photos (Wikimedia Commons): the right class reported in 5 of 7; true
  damage scores 0.34-0.83.
- The supplied sample data (three undamaged homes): 108 boxes landed on surfaces; two views
  agreeing left two regions, both false (a pot plant as mould, a shower door edge as a crack).
  Flatness removed the plant. The shower edge passes it (0.61, 0.77) and is still in the plan,
  reported as a known false positive.

## Weak spots

- Never tested on real damage inside a capture: the benchmark session stages two classes.
- Classes are confused with each other (crack vs water stain).
- The extent is the bounding box on the surface: an upper estimate, which is what a repair is
  scoped from.

## Likely questions

- *Why not raise the threshold to remove the false crack?* It scored 0.21-0.23 and real damage
  0.34-0.83 in photos, so 0.25 would remove it. But walkthrough frames are blurrier than close
  photos, and a threshold set on three undamaged homes could hide real damage at the walk-in
  test. A false crack with one scope line is cheaper than a missed leak.
- *Why open-vocabulary and not a trained damage detector?* No labelled damage data of our own;
  a zero-shot model with phrases can be checked and changed in a config file.
