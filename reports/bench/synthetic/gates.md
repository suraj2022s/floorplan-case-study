# Benchmark report: synthetic

Synthetic scenes with exactly known dimensions, rendered as LiDAR captures. This benchmark checks the geometry code and the scorer. It says nothing about real sensors, glass, mirrors or real drift, and none of its numbers are reported as benchmark accuracy.

## Gates

| Tier | Gate | Status | Result | Threshold | Notes |
|---|---|---|---|---|---|
| lidar | Opening widths | **PASS** | 17/18 = 94% | <= 2 cm on >= 85%; a miss and a phantom each count as a miss | 0 missed, 0 phantom, 1 found but off by more than 2 cm |
| lidar | Ceiling height | **PASS** | 11/11 rooms within 1.5 cm; worst 0.0 cm | <= 1.5 cm in every room | mean signed error -0.00 cm |
| lidar | Ceiling height, repeat captures | **PASS** | spread 0.00 cm over 1 room pair(s) | spread across captures <= 1 cm | repeatable and unbiased; mean error -0.01 cm |
| lidar | Repeatability per wall | **PASS** | 4/4 walls agree; worst 0.00 cm | two captures agree within 1 cm or 0.5% per wall | reading 'or' as whichever is larger. Strict reading (whichever is smaller): 4/4 |
| lidar | Wall lengths | **not evaluated** | median 0.1 cm, worst 4.2 cm (0.7%); 0 wall(s) not found | set by the Round 1 gate table, not supplied |  |
| lidar | Whole-property stitch | **PASS** | flat: footprint -0.0%; flat-drift: footprint +0.0% | one plan, correct adjacency, no overlaps, footprint within +-8%, interval holds |  |
| lidar | Interval calibration | **PASS** | 88/89 = 99% of 90% intervals contain the truth | >= 84% (90% less two standard errors at n=89) | ceiling_height 11/11; floor_area 11/11; footprint_area 5/5; opening_width 17/18; wall_length 44/44 |

## Captures

| Capture | Tier | Rooms found / measured | Adjacency | Overlap (m²) | Time (s) |
|---|---|---|---|---|---|
| box-room-a | lidar | 1 / 1 | correct | 0.000 | 12.6 |
| box-room-b | lidar | 1 / 1 | correct | 0.000 | 12.9 |
| furnished-room | lidar | 1 / 1 | correct | 0.000 | 17.6 |
| flat | lidar | 4 / 4 | correct | 0.000 | 66.6 |
| flat-drift | lidar | 4 / 4 | correct | 0.000 | 86.1 |

## Wall lengths

