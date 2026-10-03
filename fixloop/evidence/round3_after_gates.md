# Benchmark report: arkitscenes

Public data, used while no iPhone is available: rooms from Apple's ARKitScenes dataset, each captured three times with the LiDAR of an iPad Pro (ARKit poses and depth) and scanned with a Faro laser. Ground truth is read off the laser scans by bench/public/laser_truth.py. The bedroom 467138 has walls, ceiling, area and openings; the bedroom 423441, the bathroom 438802 and the kitchen 482863 have their ceiling height only (their walls do not fit the four-wall read-off). Rooms were chosen from Apple's metadata as visits with one laser scan and several videos, then kept only if the scanner stands inside the room under one ceiling level; 422009 (scanner in a doorway) and 483605 (two ceiling levels) were left out. This is real sensor data with laser ground truth, but not the benchmark set the brief specifies: no multi-room capture, no staged damage, an iPad rather than an iPhone, and captures made by Apple's operators rather than by our protocol. Fetch with python scripts/fetch_arkitscenes.py.

## Gates

| Tier | Gate | Status | Result | Threshold | Notes |
|---|---|---|---|---|---|
| lidar | Opening widths | **FAIL** | 1/10 = 10% | <= 2 cm on >= 85%; a miss and a phantom each count as a miss | 4 missed, 4 phantom, 1 found but off by more than 2 cm |
| lidar | Ceiling height | **FAIL** | 11/12 rooms within 1.5 cm; worst 1.6 cm | <= 1.5 cm in every room | mean signed error -0.44 cm |
| lidar | Ceiling height, repeat captures | **FAIL** | spread 2.12 cm over 12 room pair(s) | spread across captures <= 1 cm | unrepeatable; mean error -0.44 cm |
| lidar | Repeatability per wall | **FAIL** | 0/4 walls agree; worst 15.09 cm | two captures agree within 1 cm or 0.5% per wall | reading 'or' as whichever is larger. Strict reading (whichever is smaller): 0/4 |
| lidar | Wall lengths | **not evaluated** | median 8.1 cm, worst 20.0 cm (5.4%); 4 wall(s) not found | set by the Round 1 gate table, not supplied |  |
| lidar | Whole-property stitch | **not evaluated** | no multi-room capture at this tier |  |  |
| lidar | Interval calibration | **PASS** | 21/25 = 84% of 90% intervals contain the truth | >= 78% (90% less two standard errors at n=25) | ceiling_height 12/12; floor_area 3/3; opening_width 1/2; wall_length 5/8 |
| video | Opening widths | **FAIL** | 0/2 = 0% | <= 2 cm on >= 85%; a miss and a phantom each count as a miss | 1 missed, 0 phantom, 1 found but off by more than 2 cm |
| video | Ceiling height | **FAIL** | 0/1 rooms within 1.5 cm; worst 18.7 cm | <= 1.5 cm in every room | mean signed error +18.66 cm |
| video | Ceiling height, repeat captures | **not evaluated** | no room captured twice at this tier |  |  |
| video | Repeatability per wall | **not evaluated** | no room captured twice at this tier |  |  |
| video | Wall lengths | **FAIL** | 2/4 within 3%; median 11.5 cm, worst 16.1 cm (5.0%); 0 wall(s) not found | every wall within +-3% |  |
| video | Whole-property stitch | **not evaluated** | no multi-room capture at this tier |  |  |
| video | Interval calibration | **PASS** | 6/7 = 86% of 90% intervals contain the truth | >= 67% (90% less two standard errors at n=7) | ceiling_height 1/1; floor_area 1/1; opening_width 0/1; wall_length 4/4 |

## Captures

| Capture | Tier | Rooms found / measured | Adjacency | Overlap (m²) | Time (s) |
|---|---|---|---|---|---|
| bedroom-a | lidar | 1 / 1 | correct | 0.000 | 10.6 |
| bedroom-b | lidar | 1 / 1 | correct | 0.000 | 6.5 |
| bedroom-c | lidar | 1 / 1 | correct | 0.000 | 8.8 |
| bedroom2-a | lidar | 1 / 1 | correct | 0.000 | 39.8 |
| bedroom2-b | lidar | 2 / 1 | WRONG | 0.000 | 63.3 |
| bedroom2-c | lidar | 1 / 1 | correct | 0.000 | 38.0 |
| bathroom-a | lidar | 1 / 1 | correct | 0.000 | 6.2 |
| bathroom-b | lidar | 1 / 1 | correct | 0.000 | 14.8 |
| bathroom-c | lidar | 1 / 1 | correct | 0.000 | 6.0 |
| kitchen-a | lidar | 2 / 1 | WRONG | 0.000 | 23.3 |
| kitchen-b | lidar | 1 / 1 | correct | 0.000 | 1.4 |
| kitchen-c | lidar | 2 / 1 | WRONG | 0.000 | 28.9 |
| bedroom-a-video | video | 1 / 1 | correct | 0.000 | 31.6 |

