# 6. Intervals and calibration

**In one sentence:** every number gets a 1-sigma built from named, independent error sources
added in quadrature, is reported as a 90% interval (value ± 1.6449 sigma), and is marked
observed, inferred or not measured.

## How it works (`uncertainty/budget.py`, `pipeline._measure_room`)

**Where a wall face sits** (its 1-sigma), if the wall was seen over at least 30% of its length:

    sigma_face² = fit² + scatter² + plane(tier)² + (6 cm × hidden share)²

- *fit:* the line fit's own uncertainty (shrinks with more points);
- *scatter:* the surface's own rms, taken whole: a plain wall 7-9 mm, a curtain 20-50 mm
  (which fold is "the wall" is not known);
- *plane:* the tier's systematic term: LiDAR 4 mm, video 12 mm, photos 25 mm;
- *hidden share:* part of the wall hidden by furniture or curtains; on the laser benchmark such
  faces were up to 12 cm off.

A wall seen over less than 30% is **inferred**: sigma 15 cm (LiDAR), 25 cm (video), 40 cm
(photos).

**A wall's length** is set by its two corners, each placed by the neighbouring wall's face:

    sigma_length² = corner_a² + corner_b² + (scale × length)² + definition²

A corner where the neighbour meets at a shallow angle moves more (divided by the sine of the
angle, at least 0.2). **Area** combines each wall's face sigma times its length and twice the
scale. **Ceiling height** combines the floor and ceiling fits, the plane term twice and scale.
**The footprint** adds rooms' own errors in quadrature but their shared scale error linearly
(all rooms share the capture's scale).

**Scale** (relative, 1-sigma): LiDAR 1.5% (the iPad read 0.9-1.6% small against the laser),
video 5% (MoGe reads about 5% long), photos 6%.

**Not measured** is a value, not a guess: `value`, `lo`, `hi` and `sigma` are `null` with
`basis: not_measured`. A test walks the whole written plan and fails on any measurement
without an interval, and the schema test fails on any `NaN`.

## Calibration (`bench/calibrate.py`)

A 90% interval is calibrated when it contains the truth 90% of the time. Per tier and
measurement type, the factor f is the 90th percentile of |error| / sigma, divided by 1.6449;
every sigma of that type is multiplied by f. To avoid tuning to the rooms it is checked on,
each room is left out in turn: fitted on the others, counted on the one left out. Factors are
never below 0.75, and a type with fewer than 4 points keeps 1.0. Until fitted, every plan says
"intervals ... are not yet calibrated".

## Evidence

| Tier | 90% intervals containing the laser's value |
|---|---|
| LiDAR, 3 real scans of one room | 3/11 before the scatter, hidden and scale terms; 6/11 after |
| LiDAR, 12 real scans of four rooms, after round 3 | **21/25**: passes the calibration gate |
| Video, 1 real clip | 6/7 |
| Synthetic | 88/89 |

## Weak spots

- LiDAR intervals are still too narrow: the misses are two walls set by a curtain line, a
  window measured between curtains, and two areas.
- Factors are not fitted: one public room cannot be checked out of sample, so they wait for
  our own benchmark.

## Likely questions

- *Why quadrature?* The sources are independent; independent errors add as variances.
- *Biased or unrepeatable ceiling?* Before round 3: repeatable but biased (all twelve scans
  low). The iPad reads depth 0.9% short; a factor for that device (1.00945) removed the bias.
  Now unbiased (mean -0.3 cm, 11/12 within 1.5 cm) but not repeatable to 1 cm (scans of one
  room scatter up to 2.1 cm). One factor cannot remove scatter.
- *Why not just widen everything until 90% pass?* That is what calibration does, but per type
  and checked out of sample; widening by hand on the same data would only prove the arithmetic.
