# Benchmark report: synthetic

Synthetic scenes with exactly known dimensions, rendered as LiDAR captures. This benchmark checks the geometry code and the scorer. It says nothing about real sensors, glass, mirrors or real drift, and none of its numbers are reported as benchmark accuracy.

## Gates

| Tier | Gate | Status | Result | Threshold | Notes |
|---|---|---|---|---|---|
| lidar | Opening widths | **PASS** | 18/18 = 100% | <= 2 cm on >= 85%; a miss and a phantom each count as a miss | 0 missed, 0 phantom, 0 found but off by more than 2 cm |
| lidar | Ceiling height | **PASS** | 11/11 rooms within 1.5 cm; worst 0.0 cm | <= 1.5 cm in every room | mean signed error -0.00 cm |
| lidar | Ceiling height, repeat captures | **PASS** | spread 0.00 cm over 1 room pair(s) | spread across captures <= 1 cm | repeatable and unbiased; mean error -0.01 cm |
| lidar | Repeatability per wall | **PASS** | 4/4 walls agree; worst 0.00 cm | two captures agree within 1 cm or 0.5% per wall | reading 'or' as whichever is larger. Strict reading (whichever is smaller): 4/4 |
| lidar | Wall lengths | **not evaluated** | median 0.0 cm, worst 0.4 cm (0.1%); 0 wall(s) not found | set by the Round 1 gate table (not yet in spec/) |  |
| lidar | Whole-property stitch | **PASS** | flat: footprint -0.0%; flat-drift: footprint -0.1% | one plan, correct adjacency, no overlaps, footprint within +-8%, interval holds |  |
| lidar | Interval calibration | **PASS** | 89/89 = 100% of 90% intervals contain the truth | >= 84% (90% less two standard errors at n=89) | ceiling_height 11/11; floor_area 11/11; footprint_area 5/5; opening_width 18/18; wall_length 44/44 |

## Captures

| Capture | Tier | Rooms found / measured | Adjacency | Overlap (m²) | Time (s) |
|---|---|---|---|---|---|
| box-room-a | lidar | 1 / 1 | correct | 0.000 | 9.1 |
| box-room-b | lidar | 1 / 1 | correct | 0.000 | 9.1 |
| furnished-room | lidar | 1 / 1 | correct | 0.000 | 12.8 |
| flat | lidar | 4 / 4 | correct | 0.000 | 68.5 |
| flat-drift | lidar | 4 / 4 | correct | 0.000 | 64.7 |

## Wall lengths