## Wall lengths

| Capture | Item | Truth (m) | Measured [90% interval] | Error (cm) | Truth in interval |
|---|---|---|---|---|---|
| bedroom-a | bedroom-W1 | 3.188 | 3.165 [2.805, 3.526] | -2.2 | yes |
| bedroom-a | bedroom-W2 | 3.721 | 3.521 [3.403, 3.639] | -20.0 | NO |
| bedroom-a | bedroom-W3 | 3.180 | 3.081 [2.998, 3.163] | -10.0 | NO |
| bedroom-a | bedroom-W4 | 3.728 | 3.744 [3.638, 3.850] | +1.6 | yes |
| bedroom-b | bedroom-W1 | 3.188 | 3.125 [3.042, 3.207] | -6.3 | yes |
| bedroom-b | bedroom-W2 | 3.721 | 3.603 [3.481, 3.724] | -11.9 | yes |
| bedroom-b | bedroom-W3 | 3.180 | 3.185 [2.899, 3.471] | +0.4 | yes |
| bedroom-b | bedroom-W4 | 3.728 | 3.593 [3.488, 3.698] | -13.5 | NO |
| bedroom-c | bedroom-W1 | 3.188 | not found | not found |  |
| bedroom-c | bedroom-W2 | 3.721 | not found | not found |  |
| bedroom-c | bedroom-W3 | 3.180 | not found | not found |  |
| bedroom-c | bedroom-W4 | 3.728 | not found | not found |  |
| bedroom-a-video | bedroom-W1 | 3.188 | 3.349 [3.055, 3.642] | +16.1 | yes |
| bedroom-a-video | bedroom-W2 | 3.721 | 3.783 [3.438, 4.129] | +6.2 | yes |
| bedroom-a-video | bedroom-W3 | 3.180 | 3.314 [3.023, 3.605] | +13.4 | yes |
| bedroom-a-video | bedroom-W4 | 3.728 | 3.824 [3.476, 4.172] | +9.6 | yes |

## Ceiling heights

| Capture | Item | Truth (m) | Measured [90% interval] | Error (cm) | Truth in interval |
|---|---|---|---|---|---|
| bedroom-a | bedroom | 2.640 | 2.627 [2.561, 2.692] | -1.3 | yes |
| bedroom-b | bedroom | 2.640 | 2.624 [2.559, 2.690] | -1.6 | yes |
| bedroom-c | bedroom | 2.640 | 2.635 [2.569, 2.700] | -0.5 | yes |
| bedroom2-a | bedroom | 2.334 | 2.336 [2.278, 2.395] | +0.2 | yes |
| bedroom2-b | bedroom | 2.334 | 2.332 [2.274, 2.390] | -0.2 | yes |
| bedroom2-c | bedroom | 2.334 | 2.333 [2.275, 2.391] | -0.1 | yes |
| bathroom-a | bathroom | 2.402 | 2.415 [2.355, 2.475] | +1.3 | yes |
| bathroom-b | bathroom | 2.402 | 2.394 [2.334, 2.454] | -0.8 | yes |
| bathroom-c | bathroom | 2.402 | 2.395 [2.335, 2.455] | -0.7 | yes |
| kitchen-a | kitchen | 2.573 | 2.568 [2.504, 2.632] | -0.6 | yes |
| kitchen-b | kitchen | 2.573 | 2.565 [2.501, 2.629] | -0.9 | yes |
| kitchen-c | kitchen | 2.573 | 2.572 [2.508, 2.637] | -0.1 | yes |
| bedroom-a-video | bedroom | 2.640 | 2.826 [2.591, 3.062] | +18.7 | yes |

## Opening widths

| Capture | Item | Truth (m) | Measured [90% interval] | Error (cm) | Truth in interval |
|---|---|---|---|---|---|
| bedroom-b | bedroom-D1 | 0.732 | 0.773 [0.752, 0.795] | +4.1 | NO |
| bedroom-b | bedroom-WIN1 | 1.326 | 1.317 [1.283, 1.351] | -0.9 | yes |
| bedroom-a-video | bedroom-WIN1 | 1.326 | 1.492 [1.360, 1.624] | +16.6 | NO |

## Floor areas

