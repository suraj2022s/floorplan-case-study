# 5. Drift

**In one sentence:** a wall does not move, so every fragment of the walk that sees a wall must
see it in the same place; each fragment gets a small turn and shift that makes it so, all
solved together with the correction changing slowly along the walk.

## How it works (`geometry/drift.py`)

1. The walk is already cut into fragments of about a second; inside one, the phone's poses
   are trusted.
2. Walls are fitted to all fragments together. Copies of one wall pulled apart by drift (same
   facing, within 15 cm, overlapping) are merged into one.
3. Every wall point of every fragment is assigned to the nearest wall it faces the same way as
   (normals agree, cosine above 0.9), within a reach that tightens each pass: 15, 12, 10, 8, 6,
   5 cm.
4. Each fragment k gets three unknowns: a turn theta about the vertical and a shift (x, y).
   A point's distance to its wall changes linearly with them, which gives one big linear
   least-squares system for all fragments at once:
   - data terms: each point pulls its fragment's correction so the point lands on its wall
     (points far from their wall lose weight, so a door leaf or picture cannot drag a
     fragment);
   - smoothness terms: the correction may change by about 1 cm and 0.1 degree from one
     fragment to the next, so a fragment that sees too little (one bare wall in a corridor)
     follows its neighbours;
   - the first fragment is held fixed: it defines the frame.
5. Solve, apply, refit the walls, repeat until nothing moves by more than 0.5 mm.

Only yaw and horizontal position are corrected: the accelerometer keeps gravity observable,
so tilt does not drift, and height is left alone so a real step between rooms is never
flattened.

## Why this way (decision 0002)

- The first version was an ICP pose graph between fragment clouds. On a capture with **no**
  drift it moved poses by up to 32 cm: fragments from the up- and down-sweeps share only a thin
  strip of wall, and point-to-point matching treats sliding along a plane as measured.
- Plane-anchored correction does nothing when there is nothing to fix: on a drift-free capture
  it moved poses by 0.1 mm. That property is why it replaced ICP.

## Evidence (synthetic four-room flat, drift 0.12 degrees and 1.2% per metre)

| Correction | Footprint error | Worst wall error |
|---|---|---|
| on | +0.04% | 4.2 cm |
| off | -2.55% | 62.1 cm |

With the drift doubled again, "off" also splits the corridor in two; "on" keeps every wall
within 10 cm. On the supplied iPhone scans it moved fragments by 2-5 cm on average and at
most 20 cm (`run_log.json`, `stats.drift`).

## Weak spots

- The ablation is synthetic. The brief asks for it on the real multi-room capture, which needs
  the iPhone session.
- It needs at least two walls seen across the walk; with fewer it does not run, and the plan
  says poses were used as recorded.
- A long corridor of bare parallel walls constrains the shift along it only through the
  smoothness prior.

## Likely questions

- *Is this loop closure?* In effect: when the end of the walk sees a wall from the start, the
  shared wall pulls the end back. There is no explicit place recognition.
- *Why not a full 6-DoF pose graph?* Tilt and height do not drift on a phone with gravity, and
  correcting them would risk flattening real level changes. Three unknowns per fragment keep it
  small and stable.
- *"Poses used as-is" fails the row. Can it switch off?* Only on request (`--no-drift`), which
  is how the ablation is made, and then the plan warns.