| Capture | Item | Truth (m) | Measured [90% interval] | Error (cm) | Truth in interval |
|---|---|---|---|---|---|
| box-room-a | room-S | 4.200 | 4.200 [4.095, 4.305] | +0.0 | yes |
| box-room-a | room-W | 3.350 | 3.350 [3.266, 3.434] | +0.0 | yes |
| box-room-a | room-N | 4.200 | 4.200 [4.095, 4.305] | +0.0 | yes |
| box-room-a | room-E | 3.350 | 3.350 [3.266, 3.434] | +0.0 | yes |
| box-room-b | room-S | 4.200 | 4.200 [4.095, 4.305] | +0.0 | yes |
| box-room-b | room-W | 3.350 | 3.350 [3.266, 3.434] | +0.0 | yes |
| box-room-b | room-N | 4.200 | 4.200 [4.095, 4.305] | +0.0 | yes |
| box-room-b | room-E | 3.350 | 3.350 [3.266, 3.434] | +0.0 | yes |
| furnished-room | bedroom-S | 3.800 | 3.800 [3.705, 3.895] | -0.0 | yes |
| furnished-room | bedroom-W | 3.200 | 3.200 [3.120, 3.280] | +0.0 | yes |
| furnished-room | bedroom-N | 3.800 | 3.800 [3.705, 3.895] | +0.0 | yes |
| furnished-room | bedroom-E | 3.200 | 3.200 [3.120, 3.280] | +0.0 | yes |
| flat | corridor-S | 1.200 | 1.200 [1.168, 1.232] | +0.0 | yes |
| flat | corridor-W | 6.000 | 6.000 [5.851, 6.148] | -0.0 | yes |
| flat | corridor-N | 1.200 | 1.200 [1.168, 1.232] | -0.0 | yes |
| flat | corridor-E | 6.000 | 6.000 [5.851, 6.149] | -0.0 | yes |
| flat | bedroom-S | 3.600 | 3.599 [3.509, 3.689] | -0.1 | yes |
| flat | bedroom-W | 3.600 | 3.600 [3.510, 3.690] | +0.0 | yes |
| flat | bedroom-N | 3.600 | 3.599 [3.509, 3.689] | -0.1 | yes |
| flat | bedroom-E | 3.600 | 3.600 [3.510, 3.690] | -0.0 | yes |
| flat | living-S | 4.500 | 4.499 [4.387, 4.611] | -0.1 | yes |
| flat | living-W | 3.400 | 3.400 [3.315, 3.485] | +0.0 | yes |
| flat | living-N | 4.500 | 4.499 [4.387, 4.611] | -0.1 | yes |
| flat | living-E | 3.400 | 3.400 [3.315, 3.485] | +0.0 | yes |
| flat | kitchen-S | 2.800 | 2.801 [2.730, 2.871] | +0.1 | yes |
| flat | kitchen-W | 2.480 | 2.479 [2.416, 2.541] | -0.1 | yes |
| flat | kitchen-N | 2.800 | 2.801 [2.731, 2.871] | +0.1 | yes |
| flat | kitchen-E | 2.480 | 2.479 [2.416, 2.541] | -0.1 | yes |
| flat-drift | corridor-S | 1.200 | 1.202 [1.156, 1.249] | +0.2 | yes |
| flat-drift | corridor-W | 6.000 | 6.029 [5.875, 6.183] | +2.9 | yes |
| flat-drift | corridor-N | 1.200 | 1.201 [1.154, 1.247] | +0.1 | yes |
| flat-drift | corridor-E | 6.000 | 6.042 [5.888, 6.197] | +4.2 | yes |
| flat-drift | bedroom-S | 3.600 | 3.597 [3.506, 3.688] | -0.3 | yes |
| flat-drift | bedroom-W | 3.600 | 3.603 [3.511, 3.694] | +0.3 | yes |
| flat-drift | bedroom-N | 3.600 | 3.596 [3.505, 3.687] | -0.4 | yes |
| flat-drift | bedroom-E | 3.600 | 3.599 [3.507, 3.690] | -0.1 | yes |
| flat-drift | living-S | 4.500 | 4.492 [4.379, 4.605] | -0.8 | yes |
| flat-drift | living-W | 3.400 | 3.399 [3.312, 3.486] | -0.1 | yes |
| flat-drift | living-N | 4.500 | 4.499 [4.386, 4.612] | -0.1 | yes |
| flat-drift | living-E | 3.400 | 3.397 [3.310, 3.484] | -0.3 | yes |
| flat-drift | kitchen-S | 2.800 | 2.799 [2.728, 2.870] | -0.1 | yes |
| flat-drift | kitchen-W | 2.480 | 2.477 [2.414, 2.540] | -0.3 | yes |
| flat-drift | kitchen-N | 2.800 | 2.809 [2.738, 2.880] | +0.9 | yes |
| flat-drift | kitchen-E | 2.480 | 2.476 [2.413, 2.539] | -0.4 | yes |

## Ceiling heights

| Capture | Item | Truth (m) | Measured [90% interval] | Error (cm) | Truth in interval |
|---|---|---|---|---|---|
| box-room-a | room | 2.740 | 2.740 [2.672, 2.808] | -0.0 | yes |
| box-room-b | room | 2.740 | 2.740 [2.672, 2.808] | -0.0 | yes |
| furnished-room | bedroom | 2.650 | 2.650 [2.584, 2.716] | +0.0 | yes |
| flat | corridor | 2.700 | 2.700 [2.633, 2.767] | +0.0 | yes |
| flat | bedroom | 2.700 | 2.700 [2.633, 2.767] | +0.0 | yes |
| flat | living | 2.700 | 2.700 [2.633, 2.767] | +0.0 | yes |
| flat | kitchen | 2.550 | 2.550 [2.486, 2.614] | -0.0 | yes |
| flat-drift | corridor | 2.700 | 2.700 [2.633, 2.767] | +0.0 | yes |
| flat-drift | bedroom | 2.700 | 2.700 [2.633, 2.767] | +0.0 | yes |
| flat-drift | living | 2.700 | 2.700 [2.633, 2.767] | +0.0 | yes |
| flat-drift | kitchen | 2.550 | 2.550 [2.486, 2.614] | -0.0 | yes |

## Opening widths

| Capture | Item | Truth (m) | Measured [90% interval] | Error (cm) | Truth in interval |
|---|---|---|---|---|---|
| box-room-a | room-D1 | 0.900 | 0.898 [0.869, 0.926] | -0.2 | yes |
| box-room-a | room-WIN1 | 1.200 | 1.195 [1.164, 1.226] | -0.5 | yes |
| box-room-b | room-D1 | 0.900 | 0.898 [0.870, 0.927] | -0.2 | yes |
| box-room-b | room-WIN1 | 1.200 | 1.195 [1.164, 1.226] | -0.5 | yes |
| furnished-room | bedroom-D1 | 0.850 | 0.847 [0.824, 0.870] | -0.3 | yes |
| furnished-room | bedroom-WIN1 | 1.400 | 1.399 [1.363, 1.435] | -0.1 | yes |
| flat | corridor-D1 | 0.900 | 0.898 [0.873, 0.922] | -0.2 | yes |
| flat | bedroom-D1 | 0.800 | 0.796 [0.775, 0.817] | -0.4 | yes |
| flat | living-D1 | 0.900 | 0.895 [0.872, 0.918] | -0.5 | yes |
| flat | kitchen-D1 | 0.750 | 0.746 [0.726, 0.765] | -0.4 | yes |
| flat | bedroom-WIN1 | 1.500 | 1.496 [1.458, 1.534] | -0.4 | yes |
| flat | living-WIN1 | 1.800 | 1.795 [1.750, 1.840] | -0.5 | yes |
| flat-drift | corridor-D1 | 0.900 | 0.899 [0.875, 0.924] | -0.1 | yes |
| flat-drift | bedroom-D1 | 0.800 | 0.797 [0.775, 0.819] | -0.3 | yes |
| flat-drift | living-D1 | 0.900 | 0.869 [0.846, 0.891] | -3.1 | NO |
| flat-drift | kitchen-D1 | 0.750 | 0.748 [0.729, 0.768] | -0.2 | yes |
| flat-drift | bedroom-WIN1 | 1.500 | 1.502 [1.464, 1.540] | +0.2 | yes |
| flat-drift | living-WIN1 | 1.800 | 1.797 [1.751, 1.842] | -0.3 | yes |

