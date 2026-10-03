# Fix loop

Two rounds, both on the public-data benchmark (`bench/benchmarks/arkitscenes.yaml`: three
iPad Pro LiDAR scans of one real bedroom, ground truth from Apple's laser scan of it), because
no iPhone benchmark existed yet. Each declaration was committed before its fix.

| Round | Declaration | Before (tag) | Shipped fix (tag) | Result | Diff |
|---|---|---|---|---|---|
| 1 | [DECLARATION.md](DECLARATION.md) | `fixloop-before` | `fixloop-round1-after` | [ROUND1_RESULT.md](ROUND1_RESULT.md): gate unmoved, prediction badly wrong, post-mortem | [round1.diff](round1.diff) |
| 2 | [ROUND2_DECLARATION.md](ROUND2_DECLARATION.md) | `fixloop-round2-before` | `fixloop-round2-after` | [ROUND2_RESULT.md](ROUND2_RESULT.md): root cause right, leaks gone, gate unmoved | [round2.diff](round2.diff) |

The gate is opening widths at the LiDAR tier: 0 of 10 before, 0 of 11 after both rounds.
Round 2 fixed what it declared (floor-area errors from +3.9 and +0.2 m² to +0.4 and -0.8 m²);
why the gate itself did not move, and what would move it next, is in its result file.

## Regenerate before and after

```
git checkout fixloop-round2-before      # or any of the four tags
uv run python bench/run_bench.py bench/benchmarks/arkitscenes.yaml
# reports/bench/arkitscenes/gates.md now holds that side's numbers
git checkout main
```

The captures come from `uv run python scripts/fetch_arkitscenes.py` (155 MB). The runs used
for each result are kept as `evidence/*_gates.md`, with the drawings the diagnoses were made
from (`evidence/*.png`, made with `bench/public/overlay.py` and
`bench/public/layout_debug.py`).