| Capture | Item | Truth (m) | Measured [90% interval] | Error (cm) | Truth in interval |
|---|---|---|---|---|---|
| box-room-a | room-S | 4.200 | 4.200 [4.164, 4.236] | +0.0 | yes |
| box-room-a | room-W | 3.350 | 3.350 [3.321, 3.379] | +0.0 | yes |
| box-room-a | room-N | 4.200 | 4.200 [4.164, 4.236] | +0.0 | yes |
| box-room-a | room-E | 3.350 | 3.350 [3.321, 3.379] | +0.0 | yes |
| box-room-b | room-S | 4.200 | 4.200 [4.164, 4.236] | +0.0 | yes |
| box-room-b | room-W | 3.350 | 3.350 [3.321, 3.379] | +0.0 | yes |
| box-room-b | room-N | 4.200 | 4.200 [4.164, 4.236] | +0.0 | yes |
| box-room-b | room-E | 3.350 | 3.350 [3.321, 3.379] | +0.0 | yes |
| furnished-room | bedroom-S | 3.800 | 3.800 [3.767, 3.833] | -0.0 | yes |
| furnished-room | bedroom-W | 3.200 | 3.200 [3.172, 3.228] | +0.0 | yes |
| furnished-room | bedroom-N | 3.800 | 3.800 [3.767, 3.833] | +0.0 | yes |
| furnished-room | bedroom-E | 3.200 | 3.200 [3.172, 3.228] | +0.0 | yes |
| flat | corridor-S | 1.200 | 1.200 [1.186, 1.214] | -0.0 | yes |
| flat | corridor-W | 6.000 | 6.000 [5.949, 6.050] | -0.0 | yes |
| flat | corridor-N | 1.200 | 1.200 [1.186, 1.214] | -0.0 | yes |
| flat | corridor-E | 6.000 | 6.000 [5.950, 6.050] | -0.0 | yes |
| flat | bedroom-S | 3.600 | 3.599 [3.568, 3.631] | -0.1 | yes |
| flat | bedroom-W | 3.600 | 3.600 [3.569, 3.631] | +0.0 | yes |
| flat | bedroom-N | 3.600 | 3.599 [3.568, 3.630] | -0.1 | yes |
| flat | bedroom-E | 3.600 | 3.600 [3.569, 3.631] | +0.0 | yes |
| flat | living-S | 4.500 | 4.499 [4.461, 4.538] | -0.1 | yes |
| flat | living-W | 3.400 | 3.400 [3.370, 3.430] | +0.0 | yes |
| flat | living-N | 4.500 | 4.499 [4.461, 4.537] | -0.1 | yes |
| flat | living-E | 3.400 | 3.400 [3.370, 3.430] | +0.0 | yes |
| flat | kitchen-S | 2.800 | 2.801 [2.776, 2.826] | +0.1 | yes |
| flat | kitchen-W | 2.480 | 2.479 [2.456, 2.501] | -0.1 | yes |
| flat | kitchen-N | 2.800 | 2.801 [2.776, 2.826] | +0.1 | yes |
| flat | kitchen-E | 2.480 | 2.479 [2.456, 2.501] | -0.1 | yes |
| flat-drift | corridor-S | 1.200 | 1.200 [1.186, 1.214] | -0.0 | yes |
| flat-drift | corridor-W | 6.000 | 6.004 [5.954, 6.055] | +0.4 | yes |
| flat-drift | corridor-N | 1.200 | 1.199 [1.185, 1.213] | -0.1 | yes |
| flat-drift | corridor-E | 6.000 | 5.999 [5.948, 6.049] | -0.1 | yes |
| flat-drift | bedroom-S | 3.600 | 3.600 [3.569, 3.631] | -0.0 | yes |
| flat-drift | bedroom-W | 3.600 | 3.600 [3.569, 3.631] | -0.0 | yes |
| flat-drift | bedroom-N | 3.600 | 3.600 [3.568, 3.631] | -0.0 | yes |
| flat-drift | bedroom-E | 3.600 | 3.598 [3.567, 3.629] | -0.2 | yes |
| flat-drift | living-S | 4.500 | 4.498 [4.459, 4.536] | -0.2 | yes |
| flat-drift | living-W | 3.400 | 3.398 [3.368, 3.427] | -0.2 | yes |
| flat-drift | living-N | 4.500 | 4.500 [4.462, 4.538] | -0.0 | yes |
| flat-drift | living-E | 3.400 | 3.397 [3.367, 3.427] | -0.3 | yes |
| flat-drift | kitchen-S | 2.800 | 2.800 [2.774, 2.825] | -0.0 | yes |
| flat-drift | kitchen-W | 2.480 | 2.479 [2.456, 2.501] | -0.1 | yes |
| flat-drift | kitchen-N | 2.800 | 2.802 [2.777, 2.827] | +0.2 | yes |
| flat-drift | kitchen-E | 2.480 | 2.478 [2.456, 2.501] | -0.2 | yes |

## Ceiling heights