## Floor areas

| Capture | Item | Truth (m) | Measured [90% interval] | Error (m²) | Truth in interval |
|---|---|---|---|---|---|
| box-room-a | room | 14.070 | 14.070 [13.372, 14.768] | -0.000 | yes |
| box-room-b | room | 14.070 | 14.070 [13.372, 14.768] | -0.000 | yes |
| furnished-room | bedroom | 12.160 | 12.160 [11.557, 12.764] | +0.000 | yes |
| flat | corridor | 7.200 | 7.200 [6.838, 7.562] | -0.000 | yes |
| flat | bedroom | 12.960 | 12.957 [12.314, 13.600] | -0.003 | yes |
| flat | living | 15.300 | 15.297 [14.538, 16.055] | -0.003 | yes |
| flat | kitchen | 6.944 | 6.943 [6.597, 7.289] | -0.001 | yes |
| flat-drift | corridor | 7.200 | 7.252 [6.832, 7.672] | +0.052 | yes |
| flat-drift | bedroom | 12.960 | 12.949 [12.302, 13.596] | -0.011 | yes |
| flat-drift | living | 15.300 | 15.275 [14.511, 16.040] | -0.025 | yes |
| flat-drift | kitchen | 6.944 | 6.944 [6.597, 7.291] | +0.000 | yes |

## Footprint

| Capture | Item | Truth (m) | Measured [90% interval] | Error (m²) | Truth in interval |
|---|---|---|---|---|---|
| box-room-a | box-room-a | 14.070 | 14.070 [13.372, 14.768] | -0.000 | yes |
| box-room-b | box-room-b | 14.070 | 14.070 [13.372, 14.768] | -0.000 | yes |
| furnished-room | furnished-room | 12.160 | 12.160 [11.557, 12.764] | +0.000 | yes |
| flat | flat | 42.404 | 42.396 [40.300, 44.493] | -0.008 | yes |
| flat-drift | flat-drift | 42.404 | 42.421 [40.309, 44.533] | +0.017 | yes |

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
| flat-drift | corridor-D1 | matched | door | door | -0.1 |
| flat-drift | bedroom-D1 | matched | door | door | -0.3 |
| flat-drift | living-D1 | matched | door | door | -3.1 |
| flat-drift | kitchen-D1 | matched | door | door | -0.2 |
| flat-drift | bedroom-WIN1 | matched | window | window | +0.2 |
| flat-drift | living-WIN1 | matched | window | window | -0.3 |

## Drift ablation

The same capture run with drift correction on and off.

| Capture | Correction | Rooms | Walls found / measured | Footprint error | Worst wall error (cm) | Room overlap (m²) |
|---|---|---|---|---|---|---|
| flat-drift | on | 4 / 4 | 16 / 16 | +0.04% | 4.2 | 0.000 |
| flat-drift | off | 4 / 4 | 16 / 16 | -2.55% | 62.1 | 0.000 |

## Timing (seconds)

| Capture | cloud | damage | drift | fragments | keyframes | layout | levels | measure | openings | planes | refine | total |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| box-room-a | 0.2 | 0.2 | 0.4 | 9.4 | 0.0 | 0.0 | 0.0 | 0.0 | 2.0 | 0.3 | 0.0 | 12.6 |
| box-room-b | 0.2 | 0.2 | 0.4 | 9.5 | 0.0 | 0.0 | 0.0 | 0.0 | 2.2 | 0.3 | 0.0 | 12.9 |
| furnished-room | 0.2 | 0.5 | 0.5 | 12.6 | 0.0 | 0.0 | 0.1 | 0.0 | 3.4 | 0.3 | 0.0 | 17.6 |
| flat | 0.6 | 0.1 | 14.2 | 42.3 | 0.0 | 0.5 | 0.2 | 0.0 | 6.7 | 1.9 | 0.1 | 66.6 |
| flat-drift | 0.9 | 0.2 | 31.5 | 36.3 | 0.0 | 1.7 | 0.2 | 0.0 | 10.5 | 4.7 | 0.2 | 86.1 |