| Capture | Item | Truth (m) | Measured [90% interval] | Error (m²) | Truth in interval |
|---|---|---|---|---|---|
| bedroom-a | bedroom | 11.859 | 11.257 [10.649, 11.866] | -0.602 | yes |
| bedroom-b | bedroom | 11.859 | 11.378 [10.764, 11.992] | -0.481 | yes |
| bedroom-c | bedroom | 11.859 | 11.546 [10.943, 12.150] | -0.313 | yes |
| bedroom-a-video | bedroom | 11.859 | 12.671 [10.487, 14.856] | +0.812 | yes |

## Opening detection

| Capture | Opening | Outcome | Measured kind | Found kind | Width error (cm) |
|---|---|---|---|---|---|
| bedroom-a | bedroom-D1 | missed | door |  |  |
| bedroom-a | bedroom-WIN1 | missed | window |  |  |
| bedroom-a | room_1-P1 | phantom |  | passage |  |
| bedroom-b | bedroom-D1 | matched | door | door | +4.1 |
| bedroom-b | bedroom-WIN1 | matched | window | window | -0.9 |
| bedroom-c | bedroom-D1 | missed | door |  |  |
| bedroom-c | bedroom-WIN1 | missed | window |  |  |
| bedroom-c | room_1-D1 | phantom |  | door |  |
| bedroom-c | room_1-WIN1 | phantom |  | window |  |
| bedroom-c | room_1-D2 | phantom |  | door |  |
| bedroom-a-video | bedroom-D1 | missed | door |  |  |
| bedroom-a-video | bedroom-WIN1 | matched | window | window | +16.6 |

## Timing (seconds)

| Capture | cloud | damage | drift | fragments | keyframes | layout | levels | measure | openings | planes | poses_and_depth | refine | total |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| bedroom-a | 0.1 | 0.3 | 1.8 | 6.3 | 0.0 | 0.2 | 0.0 | 0.0 | 1.3 | 0.6 | 0.0 | 0.0 | 10.6 |
| bedroom-b | 0.1 | 0.3 | 1.2 | 3.5 | 0.0 | 0.1 | 0.0 | 0.0 | 0.7 | 0.5 | 0.0 | 0.0 | 6.5 |
| bedroom-c | 0.1 | 0.3 | 1.6 | 4.9 | 0.0 | 0.1 | 0.0 | 0.0 | 1.0 | 0.8 | 0.0 | 0.0 | 8.8 |
| bedroom2-a | 0.3 | 0.3 | 13.2 | 15.5 | 0.0 | 0.4 | 0.1 | 0.0 | 5.9 | 4.1 | 0.0 | 0.0 | 39.8 |
| bedroom2-b | 0.4 | 0.2 | 20.6 | 26.1 | 0.0 | 0.4 | 0.1 | 0.0 | 9.8 | 5.5 | 0.0 | 0.0 | 63.3 |
| bedroom2-c | 0.3 | 0.3 | 13.9 | 12.7 | 0.0 | 0.5 | 0.1 | 0.0 | 5.3 | 5.0 | 0.0 | 0.0 | 38.0 |
| bathroom-a | 0.1 | 0.6 | 1.4 | 2.5 | 0.0 | 0.1 | 0.0 | 0.0 | 0.9 | 0.5 | 0.0 | 0.0 | 6.2 |
| bathroom-b | 0.1 | 0.3 | 2.6 | 8.2 | 0.0 | 0.2 | 0.0 | 0.0 | 2.7 | 0.7 | 0.0 | 0.0 | 14.8 |
| bathroom-c | 0.1 | 0.3 | 1.3 | 3.1 | 0.0 | 0.1 | 0.0 | 0.0 | 0.8 | 0.4 | 0.0 | 0.0 | 6.0 |
| kitchen-a | 0.2 | 0.4 | 8.1 | 9.7 | 0.0 | 0.2 | 0.1 | 0.0 | 2.8 | 1.7 | 0.0 | 0.0 | 23.3 |
| kitchen-b | 0.0 | 0.3 | 0.0 | 0.6 | 0.0 | 0.3 | 0.0 | 0.0 | 0.0 | 0.2 | 0.0 | 0.0 | 1.4 |
| kitchen-c | 0.2 | 0.4 | 12.4 | 10.6 | 0.0 | 0.3 | 0.1 | 0.0 | 2.2 | 2.6 | 0.0 | 0.0 | 28.9 |
| bedroom-a-video | 0.1 | 0.4 | 0.8 | 3.5 | 0.0 | 0.1 | 0.0 | 0.0 | 1.4 | 0.2 | 25.1 | 0.0 | 31.6 |