| Capture | Item | Truth (m) | Measured [90% interval] | Error (cm) | Truth in interval |
|---|---|---|---|---|---|
| box-room-a | room | 2.740 | 2.740 [2.715, 2.764] | -0.0 | yes |
| box-room-b | room | 2.740 | 2.740 [2.715, 2.764] | -0.0 | yes |
| furnished-room | bedroom | 2.650 | 2.650 [2.626, 2.674] | +0.0 | yes |
| flat | corridor | 2.700 | 2.700 [2.676, 2.724] | +0.0 | yes |
| flat | bedroom | 2.700 | 2.700 [2.676, 2.724] | +0.0 | yes |
| flat | living | 2.700 | 2.700 [2.676, 2.724] | +0.0 | yes |
| flat | kitchen | 2.550 | 2.550 [2.527, 2.573] | -0.0 | yes |
| flat-drift | corridor | 2.700 | 2.700 [2.676, 2.724] | +0.0 | yes |
| flat-drift | bedroom | 2.700 | 2.700 [2.676, 2.724] | +0.0 | yes |
| flat-drift | living | 2.700 | 2.700 [2.676, 2.724] | +0.0 | yes |
| flat-drift | kitchen | 2.550 | 2.550 [2.527, 2.573] | -0.0 | yes |

## Opening widths

| Capture | Item | Truth (m) | Measured [90% interval] | Error (cm) | Truth in interval |
|---|---|---|---|---|---|
| box-room-a | room-D1 | 0.900 | 0.898 [0.878, 0.917] | -0.2 | yes |
| box-room-a | room-WIN1 | 1.200 | 1.195 [1.181, 1.209] | -0.5 | yes |
| box-room-b | room-D1 | 0.900 | 0.898 [0.879, 0.917] | -0.2 | yes |
| box-room-b | room-WIN1 | 1.200 | 1.195 [1.181, 1.209] | -0.5 | yes |
| furnished-room | bedroom-D1 | 0.850 | 0.847 [0.835, 0.859] | -0.3 | yes |
| furnished-room | bedroom-WIN1 | 1.400 | 1.399 [1.384, 1.415] | -0.0 | yes |
| flat | corridor-D1 | 0.900 | 0.898 [0.885, 0.910] | -0.2 | yes |
| flat | bedroom-D1 | 0.800 | 0.796 [0.786, 0.806] | -0.4 | yes |
| flat | living-D1 | 0.900 | 0.895 [0.884, 0.905] | -0.5 | yes |
| flat | kitchen-D1 | 0.750 | 0.746 [0.736, 0.755] | -0.4 | yes |
| flat | bedroom-WIN1 | 1.500 | 1.496 [1.481, 1.512] | -0.4 | yes |
| flat | living-WIN1 | 1.800 | 1.795 [1.777, 1.813] | -0.5 | yes |
| flat-drift | corridor-D1 | 0.900 | 0.900 [0.888, 0.913] | +0.0 | yes |
| flat-drift | bedroom-D1 | 0.800 | 0.801 [0.789, 0.812] | +0.1 | yes |
| flat-drift | living-D1 | 0.900 | 0.890 [0.880, 0.901] | -1.0 | yes |
| flat-drift | kitchen-D1 | 0.750 | 0.747 [0.738, 0.757] | -0.3 | yes |
| flat-drift | bedroom-WIN1 | 1.500 | 1.501 [1.485, 1.517] | +0.1 | yes |
| flat-drift | living-WIN1 | 1.800 | 1.799 [1.781, 1.817] | -0.1 | yes |

## Floor areas

| Capture | Item | Truth (m) | Measured [90% interval] | Error (m²) | Truth in interval |
|---|---|---|---|---|---|
| box-room-a | room | 14.070 | 14.070 [13.833, 14.306] | -0.000 | yes |
| box-room-b | room | 14.070 | 14.070 [13.833, 14.307] | -0.000 | yes |
| furnished-room | bedroom | 12.160 | 12.160 [11.955, 12.365] | +0.000 | yes |
| flat | corridor | 7.200 | 7.199 [7.068, 7.331] | -0.001 | yes |
| flat | bedroom | 12.960 | 12.957 [12.739, 13.176] | -0.003 | yes |
| flat | living | 15.300 | 15.297 [15.040, 15.554] | -0.003 | yes |
| flat | kitchen | 6.944 | 6.943 [6.824, 7.062] | -0.001 | yes |
| flat-drift | corridor | 7.200 | 7.197 [7.066, 7.329] | -0.003 | yes |
| flat-drift | bedroom | 12.960 | 12.955 [12.737, 13.173] | -0.005 | yes |
| flat-drift | living | 15.300 | 15.284 [15.027, 15.541] | -0.016 | yes |
| flat-drift | kitchen | 6.944 | 6.942 [6.823, 7.062] | -0.002 | yes |

