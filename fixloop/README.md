# Fix loop

Three rounds, all on the public-data benchmark (`bench/benchmarks/arkitscenes.yaml`: iPad Pro
LiDAR scans of real rooms, ground truth from Apple's laser scans of them; one bedroom for
rounds 1 and 2, four rooms for round 3), because no iPhone benchmark existed yet. Each
declaration was committed before its fix.

| Round | Declaration | Before (tag) | Shipped fix (tag) | Result | Diff |
|---|---|---|---|---|---|
| 1 | [DECLARATION.md](DECLARATION.md) | `fixloop-before` | `fixloop-round1-after` | [ROUND1_RESULT.md](ROUND1_RESULT.md): gate unmoved, prediction badly wrong, post-mortem | [round1.diff](round1.diff) |
| 2 | [ROUND2_DECLARATION.md](ROUND2_DECLARATION.md) | `fixloop-round2-before` | `fixloop-round2-after` | [ROUND2_RESULT.md](ROUND2_RESULT.md): root cause right, leaks gone, gate unmoved | [round2.diff](round2.diff) |
| 3 | [ROUND3_DECLARATION.md](ROUND3_DECLARATION.md) | `fixloop-round3-before` | `fixloop-round3-after` | [ROUND3_RESULT.md](ROUND3_RESULT.md): root cause right, ceiling bias gone (2/12 to 11/12 within 1.5 cm), gate short by one scan; interval calibration FAIL to PASS | [round3.diff](round3.diff) |

Rounds 1 and 2 worked on opening widths at the LiDAR tier: 0 of 10 before, 0 of 11 after both
rounds (1 of 10 after round 3). Round 3 worked on the ceiling height: 2 of 12 scans within
1.5 cm before, 11 of 12 after, the bias gone and the scatter between scans of a room left.
Round 2 fixed what it declared (floor-area errors from +3.9 and +0.2 m² to +0.4 and -0.8 m²);
why the gate itself did not move, and what would move it next, is in its result file.

## Regenerate before and after

```
git checkout fixloop-round3-before      # or any of the six tags
uv run python bench/run_bench.py bench/benchmarks/arkitscenes.yaml
# reports/bench/arkitscenes/gates.md now holds that side's numbers
git checkout main
```

The captures come from `uv run python scripts/fetch_arkitscenes.py` (about 1.1 GB; round 3 at its tags needs all twelve). The runs used
for each result are kept as `evidence/*_gates.md`, with the drawings the diagnoses were made
from (`evidence/*.png`, made with `bench/public/overlay.py` and
`bench/public/layout_debug.py`).