## Footprint

| Capture | Item | Truth (m) | Measured [90% interval] | Error (m²) | Truth in interval |
|---|---|---|---|---|---|
| box-room-a | box-room-a | 14.070 | 14.070 [13.833, 14.306] | -0.000 | yes |
| box-room-b | box-room-b | 14.070 | 14.070 [13.833, 14.307] | -0.000 | yes |
| furnished-room | furnished-room | 12.160 | 12.160 [11.955, 12.365] | +0.000 | yes |
| flat | flat | 42.404 | 42.396 [41.692, 43.100] | -0.008 | yes |
| flat-drift | flat-drift | 42.404 | 42.379 [41.675, 43.083] | -0.025 | yes |

## Opening detection

| Capture | Opening | Outcome | Measured kind | Found kind | Width error (cm) |
|---|---|---|---|---|---|
| box-room-a | room-D1 | matched | door | door | -0.2 |
| box-room-a | room-WIN1 | matched | window | window | -0.5 |
| box-room-b | room-D1 | matched | door | door | -0.2 |
| box-room-b | room-WIN1 | matched | window | window | -0.5 |
| furnished-room | bedroom-D1 | matched | door | door | -0.3 |
| furnished-room | bedroom-WIN1 | matched | window | window | -0.1 |
| flat | corridor-D1 | matched | door | door | -0.2 |
| flat | bedroom-D1 | matched | door | door | -0.4 |
| flat | living-D1 | matched | door | door | -0.5 |
| flat | kitchen-D1 | matched | door | door | -0.4 |
| flat | bedroom-WIN1 | matched | window | window | -0.4 |
| flat | living-WIN1 | matched | window | window | -0.5 |
| flat-drift | corridor-D1 | matched | door | door | +0.0 |
| flat-drift | bedroom-D1 | matched | door | door | +0.1 |
| flat-drift | living-D1 | matched | door | door | -1.0 |
| flat-drift | kitchen-D1 | matched | door | door | -0.3 |
| flat-drift | bedroom-WIN1 | matched | window | window | +0.1 |
| flat-drift | living-WIN1 | matched | window | window | -0.1 |

## Drift ablation

The same capture run with drift correction on and off.

| Capture | Correction | Rooms | Walls found / measured | Footprint error | Worst wall error (cm) | Room overlap (m²) |
|---|---|---|---|---|---|---|
| flat-drift | on | 4 / 4 | 16 / 16 | -0.06% | 0.4 | 0.000 |
| flat-drift | off | 4 / 4 | 16 / 16 | -0.05% | 0.8 | 0.000 |

## Timing (seconds)

| Capture | cloud | drift | fragments | keyframes | layout | levels | measure | openings | planes | refine | total |
|---|---|---|---|---|---|---|---|---|---|---|---|
| box-room-a | 0.1 | 1.8 | 5.9 | 0.0 | 0.0 | 0.0 | 0.0 | 1.0 | 0.2 | 0.0 | 9.1 |
| box-room-b | 0.1 | 2.1 | 5.6 | 0.0 | 0.0 | 0.0 | 0.0 | 1.0 | 0.2 | 0.0 | 9.1 |
| furnished-room | 0.1 | 2.2 | 8.7 | 0.0 | 0.0 | 0.0 | 0.0 | 1.5 | 0.1 | 0.0 | 12.8 |
| flat | 0.6 | 30.7 | 30.0 | 0.0 | 0.2 | 0.2 | 0.0 | 5.7 | 1.1 | 0.0 | 68.5 |
| flat-drift | 0.5 | 27.7 | 28.1 | 0.0 | 0.6 | 0.2 | 0.0 | 5.6 | 2.0 | 0.1 | 64.7 |
